"""Constructores de comidas para las pruebas de Alimentación (sin datos reales)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from glucosa.analytics.glucose_filters import CUSTOM, Period, resolve_period
from glucosa.data.timeutil import parse_timestamp
from glucosa.models.records import MealItem, MealRecord, MealType

NOW = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)


def meal(
    uuid: str,
    local: str,
    kind: MealType | None,
    items: list[tuple[str, str]] | None = None,
    comment: str | None = None,
) -> MealRecord:
    """``local`` es la hora de pared de Chile en ISO sin zona, como la guarda Android."""
    return MealRecord(
        uuid=uuid,
        type=kind,
        eaten_at=parse_timestamp(f"{local}:00.000000"),
        comment=comment,
        items=tuple(MealItem(name, quantity) for name, quantity in (items or [])),
    )


def period(first: date, last: date) -> Period:
    return resolve_period(CUSTOM, NOW, first, last)


def sample_meals() -> list[MealRecord]:
    """Siete comidas en tres días del 20 al 26 de octubre de 2026 (martes a lunes)."""
    return [
        meal(
            "m1",
            "2026-10-20T08:00",
            MealType.BREAKFAST,
            [("Pan", "2 rebanadas"), ("Huevo", "1 unidad")],
        ),
        meal(
            "m2",
            "2026-10-20T13:30",
            MealType.LUNCH,
            [("Arroz", "1 tz"), ("Pollo", "150 g"), ("Ensalada", "1 tz")],
        ),
        meal("m3", "2026-10-20T21:00", MealType.DINNER, [("Pan", "1 rebanada")]),
        meal(
            "m4", "2026-10-22T08:30", MealType.BREAKFAST, [("pan", "3 rebanadas"), ("Palta", "1/2")]
        ),
        meal("m5", "2026-10-22T14:00", MealType.LUNCH, []),
        meal("m6", "2026-10-25T20:40", MealType.BREAKFAST, [("Café", "1 tz")]),
        meal("m7", "2026-10-25T22:30", None, [("Pan", "2 rebanadas")], comment="texto libre"),
    ]


WEEK = (date(2026, 10, 20), date(2026, 10, 26))
