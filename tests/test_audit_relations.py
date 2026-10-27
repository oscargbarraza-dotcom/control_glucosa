"""Relaciones entre métricas: cobertura temporal, coherencia del momento y continuidad."""

from glucosa.audit.relations import (
    assess_continuity,
    daily_coverage,
    intake_glucose_coverage,
    meal_glucose_coverage,
    moment_consistency,
)
from glucosa.data.timeutil import parse_timestamp as t
from glucosa.models.records import (
    BiometricRecord,
    DoseUnit,
    GlucoseMoment,
    GlucoseRecord,
    IntakeItem,
    IntakeRecord,
    MealRecord,
    MealType,
    Origin,
)


def g(when, value=100, moment=GlucoseMoment.NOW, origin=Origin.MANUAL):
    return GlucoseRecord(f"g-{when}", value, moment, t(when), None, origin)


def meal(when, kind=MealType.LUNCH):
    return MealRecord(f"m-{when}", kind, t(when), None, ())


def intake(when):
    return IntakeRecord(f"i-{when}", t(when), None, (IntakeItem("X", 1.0, DoseUnit.TABLET),))


def bio(when):
    return BiometricRecord(f"b-{when}", 80.0, None, None, None, t(when), None)


def test_meal_coverage_counts_measurements_before_and_after_each_meal():
    meals = [
        meal("2026-10-20T13:00:00.000"),  # pre 12:30 y post 14:00 → completa
        meal("2026-10-21T13:00:00.000"),  # solo pre
        meal("2026-10-22T13:00:00.000"),  # nada
    ]
    glucose = [
        g("2026-10-20T12:30:00.000"),
        g("2026-10-20T14:00:00.000"),
        g("2026-10-20T14:30:00.000"),
        g("2026-10-21T12:45:00.000"),
    ]

    c = meal_glucose_coverage(meals, glucose)

    assert (c.meals, c.with_pre, c.with_post, c.with_both) == (3, 2, 1, 1)
    assert c.median_post_count == 0  # medianas de [2, 0, 0]


def test_window_boundaries_are_inclusive_and_configurable():
    meals = [meal("2026-10-20T13:00:00.000")]
    glucose = [g("2026-10-20T13:30:00.000")]  # justo en el borde de 30 min
    assert meal_glucose_coverage(meals, glucose).with_post == 1
    assert meal_glucose_coverage(meals, glucose, post_minutes=(45, 180)).with_post == 0


def test_moment_consistency_checks_that_labelled_meals_exist_nearby():
    meals = [meal("2026-10-20T13:00:00.000", MealType.LUNCH)]
    glucose = [
        g("2026-10-20T14:30:00.000", moment=GlucoseMoment.AFTER_LUNCH),  # coherente
        g("2026-10-20T12:30:00.000", moment=GlucoseMoment.BEFORE_LUNCH),  # coherente
        g("2026-10-20T21:00:00.000", moment=GlucoseMoment.AFTER_DINNER),  # sin cena registrada
        g("2026-10-20T09:00:00.000", moment=GlucoseMoment.NOW),  # no se evalúa
        g("2026-10-20T07:00:00.000", moment=GlucoseMoment.WAKING_UP),  # no se evalúa
    ]

    c = moment_consistency(glucose, meals)

    assert (c.checked, c.consistent, c.no_matching_meal) == (3, 2, 1)


def test_daily_coverage_intersects_the_days_of_each_module():
    glucose = [g("2026-10-20T08:00:00.000"), g("2026-10-21T08:00:00.000")]
    meals = [meal("2026-10-20T13:00:00.000")]
    intakes = [intake("2026-10-20T08:00:00.000")]
    bios = [bio("2026-10-20T07:00:00.000"), bio("2026-10-23T07:00:00.000")]

    c = daily_coverage(glucose, meals, intakes, bios)

    assert (c.first_day.isoformat(), c.last_day.isoformat()) == ("2026-10-20", "2026-10-23")
    assert c.calendar_days == 4
    assert (c.days_glucose, c.days_meals, c.days_intakes, c.days_biometrics) == (2, 1, 1, 2)
    assert c.days_glucose_and_meals == 1
    assert c.days_all_four == 1


def test_intake_glucose_coverage_uses_before_and_after_windows():
    intakes = [intake("2026-10-20T08:00:00.000"), intake("2026-10-21T08:00:00.000")]
    glucose = [g("2026-10-20T07:30:00.000"), g("2026-10-20T10:00:00.000")]
    c = intake_glucose_coverage(intakes, glucose)
    assert (c.intakes, c.with_pre, c.with_post) == (2, 1, 1)


def test_manual_isolated_measurements_do_not_qualify_for_time_in_range():
    glucose = [g(f"2026-10-20T{h:02d}:00:00.000") for h in (8, 12, 20)]
    result = assess_continuity(glucose)
    assert result.continuous_series_available is False
    assert result.imported == 0
    assert "manual" in result.reason.lower()


def test_dense_imported_series_qualifies_for_time_in_range():
    glucose = [
        g(f"2026-10-20T{h:02d}:{m:02d}:00.000", origin=Origin.IMPORTED)
        for h in range(8, 12)
        for m in range(0, 60, 15)
    ]
    result = assess_continuity(glucose)
    assert result.continuous_series_available is True
    assert result.median_gap_imported_minutes == 15.0
