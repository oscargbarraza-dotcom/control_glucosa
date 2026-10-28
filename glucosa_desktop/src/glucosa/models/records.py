"""Modelos inmutables de los registros de SeguimientoGlucosa.

Los valores de los enums coinciden con los nombres (``enum.name``) que la app
Android escribe en Firestore. Un valor desconocido NO se reemplaza por uno por
defecto: el modelo lo deja en ``None`` y el parsing lo reporta como aviso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Origin(StrEnum):
    """Origen *inferido* de una medición de glucosa.

    Android no guarda el origen en un campo propio: las mediciones importadas
    desde el sensor llevan en el comentario "Importado desde X." o "Tomado
    desde X.". Ausencia de esa marca = ``MANUAL`` (no es una garantía).
    """

    MANUAL = "manual"
    IMPORTED = "imported"


class GlucoseMoment(StrEnum):
    NOW = "now"
    WAKING_UP = "wakingUp"
    BEFORE_BREAKFAST = "beforeBreakfast"
    AFTER_BREAKFAST = "afterBreakfast"
    BEFORE_LUNCH = "beforeLunch"
    AFTER_LUNCH = "afterLunch"
    BEFORE_DINNER = "beforeDinner"
    AFTER_DINNER = "afterDinner"
    BEFORE_SLEEP = "beforeSleep"

    @property
    def label(self) -> str:
        return _MOMENT_LABELS[self]


_MOMENT_LABELS = {
    GlucoseMoment.NOW: "Ahora",
    GlucoseMoment.WAKING_UP: "Al despertar",
    GlucoseMoment.BEFORE_BREAKFAST: "Antes desayuno",
    GlucoseMoment.AFTER_BREAKFAST: "Después desayuno",
    GlucoseMoment.BEFORE_LUNCH: "Antes almuerzo",
    GlucoseMoment.AFTER_LUNCH: "Después almuerzo",
    GlucoseMoment.BEFORE_DINNER: "Antes cena",
    GlucoseMoment.AFTER_DINNER: "Después cena",
    GlucoseMoment.BEFORE_SLEEP: "Antes dormir",
}


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    SNACK = "snack"
    DINNER = "dinner"
    OTHER = "other"

    @property
    def label(self) -> str:
        return _MEAL_LABELS[self]


_MEAL_LABELS = {
    MealType.BREAKFAST: "Desayuno",
    MealType.LUNCH: "Almuerzo",
    MealType.SNACK: "Once/Merienda",
    MealType.DINNER: "Cena",
    MealType.OTHER: "Otro/Snack",
}


class DoseUnit(StrEnum):
    MILLIGRAM = "milligram"
    MILLILITER = "milliliter"
    TABLET = "tablet"
    UNIT = "unit"
    DROP = "drop"
    OTHER = "other"

    @property
    def label(self) -> str:
        return _UNIT_LABELS[self]


_UNIT_LABELS = {
    DoseUnit.MILLIGRAM: "mg",
    DoseUnit.MILLILITER: "ml",
    DoseUnit.TABLET: "Comprimido",
    DoseUnit.UNIT: "Unidades",
    DoseUnit.DROP: "Gota",
    DoseUnit.OTHER: "Otro",
}


@dataclass(frozen=True)
class GlucoseRecord:
    uuid: str
    value_mg_dl: int
    moment: GlucoseMoment | None
    measured_at: datetime
    comment: str | None
    origin: Origin
    import_source: str | None = None
    cloud_created_at: datetime | None = None


@dataclass(frozen=True)
class MealItem:
    food_name: str
    quantity: str  # texto libre en Android ("1 taza"); no es numérico


@dataclass(frozen=True)
class MealRecord:
    uuid: str
    type: MealType | None
    eaten_at: datetime
    comment: str | None
    items: tuple[MealItem, ...] = ()
    cloud_created_at: datetime | None = None


@dataclass(frozen=True)
class IntakeItem:
    medication_name: str
    quantity: float
    unit: DoseUnit
    custom_unit_label: str | None = None

    @property
    def unit_label(self) -> str:
        """Unidad a mostrar: la etiqueta propia cuando la unidad es "Otro"."""
        if self.unit is DoseUnit.OTHER and self.custom_unit_label:
            return self.custom_unit_label
        return self.unit.label


@dataclass(frozen=True)
class IntakeRecord:
    uuid: str
    taken_at: datetime
    comment: str | None
    items: tuple[IntakeItem, ...] = ()
    cloud_created_at: datetime | None = None


@dataclass(frozen=True)
class BiometricRecord:
    uuid: str
    weight_kg: float
    systolic: int | None
    diastolic: int | None
    heart_rate_bpm: int | None
    measured_at: datetime
    comment: str | None
    cloud_created_at: datetime | None = None

    @property
    def has_blood_pressure(self) -> bool:
        return self.systolic is not None and self.diastolic is not None
