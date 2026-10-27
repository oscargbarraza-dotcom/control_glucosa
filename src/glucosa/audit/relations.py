"""Relaciones entre métricas: cobertura temporal, coherencia del momento y continuidad.

Todo es descriptivo: mide *cuánta información hay* para analizar comidas o tomas
junto a la glucosa. No interpreta causas ni efectos.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median

from glucosa.models.records import (
    BiometricRecord,
    GlucoseMoment,
    GlucoseRecord,
    IntakeRecord,
    MealRecord,
    MealType,
    Origin,
)

MEAL_PRE_MINUTES = (-60, 0)
MEAL_POST_MINUTES = (30, 180)
INTAKE_PRE_MINUTES = (-60, 0)
INTAKE_POST_MINUTES = (30, 240)
# Coherencia del «momento» con las comidas registradas (minutos).
AFTER_MEAL_WINDOW = (0, 240)  # la comida ocurrió hasta 4 h antes de la medición
BEFORE_MEAL_WINDOW = (0, 120)  # la comida ocurrió hasta 2 h después de la medición
# Una serie se considera continua solo con muchas lecturas importadas y poco espaciadas.
CONTINUOUS_MIN_IMPORTED = 12
CONTINUOUS_MAX_MEDIAN_GAP_MINUTES = 20.0

_MOMENT_MEAL: dict[GlucoseMoment, tuple[MealType, bool]] = {
    GlucoseMoment.BEFORE_BREAKFAST: (MealType.BREAKFAST, False),
    GlucoseMoment.AFTER_BREAKFAST: (MealType.BREAKFAST, True),
    GlucoseMoment.BEFORE_LUNCH: (MealType.LUNCH, False),
    GlucoseMoment.AFTER_LUNCH: (MealType.LUNCH, True),
    GlucoseMoment.BEFORE_DINNER: (MealType.DINNER, False),
    GlucoseMoment.AFTER_DINNER: (MealType.DINNER, True),
}


def _count_between(sorted_times: list[datetime], anchor: datetime, window: tuple[int, int]) -> int:
    start = anchor + timedelta(minutes=window[0])
    end = anchor + timedelta(minutes=window[1])
    return bisect_right(sorted_times, end) - bisect_left(sorted_times, start)


def _glucose_times(glucose: Sequence[GlucoseRecord]) -> list[datetime]:
    return sorted(r.measured_at for r in glucose)


# ------------------------------------------------------------ comidas y glucosa
@dataclass(frozen=True)
class MealGlucoseCoverage:
    meals: int
    with_pre: int
    with_post: int
    with_both: int
    median_post_count: float | None


def meal_glucose_coverage(
    meals: Sequence[MealRecord],
    glucose: Sequence[GlucoseRecord],
    pre_minutes: tuple[int, int] = MEAL_PRE_MINUTES,
    post_minutes: tuple[int, int] = MEAL_POST_MINUTES,
) -> MealGlucoseCoverage:
    times = _glucose_times(glucose)
    pre = [_count_between(times, m.eaten_at, pre_minutes) for m in meals]
    post = [_count_between(times, m.eaten_at, post_minutes) for m in meals]
    return MealGlucoseCoverage(
        meals=len(meals),
        with_pre=sum(count > 0 for count in pre),
        with_post=sum(count > 0 for count in post),
        with_both=sum(a > 0 and b > 0 for a, b in zip(pre, post, strict=True)),
        median_post_count=median(post) if post else None,
    )


@dataclass(frozen=True)
class MomentConsistency:
    checked: int  # mediciones cuyo «momento» alude a una comida
    consistent: int
    no_matching_meal: int


def moment_consistency(
    glucose: Sequence[GlucoseRecord], meals: Sequence[MealRecord]
) -> MomentConsistency:
    meal_times: dict[MealType, list[datetime]] = {}
    for meal in meals:
        if meal.type is not None:
            meal_times.setdefault(meal.type, []).append(meal.eaten_at)
    for times in meal_times.values():
        times.sort()
    checked = consistent = 0
    for record in glucose:
        if record.moment not in _MOMENT_MEAL:
            continue
        kind, after = _MOMENT_MEAL[record.moment]
        checked += 1
        times = meal_times.get(kind, [])
        window = (-AFTER_MEAL_WINDOW[1], -AFTER_MEAL_WINDOW[0]) if after else BEFORE_MEAL_WINDOW
        consistent += _count_between(times, record.measured_at, window) > 0
    return MomentConsistency(checked, consistent, checked - consistent)


# --------------------------------------------------------- medicamentos y glucosa
@dataclass(frozen=True)
class IntakeGlucoseCoverage:
    intakes: int
    with_pre: int
    with_post: int


def intake_glucose_coverage(
    intakes: Sequence[IntakeRecord], glucose: Sequence[GlucoseRecord]
) -> IntakeGlucoseCoverage:
    times = _glucose_times(glucose)
    return IntakeGlucoseCoverage(
        intakes=len(intakes),
        with_pre=sum(_count_between(times, i.taken_at, INTAKE_PRE_MINUTES) > 0 for i in intakes),
        with_post=sum(_count_between(times, i.taken_at, INTAKE_POST_MINUTES) > 0 for i in intakes),
    )


# ------------------------------------------------------------ cobertura por día
@dataclass(frozen=True)
class DailyCoverage:
    first_day: date | None
    last_day: date | None
    calendar_days: int
    days_glucose: int
    days_meals: int
    days_intakes: int
    days_biometrics: int
    days_glucose_and_meals: int
    days_all_four: int


def daily_coverage(
    glucose: Sequence[GlucoseRecord],
    meals: Sequence[MealRecord],
    intakes: Sequence[IntakeRecord],
    biometrics: Sequence[BiometricRecord],
) -> DailyCoverage:
    g = {r.measured_at.date() for r in glucose}
    m = {r.eaten_at.date() for r in meals}
    i = {r.taken_at.date() for r in intakes}
    b = {r.measured_at.date() for r in biometrics}
    every = g | m | i | b
    first, last = (min(every), max(every)) if every else (None, None)
    return DailyCoverage(
        first_day=first,
        last_day=last,
        calendar_days=(last - first).days + 1 if first and last else 0,
        days_glucose=len(g),
        days_meals=len(m),
        days_intakes=len(i),
        days_biometrics=len(b),
        days_glucose_and_meals=len(g & m),
        days_all_four=len(g & m & i & b),
    )


# ------------------------------------------------- continuidad (tiempo en rango)
@dataclass(frozen=True)
class ContinuityAssessment:
    imported: int
    median_gap_imported_minutes: float | None
    continuous_series_available: bool
    reason: str


def assess_continuity(glucose: Sequence[GlucoseRecord]) -> ContinuityAssessment:
    """¿Hay una serie continua que permita calcular tiempo en rango?

    Decisión 7 del proyecto: el tiempo en rango NO se calcula con mediciones
    manuales aisladas. Solo se habilita con una serie importada (sensor) densa.
    """
    imported = sorted(r.measured_at for r in glucose if r.origin is Origin.IMPORTED)
    gaps = [(b - a).total_seconds() / 60.0 for a, b in zip(imported, imported[1:], strict=False)]
    median_gap = median(gaps) if gaps else None
    if len(imported) < CONTINUOUS_MIN_IMPORTED:
        return ContinuityAssessment(
            len(imported),
            median_gap,
            False,
            "Solo hay mediciones manuales o muy pocas lecturas de sensor: "
            "se informa el porcentaje de mediciones en rango, no el tiempo en rango.",
        )
    if median_gap is None or median_gap > CONTINUOUS_MAX_MEDIAN_GAP_MINUTES:
        return ContinuityAssessment(
            len(imported),
            median_gap,
            False,
            "Las lecturas de sensor están demasiado espaciadas para ser una serie continua.",
        )
    return ContinuityAssessment(
        len(imported), median_gap, True, "Serie de sensor densa: se puede calcular tiempo en rango."
    )
