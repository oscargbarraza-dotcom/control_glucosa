"""Constructores para las pruebas de la asociación comida – glucosa (sin datos reales)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from glucosa.analytics.meal_readings import GlucoseInputs, Reading, ReadingSource
from glucosa.analytics.meal_view import MealView, meal_views
from glucosa.models.records import MealRecord, MealType

# 13:00 en Santiago (UTC-3 en octubre). Todo se calcula sobre instantes UTC.
T0 = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
NOW = T0 + timedelta(days=3)  # «ahora» inyectado: todos los hitos ya ocurrieron


def at(minutes: float, base: datetime = T0) -> datetime:
    return base + timedelta(minutes=minutes)


_counter = {"n": 0}


def reading(
    source: ReadingSource, minutes: float, value: int = 120, *, base: datetime = T0, ident=None
) -> Reading:
    _counter["n"] += 1
    return Reading(
        instant=at(minutes, base),
        value=value,
        source=source,
        id=ident or f"{source.value}-{_counter['n']}",
    )


def manual(minutes, value=120, **kw):
    return reading(ReadingSource.MANUAL, minutes, value, **kw)


def imported(minutes, value=120, **kw):
    return reading(ReadingSource.IMPORTED, minutes, value, **kw)


def sensor(minutes, value=120, **kw):
    return reading(ReadingSource.SENSOR, minutes, value, **kw)


def scan(minutes, value=120, **kw):
    return reading(ReadingSource.SCAN, minutes, value, **kw)


def sensor_run(first: float, last: float, step: float = 15, value: int = 120, **kw):
    count = int(round((last - first) / step)) + 1
    return [sensor(first + step * i, value, **kw) for i in range(count)]


def inputs(*readings: Reading, export_span=None) -> GlucoseInputs:
    return GlucoseInputs.of(readings, export_span=export_span)


def meal_at(uuid: str, minutes: float = 0, kind=MealType.LUNCH, comment=None, base=T0) -> MealView:
    record = MealRecord(uuid, kind, at(minutes, base), comment)
    return meal_views([record])[0]


def meals(*specs: tuple[str, float]) -> list[MealView]:
    return meal_views([MealRecord(u, MealType.LUNCH, at(m), None) for u, m in specs])
