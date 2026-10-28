"""IMC calculado con la altura configurada localmente en Windows.

Android no sincroniza la altura (solo existe en su tabla local ``user_profile``),
por lo que cada resultado informa la altura utilizada para que la interfaz
pueda mostrarlo claramente. Sin altura no hay IMC: no se estima ni se asume.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BmiCategory(StrEnum):
    UNDERWEIGHT = "underweight"
    NORMAL = "normal"
    OVERWEIGHT = "overweight"
    OBESE = "obese"

    @property
    def label(self) -> str:
        return _BMI_LABELS[self]


_BMI_LABELS = {
    BmiCategory.UNDERWEIGHT: "Bajo peso",
    BmiCategory.NORMAL: "Normal",
    BmiCategory.OVERWEIGHT: "Sobrepeso",
    BmiCategory.OBESE: "Obesidad",
}


@dataclass(frozen=True)
class BmiResult:
    value: float
    height_cm_used: float


def compute_bmi(weight_kg: float, height_cm: float | None) -> BmiResult | None:
    """IMC = peso / altura². ``None`` si no hay altura configurada."""
    if weight_kg <= 0:
        raise ValueError("El peso debe ser positivo.")
    if height_cm is None:
        return None
    if height_cm <= 0:
        raise ValueError("La altura debe ser positiva.")
    meters = height_cm / 100.0
    return BmiResult(value=weight_kg / (meters * meters), height_cm_used=height_cm)


def bmi_category(bmi: float) -> BmiCategory:
    """Rangos estándar de la OMS para adultos (sin distinguir edad ni sexo)."""
    if bmi < 18.5:
        return BmiCategory.UNDERWEIGHT
    if bmi < 25.0:
        return BmiCategory.NORMAL
    if bmi < 30.0:
        return BmiCategory.OVERWEIGHT
    return BmiCategory.OBESE
