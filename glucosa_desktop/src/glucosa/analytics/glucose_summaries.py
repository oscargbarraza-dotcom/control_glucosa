"""Indicadores del módulo Glucosa, calculados **por fuente** y nunca sobre la mezcla.

* Mediciones manuales (Firebase): conteo, estadísticos y **porcentaje de mediciones** bajo/dentro/
  sobre el rango. Ese porcentaje cuenta mediciones aisladas; no es tiempo en rango.
* Sensor (LibreView, solo el historial): estadísticos de las lecturas del período, rango de datos
  disponibles, cobertura, interrupciones y TIR estimado (ver ``glucose_sensor``).
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, median

from glucosa.analytics.glucose_filters import Period
from glucosa.analytics.glucose_sensor import SensorSample, TirParams, TirResult, compute_tir
from glucosa.analytics.glucose_view import Band, GlucosePoint, Kind, classify
from glucosa.models.records import GlucoseMoment

MANUAL_PERCENT_LABEL = "Porcentaje de mediciones manuales (no es tiempo en rango)"
IMPORTED_PERCENT_LABEL = "Porcentaje de mediciones importadas (no es tiempo en rango)"
NO_MOMENT_LABEL = "Sin momento declarado"
DEFAULT_BIN_WIDTH = 20


@dataclass(frozen=True)
class ManualSummary:
    count: int
    last_value: int | None
    last_instant: datetime | None
    mean: float | None
    median: float | None
    minimum: int | None
    maximum: int | None
    below: int
    in_range: int
    above: int
    pct_below: float | None
    pct_in_range: float | None
    pct_above: float | None
    label: str = MANUAL_PERCENT_LABEL


@dataclass(frozen=True)
class MomentSummary:
    moment: GlucoseMoment | None
    label: str
    count: int
    mean: float
    median: float
    minimum: int
    maximum: int
    pct_in_range: float


@dataclass(frozen=True)
class HistogramBin:
    """Intervalo ``[start, end)`` con sus lecturas separadas por clase (cada una en la suya)."""

    start: int
    end: int  # exclusivo
    below: int
    in_range: int
    above: int

    @property
    def count(self) -> int:
        return self.below + self.in_range + self.above


@dataclass(frozen=True)
class SensorSummary:
    count: int
    first_in_period: datetime | None
    last_in_period: datetime | None
    first_available: datetime | None
    last_available: datetime | None
    mean: float | None
    median: float | None
    minimum: int | None
    maximum: int | None
    tir: TirResult
    histogram: tuple[HistogramBin, ...]


def _bands(values: Sequence[int], low: int, high: int) -> tuple[int, int, int]:
    bands = [classify(v, low, high) for v in values]
    return (
        sum(b is Band.BELOW for b in bands),
        sum(b is Band.IN_RANGE for b in bands),
        sum(b is Band.ABOVE for b in bands),
    )


def _summarize_firebase(
    points: Iterable[GlucosePoint], kind: Kind, label: str, low: int, high: int
) -> ManualSummary:
    manual = sorted((p for p in points if p.kind is kind), key=lambda p: p.instant)
    values = [p.value for p in manual]
    if not values:
        return ManualSummary(
            0, None, None, None, None, None, None, 0, 0, 0, None, None, None, label=label
        )
    below, in_range, above = _bands(values, low, high)
    total = len(values)
    return ManualSummary(
        count=total,
        last_value=manual[-1].value,
        last_instant=manual[-1].instant,
        mean=mean(values),
        median=median(values),
        minimum=min(values),
        maximum=max(values),
        below=below,
        in_range=in_range,
        above=above,
        pct_below=below / total,
        pct_in_range=in_range / total,
        pct_above=above / total,
        label=label,
    )


def summarize_manual(points: Iterable[GlucosePoint], low: int, high: int) -> ManualSummary:
    """Solo las mediciones MANUALES de Firebase; las importadas tienen su propio resumen."""
    return _summarize_firebase(points, Kind.MANUAL, MANUAL_PERCENT_LABEL, low, high)


def summarize_imported(points: Iterable[GlucosePoint], low: int, high: int) -> ManualSummary:
    """Solo las mediciones de Firebase marcadas como importadas desde otra aplicación."""
    return _summarize_firebase(points, Kind.IMPORTED, IMPORTED_PERCENT_LABEL, low, high)


def summarize_by_moment(points: Iterable[GlucosePoint], low: int, high: int) -> list[MomentSummary]:
    """Agrupa SOLO por el momento declarado en Android; nunca se infiere desde Alimentación."""
    groups: dict[GlucoseMoment | None, list[int]] = defaultdict(list)
    for point in points:
        if point.kind is Kind.MANUAL:
            groups[point.moment].append(point.value)
    order = [*GlucoseMoment, None]
    rows = []
    for moment in order:
        values = groups.get(moment)
        if not values:
            continue
        _, in_range, _ = _bands(values, low, high)
        rows.append(
            MomentSummary(
                moment=moment,
                label=moment.label if moment else NO_MOMENT_LABEL,
                count=len(values),
                mean=mean(values),
                median=median(values),
                minimum=min(values),
                maximum=max(values),
                pct_in_range=in_range / len(values),
            )
        )
    return rows


def histogram(
    values: Sequence[int], width: int = DEFAULT_BIN_WIDTH, low: int = 70, high: int = 180
) -> list[HistogramBin]:
    """Barras de ``width`` mg/dL; cada lectura se cuenta en SU clase aunque comparta barra."""
    if not values:
        return []
    start = (min(values) // width) * width
    end = (max(values) // width + 1) * width
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0])
    order = {Band.BELOW: 0, Band.IN_RANGE: 1, Band.ABOVE: 2}
    for v in values:
        counts[(v // width) * width][order[classify(v, low, high)]] += 1
    return [HistogramBin(s, s + width, *counts.get(s, [0, 0, 0])) for s in range(start, end, width)]


def summarize_sensor(
    samples: Iterable[SensorSample], period: Period, low: int, high: int
) -> SensorSummary:
    ordered = sorted(samples, key=lambda s: s.instant)
    in_period = [s for s in ordered if period.start <= s.instant < period.end]
    values = [s.value for s in in_period]
    return SensorSummary(
        count=len(in_period),
        first_in_period=in_period[0].instant if in_period else None,
        last_in_period=in_period[-1].instant if in_period else None,
        first_available=ordered[0].instant if ordered else None,
        last_available=ordered[-1].instant if ordered else None,
        mean=mean(values) if values else None,
        median=median(values) if values else None,
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        tir=compute_tir(ordered, period.start, period.end, TirParams(low=low, high=high)),
        histogram=tuple(histogram(values, low=low, high=high)),
    )
