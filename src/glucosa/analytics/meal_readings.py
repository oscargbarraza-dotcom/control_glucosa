"""Lecturas de glucosa de todas las fuentes en un modelo común, para asociarlas con las comidas.

Lógica pura: sin red, sin disco, sin interfaz y sin leer el reloj del sistema. Reglas:

* Cuatro fuentes que **nunca se mezclan** en un estadístico: manual y importada (Firebase),
  historial del sensor y escaneos (LibreView). El comentario y el «momento» del registro no se
  copian: no se usan para clasificar nada.
* Todo en instantes con zona horaria; los originales no se modifican ni se descartan.
* Las **coincidencias** manual ↔ LibreView solo se MARCAN como «probables»: no prueban que sean
  el mismo registro y nunca se elimina ni se fusiona nada.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from glucosa.analytics.glucose_sensor import consolidate_history
from glucosa.models.records import GlucoseRecord, Origin
from glucosa.sources.libre.models import RecordType, StoredReading

SCAN_MATCH_MINUTES = 10  # mismo valor aprobado para el indicador manual ↔ escaneo


class ReadingSource(StrEnum):
    MANUAL = "manual"  # medición manual de Firebase
    IMPORTED = "imported"  # medición de Firebase marcada «importada desde otra aplicación»
    SENSOR = "sensor"  # historial del sensor (LibreView, tipo 0)
    SCAN = "scan"  # escaneo del sensor (LibreView, tipo 1): fuera de las series


# Prioridad solo para desempatar o elegir una lectura representativa (decisión aprobada).
SOURCE_PRIORITY = {
    ReadingSource.MANUAL: 0,
    ReadingSource.IMPORTED: 1,
    ReadingSource.SENSOR: 2,
    ReadingSource.SCAN: 3,
}
SERIES_SOURCES = (ReadingSource.MANUAL, ReadingSource.IMPORTED, ReadingSource.SENSOR)


@dataclass(frozen=True)
class Reading:
    instant: datetime
    value: int  # mg/dL
    source: ReadingSource
    id: str

    def __post_init__(self) -> None:
        if self.instant.tzinfo is None:
            raise ValueError("Las lecturas deben tener zona horaria.")


@dataclass(frozen=True)
class WindowReading:
    """Una lectura con su desfase respecto de la comida (negativo = antes del registro)."""

    reading: Reading
    delta_minutes: float


def _sort_key(reading: Reading) -> tuple[datetime, int, str]:
    return reading.instant, SOURCE_PRIORITY[reading.source], reading.id


@dataclass(frozen=True)
class GlucoseInputs:
    manual: tuple[Reading, ...] = ()
    imported: tuple[Reading, ...] = ()
    sensor: tuple[Reading, ...] = ()
    scans: tuple[Reading, ...] = ()
    export_span: tuple[datetime, datetime] | None = None  # primera y última lectura del historial

    @classmethod
    def of(
        cls, readings: Iterable[Reading], export_span: tuple[datetime, datetime] | None = None
    ) -> "GlucoseInputs":
        groups: dict[ReadingSource, list[Reading]] = {source: [] for source in ReadingSource}
        for reading in readings:
            groups[reading.source].append(reading)
        ordered = {source: tuple(sorted(items, key=_sort_key)) for source, items in groups.items()}
        sensor = ordered[ReadingSource.SENSOR]
        span = export_span or ((sensor[0].instant, sensor[-1].instant) if sensor else None)
        return cls(
            manual=ordered[ReadingSource.MANUAL],
            imported=ordered[ReadingSource.IMPORTED],
            sensor=sensor,
            scans=ordered[ReadingSource.SCAN],
            export_span=span,
        )

    def series(self, source: ReadingSource) -> tuple[Reading, ...]:
        return {
            ReadingSource.MANUAL: self.manual,
            ReadingSource.IMPORTED: self.imported,
            ReadingSource.SENSOR: self.sensor,
            ReadingSource.SCAN: self.scans,
        }[source]


class ReadingIndex:
    """Lecturas ordenadas con búsqueda binaria por intervalo."""

    def __init__(self, readings: Sequence[Reading]) -> None:
        self._readings = tuple(readings)
        self._instants = [r.instant for r in self._readings]

    def __len__(self) -> int:
        return len(self._readings)

    def between(
        self,
        start: datetime,
        end: datetime,
        *,
        include_start: bool = True,
        include_end: bool = True,
    ) -> tuple[Reading, ...]:
        left = (bisect_left if include_start else bisect_right)(self._instants, start)
        right = (bisect_right if include_end else bisect_left)(self._instants, end)
        return self._readings[left:right]


# -------------------------------------------------------------------- construcción
def readings_from_records(records: Iterable[GlucoseRecord]) -> list[Reading]:
    """Mediciones de Firebase → manuales o importadas; sin comentario ni «momento»."""
    return [
        Reading(
            r.measured_at,
            r.value_mg_dl,
            ReadingSource.IMPORTED if r.origin is Origin.IMPORTED else ReadingSource.MANUAL,
            r.uuid,
        )
        for r in records
    ]


@dataclass(frozen=True)
class HistoryReadings:
    sensor: tuple[Reading, ...]
    scans: tuple[Reading, ...]
    duplicates: int  # lecturas repetidas entre dispositivos (se cuentan una vez)
    conflict_minutes: int  # minutos con valores distintos entre dispositivos (se conservan)
    span: tuple[datetime, datetime] | None


def _stable_id(prefix: str, instant: datetime, value: int) -> str:
    return f"{prefix}:{int(instant.timestamp())}:{value}"


def readings_from_history(stored: Iterable[StoredReading]) -> HistoryReadings:
    """Historial ya consolidado entre dispositivos (misma regla de Glucosa) y escaneos aparte."""
    items = list(stored)
    consolidation = consolidate_history(items)
    sensor = [
        Reading(
            r.instant_utc,
            r.glucose_mg_dl,
            ReadingSource.SENSOR,
            _stable_id("sensor", r.instant_utc, r.glucose_mg_dl),
        )
        for r in consolidation.readings
    ]
    scans: dict[str, Reading] = {}
    for r in items:
        if r.record_type is RecordType.SCAN:
            ident = _stable_id("scan", r.instant_utc, r.glucose_mg_dl)
            scans.setdefault(
                ident, Reading(r.instant_utc, r.glucose_mg_dl, ReadingSource.SCAN, ident)
            )
    ordered_sensor = tuple(sorted(sensor, key=_sort_key))
    span = (ordered_sensor[0].instant, ordered_sensor[-1].instant) if ordered_sensor else None
    return HistoryReadings(
        sensor=ordered_sensor,
        scans=tuple(sorted(scans.values(), key=_sort_key)),
        duplicates=consolidation.duplicates,
        conflict_minutes=consolidation.conflict_minutes,
        span=span,
    )


# ------------------------------------------------------------------- coincidencias
class CoincidenceKind(StrEnum):
    MANUAL_SCAN = "manual_scan"
    MANUAL_HISTORY = "manual_history"


@dataclass(frozen=True)
class ProbableCoincidence:
    """Coincidencia PROBABLE (cercanía y mismo valor): no demuestra que sea el mismo registro."""

    kind: CoincidenceKind
    manual_id: str
    other_id: str
    delta_seconds: int  # otra lectura − manual
    certainty: str = "probable"


def _minute(instant: datetime) -> datetime:
    return instant.replace(second=0, microsecond=0)


def _assign_one_to_one(
    pairs: list[tuple[int, Reading, Reading]], kind: CoincidenceKind
) -> list[ProbableCoincidence]:
    """Asignación 1 a 1 y determinista: primero las más cercanas; empate → la anterior."""
    pairs.sort(key=lambda p: (abs(p[0]), p[1].instant, p[2].instant, p[1].id, p[2].id))
    used_manual: set[str] = set()
    used_other: set[str] = set()
    found = []
    for delta, manual, other in pairs:
        if manual.id in used_manual or other.id in used_other:
            continue
        used_manual.add(manual.id)
        used_other.add(other.id)
        found.append(ProbableCoincidence(kind, manual.id, other.id, delta))
    return found


def find_coincidences(
    manual: Sequence[Reading],
    scans: Sequence[Reading],
    history: Sequence[Reading],
    scan_tolerance_minutes: float = SCAN_MATCH_MINUTES,
) -> tuple[ProbableCoincidence, ...]:
    """Marca coincidencias manual ↔ escaneo (±10 min, mismo valor) y manual ↔ historial (mismo
    minuto y valor). Solo marca: ningún registro se elimina, se modifica ni se fusiona."""
    tolerance = timedelta(minutes=scan_tolerance_minutes)
    scan_index = ReadingIndex(sorted(scans, key=_sort_key))
    scan_pairs: list[tuple[int, Reading, Reading]] = []
    history_by_key: dict[tuple[datetime, int], list[Reading]] = {}
    for reading in history:
        history_by_key.setdefault((_minute(reading.instant), reading.value), []).append(reading)
    history_pairs: list[tuple[int, Reading, Reading]] = []
    for m in manual:
        for s in scan_index.between(m.instant - tolerance, m.instant + tolerance):
            if s.value == m.value:
                scan_pairs.append((round((s.instant - m.instant).total_seconds()), m, s))
        for h in history_by_key.get((_minute(m.instant), m.value), ()):
            history_pairs.append((round((h.instant - m.instant).total_seconds()), m, h))
    found = _assign_one_to_one(scan_pairs, CoincidenceKind.MANUAL_SCAN)
    found += _assign_one_to_one(history_pairs, CoincidenceKind.MANUAL_HISTORY)
    return tuple(sorted(found, key=lambda c: (c.kind.value, c.manual_id, c.other_id)))
