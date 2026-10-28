"""Hitos posprandiales +60 y +90 min: lectura más cercana por fuente, sin inferir cumplimiento.

Reglas aprobadas:

* La tolerancia es un **entero de 5 a 20 minutos** (10 por defecto). Para el historial de
  LibreView la tolerancia efectiva es como mínimo 8 minutos.
* Por fuente se elige la lectura más cercana al hito; **empate → la anterior**; luego el id
  (determinista).
* Estados que no se confunden: medición cercana, sin medición manual registrada, hito pendiente
  (con la hora actual INYECTADA), sin datos del sensor, export fuera de cobertura y hueco real.
* No se mira ningún comentario ni se habla de «cumplimiento» de recordatorios: es descriptivo.
* Una misma lectura puede ser la más cercana de dos hitos o de dos comidas: se informa, no se
  reasigna.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from glucosa.analytics.meal_readings import (
    SERIES_SOURCES,
    SOURCE_PRIORITY,
    GlucoseInputs,
    ReadingIndex,
    ReadingSource,
    WindowReading,
)

MILESTONES: tuple[int, ...] = (60, 90)
MIN_TOLERANCE_MINUTES = 5
MAX_TOLERANCE_MINUTES = 20
DEFAULT_TOLERANCE_MINUTES = 10
SENSOR_MINIMUM_TOLERANCE_MINUTES = 8


@dataclass(frozen=True)
class MilestoneParams:
    tolerance_minutes: int = DEFAULT_TOLERANCE_MINUTES
    sensor_minimum_minutes: int = SENSOR_MINIMUM_TOLERANCE_MINUTES

    def __post_init__(self) -> None:
        value = self.tolerance_minutes
        valid = isinstance(value, int) and not isinstance(value, bool)
        if not valid or not MIN_TOLERANCE_MINUTES <= value <= MAX_TOLERANCE_MINUTES:
            raise ValueError(
                "La tolerancia de los hitos debe ser un número entero de minutos entre 5 y 20."
            )
        if not isinstance(self.sensor_minimum_minutes, int) or self.sensor_minimum_minutes < 1:
            raise ValueError("La tolerancia mínima del sensor debe ser de al menos 1 minuto.")


def effective_tolerance(source: ReadingSource, params: MilestoneParams) -> int:
    if source is ReadingSource.SENSOR:
        return max(params.tolerance_minutes, params.sensor_minimum_minutes)
    return params.tolerance_minutes


class MilestoneStatus(StrEnum):
    MEASURED = "measured"  # hay una lectura dentro de la tolerancia
    NOT_REGISTERED = "not_registered"  # manual/importada: «sin medición registrada» cerca del hito
    NOT_APPLICABLE = "not_applicable"  # no hay lecturas importadas en ninguna parte
    PENDING = "pending"  # el hito aún no ocurre (según la hora actual inyectada)
    NO_SENSOR_DATA = "no_sensor_data"  # no hay datos de LibreView
    OUTSIDE_EXPORT = "outside_export"  # el hito cae fuera del período que cubre el export
    SENSOR_GAP = "sensor_gap"  # dentro del export, pero sin lectura en la tolerancia


@dataclass(frozen=True)
class MilestoneResult:
    meal_uuid: str
    minutes: int
    source: ReadingSource
    target: datetime
    status: MilestoneStatus
    tolerance_minutes: int
    reading: WindowReading | None = None  # desfase respecto de la comida
    offset_minutes: float | None = None  # lectura − hito (negativo = antes del hito)
    shared_with: tuple[tuple[str, int], ...] = ()  # otros (comida, hito) con la misma lectura


def _nearest(candidates: Sequence, target: datetime):
    return min(candidates, key=lambda r: (abs(r.instant - target), r.instant, r.id), default=None)


def _missing_status(
    source: ReadingSource, inputs: GlucoseInputs, target: datetime
) -> MilestoneStatus:
    if source is not ReadingSource.SENSOR:
        return MilestoneStatus.NOT_REGISTERED
    if not inputs.sensor or inputs.export_span is None:
        return MilestoneStatus.NO_SENSOR_DATA
    start, end = inputs.export_span
    if target < start or target > end:
        return MilestoneStatus.OUTSIDE_EXPORT
    return MilestoneStatus.SENSOR_GAP


def _one(
    meal_uuid: str,
    eaten_at: datetime,
    minutes: int,
    source: ReadingSource,
    inputs: GlucoseInputs,
    indexes: Mapping[ReadingSource, ReadingIndex],
    now: datetime,
    params: MilestoneParams,
) -> MilestoneResult:
    target = eaten_at + timedelta(minutes=minutes)
    tolerance = effective_tolerance(source, params)
    base = {
        "meal_uuid": meal_uuid,
        "minutes": minutes,
        "source": source,
        "target": target,
        "tolerance_minutes": tolerance,
    }
    if source is ReadingSource.IMPORTED and not inputs.imported:
        return MilestoneResult(**base, status=MilestoneStatus.NOT_APPLICABLE)
    if target > now:
        return MilestoneResult(**base, status=MilestoneStatus.PENDING)
    width = timedelta(minutes=tolerance)
    found = _nearest(indexes[source].between(target - width, target + width), target)
    if found is None:
        return MilestoneResult(**base, status=_missing_status(source, inputs, target))
    return MilestoneResult(
        **base,
        status=MilestoneStatus.MEASURED,
        reading=WindowReading(found, (found.instant - eaten_at).total_seconds() / 60),
        offset_minutes=(found.instant - target).total_seconds() / 60,
    )


def compute_milestones(
    meal_uuid: str,
    eaten_at: datetime,
    inputs: GlucoseInputs,
    indexes: Mapping[ReadingSource, ReadingIndex],
    now: datetime,
    params: MilestoneParams,
) -> dict[int, dict[ReadingSource, MilestoneResult]]:
    return {
        minutes: {
            source: _one(meal_uuid, eaten_at, minutes, source, inputs, indexes, now, params)
            for source in SERIES_SOURCES
        }
        for minutes in MILESTONES
    }


def representative(results: Mapping[ReadingSource, MilestoneResult]) -> MilestoneResult | None:
    """Selección representativa entre fuentes: más cercana, anterior en empates, luego la prioridad
    manual › importada › sensor. No promedia ni mezcla estadísticos."""
    measured = [r for r in results.values() if r.status is MilestoneStatus.MEASURED]
    return min(
        measured,
        key=lambda r: (abs(r.offset_minutes), r.offset_minutes, SOURCE_PRIORITY[r.source]),
        default=None,
    )


def mark_shared(
    per_meal: Mapping[str, dict[int, dict[ReadingSource, MilestoneResult]]],
) -> dict[str, dict[int, dict[ReadingSource, MilestoneResult]]]:
    """Señala las lecturas elegidas por más de un hito (de una o de varias comidas)."""
    users: dict[tuple[ReadingSource, str], list[tuple[str, int]]] = {}
    for uuid, by_minutes in per_meal.items():
        for minutes, by_source in by_minutes.items():
            for source, result in by_source.items():
                if result.reading is not None:
                    users.setdefault((source, result.reading.reading.id), []).append(
                        (uuid, minutes)
                    )
    marked = {}
    for uuid, by_minutes in per_meal.items():
        marked[uuid] = {
            minutes: {
                source: (
                    replace(result, shared_with=_others(users, source, result, uuid, minutes))
                    if result.reading is not None
                    else result
                )
                for source, result in by_source.items()
            }
            for minutes, by_source in by_minutes.items()
        }
    return marked


def _others(users, source, result, uuid, minutes) -> tuple[tuple[str, int], ...]:
    everyone = users[(source, result.reading.reading.id)]
    return tuple(sorted(u for u in everyone if u != (uuid, minutes)))
