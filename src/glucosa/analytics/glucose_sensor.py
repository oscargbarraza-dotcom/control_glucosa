"""Cobertura temporal y tiempo en rango (TIR) **estimado** del sensor (CSV de LibreView).

Algoritmo (documentado también en ``PROJECT_CONTEXT.md``, sección 11.7):

1. Solo se usan lecturas del **historial del sensor (tipo 0)**. Nunca mediciones manuales ni
   escaneos, y nunca se mezclan con ellas.
2. Todo se calcula sobre **instantes** (UTC), no sobre la hora del reloj: así un cambio de
   horario no inventa ni oculta interrupciones.
3. **Tiempo representado por cada lectura.** Una lectura en ``t`` representa el tiempo hasta el
   punto medio con la lectura vecina de cada lado, siempre que el intervalo con ese vecino sea
   ≤ ``max_gap_minutes`` (30 min). Si el intervalo es mayor —una **interrupción**— o no hay vecino,
   la lectura representa como máximo ``cadence/2`` (7,5 min) de ese lado. El tiempo restante de la
   interrupción no se atribuye a nadie y no se interpola glucosa: cada tramo conserva la clase
   (bajo / en rango / sobre) de **su** lectura.
4. **Límites del período.** El tramo de cada lectura se recorta a ``[inicio, fin)``. Las lecturas
   inmediatamente anteriores al inicio o posteriores al fin se usan solo como vecinas: aportan
   la parte de su tiempo que cae dentro de la ventana. ``fin`` es exclusivo.
5. **Cobertura** = minutos atribuidos / minutos del período solicitado, de modo que los días sin
   lecturas y los bordes sin datos bajan la cobertura.
6. **TIR estimado** = minutos atribuidos en cada clase / minutos atribuidos (porcentaje del tiempo
   cubierto). Se informa únicamente si hay ≥ ``min_readings`` lecturas dentro del período y la
   cobertura es ≥ ``min_coverage``; de lo contrario el estado es ``insufficient``.
7. Clasificación en los límites: bajo si v < mín; en rango si mín ≤ v ≤ máx; sobre si v > máx.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from glucosa.data.timeutil import SANTIAGO
from glucosa.sources.libre.models import RecordType, StoredReading

LABEL = "TIR estimado a partir del CSV de LibreView"
REASON_MESSAGES = {
    "sin_lecturas": "Datos insuficientes: no hay lecturas del sensor en el período.",
    "lecturas_insuficientes": "Datos insuficientes: hay muy pocas lecturas del sensor.",
    "cobertura_insuficiente": "Datos insuficientes: la cobertura del período es demasiado baja.",
}
_COVERAGE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class SensorSample:
    instant: datetime
    value: int


@dataclass(frozen=True)
class TirParams:
    low: int = 70
    high: int = 180
    cadence_minutes: float = 15.0
    max_gap_minutes: float = 30.0
    min_coverage: float = 0.70
    min_readings: int = 96

    def __post_init__(self) -> None:
        if not self.low < self.high:
            raise ValueError("El rango objetivo debe cumplir mínimo < máximo.")
        if self.cadence_minutes <= 0 or self.max_gap_minutes < self.cadence_minutes:
            raise ValueError("La cadencia y el intervalo máximo no son válidos.")
        if not 0.0 <= self.min_coverage <= 1.0 or self.min_readings < 0:
            raise ValueError("Los mínimos de cobertura no son válidos.")


@dataclass(frozen=True)
class Interruption:
    """Intervalo entre dos lecturas separadas por más del máximo permitido (recortado a la ventana).

    ``minutes`` es la duración de ese intervalo completo; parte de ella (hasta ±cadencia/2 junto
    a cada lectura) sí se atribuye a las lecturas vecinas y no cuenta como tiempo sin cobertura.
    """

    start: datetime
    end: datetime
    minutes: float


@dataclass(frozen=True)
class TirResult:
    status: Literal["ok", "insufficient"]
    reason: str | None
    message: str
    label: str
    window_start: datetime
    window_end: datetime
    window_minutes: float
    readings_in_window: int
    covered_minutes: float
    coverage: float
    below_minutes: float
    in_range_minutes: float
    above_minutes: float
    pct_below: float | None
    pct_in_range: float | None
    pct_above: float | None
    in_range_hours_per_day: float | None
    estimated: bool
    interruptions: tuple[Interruption, ...]
    longest_gap_minutes: float
    days_without_readings: int


@dataclass(frozen=True)
class HistoryConsolidation:
    """Historial del sensor sin repetir el mismo registro leído por dos dispositivos.

    ``conflict_minutes`` cuenta los minutos con valores DISTINTOS entre dispositivos: no se fusionan
    (se conservan todos) y se informan para que nadie los pase por alto.
    """

    readings: tuple[StoredReading, ...]
    duplicates: int
    conflict_minutes: int


def consolidate_history(readings: Iterable[StoredReading]) -> HistoryConsolidation:
    """Única implementación de la deduplicación del historial (tipo 0); ignora los escaneos.

    Mismo minuto y mismo valor = el mismo registro (el mismo sensor leído por dos dispositivos):
    se cuenta una vez. Mismo minuto y valor distinto: se conservan ambos y se informa el conflicto.
    """
    kept: list[StoredReading] = []
    seen: set[tuple[datetime, int]] = set()
    values_by_minute: dict[datetime, set[int]] = {}
    duplicates = 0
    for r in readings:
        if r.record_type is not RecordType.HISTORIC:
            continue
        minute = r.instant_utc.replace(second=0, microsecond=0)
        if (minute, r.glucose_mg_dl) in seen:
            duplicates += 1
            continue
        seen.add((minute, r.glucose_mg_dl))
        values_by_minute.setdefault(minute, set()).add(r.glucose_mg_dl)
        kept.append(r)
    conflicts = sum(len(values) > 1 for values in values_by_minute.values())
    return HistoryConsolidation(tuple(kept), duplicates, conflicts)


def samples_from_stored(readings: Iterable[StoredReading]) -> list[SensorSample]:
    """Solo el historial del sensor (tipo 0), ya consolidado; los escaneos no se usan."""
    return [
        SensorSample(r.instant_utc, r.glucose_mg_dl) for r in consolidate_history(readings).readings
    ]


def _minutes(delta: timedelta) -> float:
    return delta.total_seconds() / 60.0


def _classify(value: int, params: TirParams) -> str:
    if value < params.low:
        return "below"
    return "in" if value <= params.high else "above"


def _attributed_time(
    ordered: Sequence[SensorSample], start: datetime, end: datetime, params: TirParams
) -> dict[str, float]:
    half_cadence = timedelta(minutes=params.cadence_minutes / 2)
    max_gap = timedelta(minutes=params.max_gap_minutes)
    minutes = {"below": 0.0, "in": 0.0, "above": 0.0}
    for i, sample in enumerate(ordered):
        back = half_cadence
        if i > 0 and (gap := sample.instant - ordered[i - 1].instant) <= max_gap:
            back = gap / 2
        forward = half_cadence
        if i + 1 < len(ordered) and (gap := ordered[i + 1].instant - sample.instant) <= max_gap:
            forward = gap / 2
        segment_start = max(sample.instant - back, start)
        segment_end = min(sample.instant + forward, end)
        if segment_end > segment_start:
            minutes[_classify(sample.value, params)] += _minutes(segment_end - segment_start)
    return minutes


def _interruptions(
    ordered: Sequence[SensorSample], start: datetime, end: datetime, params: TirParams
) -> tuple[Interruption, ...]:
    max_gap = timedelta(minutes=params.max_gap_minutes)
    found = []
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if later.instant - earlier.instant <= max_gap:
            continue
        gap_start, gap_end = max(earlier.instant, start), min(later.instant, end)
        if gap_end > gap_start:
            found.append(Interruption(gap_start, gap_end, _minutes(gap_end - gap_start)))
    return tuple(found)


def _days_without_readings(
    in_window: Sequence[SensorSample], start: datetime, end: datetime
) -> int:
    first = start.astimezone(SANTIAGO).date()
    last = (end - timedelta(microseconds=1)).astimezone(SANTIAGO).date()
    with_data = {s.instant.astimezone(SANTIAGO).date() for s in in_window}
    return sum(
        1
        for offset in range((last - first).days + 1)
        if first + timedelta(days=offset) not in with_data
    )


def compute_tir(
    samples: Iterable[SensorSample],
    start: datetime,
    end: datetime,
    params: TirParams | None = None,
) -> TirResult:
    """Cobertura y TIR estimado de ``[start, end)``; las fechas deben tener zona horaria."""
    params = params or TirParams()
    ordered = sorted(samples, key=lambda s: s.instant)
    if start.tzinfo is None or end.tzinfo is None or any(s.instant.tzinfo is None for s in ordered):
        raise ValueError("Las fechas deben incluir zona horaria.")
    if end <= start:
        raise ValueError("El fin del período debe ser posterior al inicio.")
    in_window = [s for s in ordered if start <= s.instant < end]

    minutes = _attributed_time(ordered, start, end, params)
    covered = sum(minutes.values())
    window_minutes = _minutes(end - start)
    coverage = min(1.0, covered / window_minutes)
    interruptions = _interruptions(ordered, start, end, params)

    reason = None
    if not in_window:
        reason = "sin_lecturas"
    elif len(in_window) < params.min_readings:
        reason = "lecturas_insuficientes"
    elif coverage + _COVERAGE_TOLERANCE < params.min_coverage:
        reason = "cobertura_insuficiente"
    ok = reason is None and covered > 0

    def share(key: str) -> float | None:
        return minutes[key] / covered if ok else None

    pct_in = share("in")
    return TirResult(
        status="ok" if ok else "insufficient",
        reason=reason,
        message=REASON_MESSAGES[reason] if reason else LABEL,
        label=LABEL,
        window_start=start,
        window_end=end,
        window_minutes=window_minutes,
        readings_in_window=len(in_window),
        covered_minutes=covered,
        coverage=coverage,
        below_minutes=minutes["below"],
        in_range_minutes=minutes["in"],
        above_minutes=minutes["above"],
        pct_below=share("below"),
        pct_in_range=pct_in,
        pct_above=share("above"),
        in_range_hours_per_day=pct_in * 24 if pct_in is not None else None,
        estimated=ok and coverage < 1.0 - _COVERAGE_TOLERANCE,
        interruptions=interruptions,
        longest_gap_minutes=max((i.minutes for i in interruptions), default=0.0),
        days_without_readings=_days_without_readings(in_window, start, end),
    )
