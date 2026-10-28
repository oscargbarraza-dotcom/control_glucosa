"""Auditoría de fechas: formatos, zonas horarias, rango y desfase evento → subida a la nube."""

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from glucosa.data.firestore_decode import FirestoreDocument
from glucosa.data.timeutil import parse_timestamp, wall_clock_issue

_NAIVE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?Z")
_OFFSET = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}")
_FUTURE_TOLERANCE = timedelta(minutes=5)
_NEGATIVE_LAG_TOLERANCE_MINUTES = -1.0  # holgura por relojes distintos
_LAG_1H, _LAG_24H = 60.0, 24 * 60.0


@dataclass(frozen=True)
class LagStats:
    """Minutos entre la fecha del evento y la creación del documento en la nube."""

    count: int
    negative: int  # evento fechado DESPUÉS de su subida (más de 1 min): reloj o zona mal
    over_1h: int
    over_24h: int
    min_minutes: float
    median_minutes: float
    p90_minutes: float
    max_minutes: float


@dataclass(frozen=True)
class DateReport:
    collection: str
    field: str
    total: int
    formats: Mapping[str, int]
    fraction_digits: Mapping[int, int]
    unparseable: int
    ambiguous: int
    nonexistent: int
    future: int
    earliest: datetime | None
    latest: datetime | None
    lag: LagStats | None


def classify_format(value: Any) -> str:
    if value is None:
        return "ausente"
    if not isinstance(value, str):
        return "otro"
    if _NAIVE.fullmatch(value):
        return "local_sin_zona"
    if _UTC.fullmatch(value):
        return "utc_Z"
    if _OFFSET.fullmatch(value):
        return "con_offset"
    return "otro"


def _quantile(sorted_values: list[float], fraction: float) -> float:
    return sorted_values[min(len(sorted_values) - 1, int(fraction * len(sorted_values)))]


def _lag_stats(lags: list[float]) -> LagStats | None:
    if not lags:
        return None
    ordered = sorted(lags)
    return LagStats(
        count=len(ordered),
        negative=sum(1 for v in ordered if v < _NEGATIVE_LAG_TOLERANCE_MINUTES),
        over_1h=sum(1 for v in ordered if v > _LAG_1H),
        over_24h=sum(1 for v in ordered if v > _LAG_24H),
        min_minutes=ordered[0],
        median_minutes=_quantile(ordered, 0.5),
        p90_minutes=_quantile(ordered, 0.9),
        max_minutes=ordered[-1],
    )


def audit_dates(
    collection: str, field: str, docs: Iterable[FirestoreDocument], now: datetime
) -> DateReport:
    formats: Counter[str] = Counter()
    digits: Counter[int] = Counter()
    parsed: list[datetime] = []
    lags: list[float] = []
    unparseable = ambiguous = nonexistent = future = total = 0
    for doc in docs:
        total += 1
        raw = doc.fields.get(field)
        formats[classify_format(raw)] += 1
        if isinstance(raw, str) and "." in raw:
            digits[len(re.split(r"[Z+-]", raw.split(".", 1)[1])[0])] += 1
        try:
            moment = parse_timestamp(raw)
            issue = wall_clock_issue(raw)
        except ValueError:
            unparseable += 1
            continue
        parsed.append(moment)
        ambiguous += issue == "ambiguous"
        nonexistent += issue == "nonexistent"
        future += moment > now + _FUTURE_TOLERANCE
        if doc.create_time:
            with suppress(ValueError):
                lags.append((parse_timestamp(doc.create_time) - moment).total_seconds() / 60.0)
    return DateReport(
        collection=collection,
        field=field,
        total=total,
        formats=dict(formats),
        fraction_digits=dict(digits),
        unparseable=unparseable,
        ambiguous=ambiguous,
        nonexistent=nonexistent,
        future=future,
        earliest=min(parsed) if parsed else None,
        latest=max(parsed) if parsed else None,
        lag=_lag_stats(lags),
    )
