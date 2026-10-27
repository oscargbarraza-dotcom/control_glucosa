"""Períodos de análisis y filtros comunes del módulo Glucosa (lógica pura, sin Streamlit).

Los períodos se expresan en días **locales de Chile**. Cada período es ``[inicio, fin)`` en UTC:
empieza en la medianoche local del primer día y termina al final del último día, **recortado al
instante actual** para que las horas futuras no penalicen la cobertura.
"""

import calendar
from collections.abc import Iterable, Set
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from glucosa.analytics.glucose_view import Band, GlucosePoint, Kind, Source, classify
from glucosa.data.timeutil import SANTIAGO
from glucosa.models.records import GlucoseMoment

PERIOD_OPTIONS: tuple[str, ...] = (
    "Hoy",
    "Últimos 7 días",
    "Últimos 30 días",
    "Últimos 3 meses",
    "Últimos 6 meses",
    "Últimos 12 meses",
    "Rango personalizado",
)
CUSTOM = "Rango personalizado"
_RELATIVE_DAYS = {"Hoy": 0, "Últimos 7 días": 6, "Últimos 30 días": 29}
_RELATIVE_MONTHS = {"Últimos 3 meses": 3, "Últimos 6 meses": 6, "Últimos 12 meses": 12}


@dataclass(frozen=True)
class Period:
    start: datetime  # UTC, inclusivo
    end: datetime  # UTC, exclusivo
    label: str
    first_day: date  # días locales cubiertos
    last_day: date


def _local_midnight(day: date) -> datetime:
    # En el día del cambio de horario la medianoche no existe: zoneinfo usa el instante real
    # del primer momento del día.
    return datetime.combine(day, time(0), tzinfo=SANTIAGO).astimezone(UTC)


def _months_back(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) - months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def resolve_period(
    option: str,
    now: datetime,
    custom_start: date | None = None,
    custom_end: date | None = None,
) -> Period:
    """Convierte la opción elegida en un intervalo ``[inicio, fin)`` en UTC."""
    today = now.astimezone(SANTIAGO).date()
    if option == CUSTOM:
        if custom_start is None or custom_end is None:
            raise ValueError("Indica las fechas de inicio y fin del rango personalizado.")
        if custom_end < custom_start:
            raise ValueError("La fecha de fin debe ser igual o posterior a la de inicio.")
        first, last = custom_start, custom_end
    elif option in _RELATIVE_DAYS:
        first, last = today - timedelta(days=_RELATIVE_DAYS[option]), today
    elif option in _RELATIVE_MONTHS:
        first = _months_back(today, _RELATIVE_MONTHS[option]) + timedelta(days=1)
        last = today
    else:
        raise ValueError(f"Período desconocido: {option!r}")
    start = _local_midnight(first)
    # A medianoche exacta «ahora» coincide con el inicio de «Hoy»: el período no puede quedar vacío.
    end = max(
        min(_local_midnight(last + timedelta(days=1)), now.astimezone(UTC)),
        start + timedelta(microseconds=1),
    )
    return Period(start, end, option, first, last)


def filter_points(
    points: Iterable[GlucosePoint],
    period: Period | None = None,
    sources: Set[Source] | None = None,
    kinds: Set[Kind] | None = None,
    bands: Set[Band] | None = None,
    moments: Set[GlucoseMoment | None] | None = None,
    low: int = 70,
    high: int = 180,
) -> list[GlucosePoint]:
    """Filtra conservando el orden. ``None`` en un criterio significa «sin filtrar».

    El filtro de momento se aplica a los registros de Firebase (manuales e importados); los del
    sensor no tienen momento declarado y siempre pasan por él. ``None`` dentro de ``moments``
    representa «sin momento declarado»: sin esa opción esos registros quedan fuera.
    """
    kept = []
    for point in points:
        if period is not None and not period.start <= point.instant < period.end:
            continue
        if sources is not None and point.source not in sources:
            continue
        if kinds is not None and point.kind not in kinds:
            continue
        if bands is not None and classify(point.value, low, high) not in bands:
            continue
        if moments is not None and point.source is Source.FIREBASE and point.moment not in moments:
            continue
        kept.append(point)
    return kept
