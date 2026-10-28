"""Fuentes simuladas de Alimentación: las de Glucosa más las comidas de Firebase."""

from __future__ import annotations

from glucosa.models.records import MealRecord, MealType
from glucosa.ui.glucose_sources import ManualLoad, MealLoad, SourceStatus
from tests.glucose_fakes import FETCHED_AT, NOW, START, FakeSources
from tests.meal_helpers import meal

__all__ = ["FETCHED_AT", "NOW", "START", "FakeMealSources", "meal_records"]


def meal_records() -> tuple[MealRecord, ...]:
    """Comidas del 20 al 25 de octubre de 2026 (hora de Chile); el sensor cubre del 20 al 24."""
    return (
        meal(
            "m1", "2026-10-21T09:30", MealType.BREAKFAST, [("Pan", "2 rebanadas"), ("Huevo", "1")]
        ),
        meal("m2", "2026-10-21T13:30", MealType.LUNCH, [("Arroz", "1 tz"), ("Pollo", "150 g")]),
        meal("m3", "2026-10-21T13:50", MealType.SNACK, [("Pan", "1 rebanada")]),
        meal("m4", "2026-10-22T20:00", MealType.DINNER, [("Palta", "1/2")]),
        meal("m5", "2026-10-23T08:40", MealType.BREAKFAST, []),
        meal(
            "m6", "2026-10-25T21:00", None, [("Café", "1 tz"), ("<b>Pan</b>", "2")], "texto libre"
        ),
    )


class FakeMealSources(FakeSources):
    def __init__(self, scenario: str = "full") -> None:
        super().__init__(scenario)
        self.meal_calls = 0
        self._manual_failures = 1 if scenario == "firebase_flaky" else 0

    def load_meals(self) -> MealLoad:
        self.meal_calls += 1
        if self.marker is None:
            return MealLoad(
                SourceStatus.NO_SESSION,
                message="No hay sesión. Ejecuta: python -m glucosa.login login",
            )
        if self.scenario == "meals_error":
            return MealLoad(SourceStatus.ERROR, message="Sin conexión con Firebase.")
        if self.scenario == "no_meals":
            return MealLoad(SourceStatus.OK, records=(), fetched_at=FETCHED_AT)
        return MealLoad(
            SourceStatus.OK,
            records=meal_records(),
            rejected=1 if self.scenario == "meals_rejected" else 0,
            fetched_at=FETCHED_AT,
        )

    def load_manual(self) -> ManualLoad:
        """``firebase_flaky``: la primera lectura falla y las siguientes funcionan (recuperación)."""
        if self._manual_failures:
            self._manual_failures -= 1
            self.manual_calls += 1
            return ManualLoad(SourceStatus.ERROR, message="Sin conexión con Firebase.")
        if self.scenario == "manual_empty":  # la lectura funciona y la colección está vacía
            self.manual_calls += 1
            return ManualLoad(SourceStatus.OK, records=(), fetched_at=FETCHED_AT)
        return super().load_manual()
