"""Auditoría de calidad por módulo (datos sintéticos, registros ya tipados)."""

from glucosa.audit.quality import (
    audit_biometrics,
    audit_glucose,
    audit_intakes,
    audit_meals,
    normalize_name,
)
from glucosa.data.timeutil import parse_timestamp as t
from glucosa.models.records import (
    BiometricRecord,
    DoseUnit,
    GlucoseMoment,
    GlucoseRecord,
    IntakeItem,
    IntakeRecord,
    MealItem,
    MealRecord,
    MealType,
    Origin,
)


def g(uuid, when, value, origin=Origin.MANUAL, moment=GlucoseMoment.NOW, comment=None):
    return GlucoseRecord(uuid, value, moment, t(when), comment, origin)


# --------------------------------------------------------------------- glucosa
def test_glucose_summary_counts_ranges_origins_and_density():
    records = [
        g("1", "2026-10-20T08:00:00.000", 65),
        g("2", "2026-10-20T12:00:00.000", 120, moment=GlucoseMoment.BEFORE_LUNCH),
        g("3", "2026-10-20T20:00:00.000", 200, origin=Origin.IMPORTED),
        g("4", "2026-10-21T08:00:00.000", 15),  # fuera del rango de la app
        g("5", "2026-10-21T08:00:00.000", 15),  # mismo instante y valor
    ]

    q = audit_glucose(records)

    assert q.total == 5
    assert (q.manual, q.imported) == (4, 1)
    assert (q.below_70, q.in_70_180, q.above_180) == (3, 1, 1)
    assert q.out_of_app_range == 2
    assert (q.min_value, q.max_value) == (15, 200)
    assert q.days_with_data == 2
    assert q.per_day_buckets == {"1": 0, "2": 1, "3-4": 1, "5+": 0}
    assert q.max_per_day == 3
    assert q.same_instant_same_value == 1
    assert q.moment_distribution["now"] == 4


def test_glucose_possible_duplicates_include_near_identical_entries():
    records = [
        g("1", "2026-10-20T08:00:00.000", 100),
        g("2", "2026-10-20T08:01:00.000", 100),  # mismo valor a 1 minuto
        g("3", "2026-10-20T08:30:00.000", 100),
    ]
    assert audit_glucose(records).near_duplicates == 1


def test_glucose_gaps_use_the_median_interval_between_consecutive_measurements():
    records = [
        g("1", "2026-10-20T08:00:00.000", 100),
        g("2", "2026-10-20T08:30:00.000", 100),
        g("3", "2026-10-20T10:30:00.000", 100),
    ]
    assert audit_glucose(records).median_gap_minutes == 75.0


def test_glucose_empty_input_is_safe():
    q = audit_glucose([])
    assert q.total == 0 and q.min_value is None and q.median_gap_minutes is None


# ---------------------------------------------------------------------- comidas
def meal(uuid, when, kind=MealType.LUNCH, items=()):
    return MealRecord(uuid, kind, t(when), None, tuple(items))


def test_name_normalization_ignores_case_accents_and_spacing():
    assert normalize_name("  Plátano  ") == normalize_name("platano")
    assert normalize_name("Pan  integral") == normalize_name("pan integral")


def test_meal_summary_reports_empty_items_quantity_format_and_name_variants():
    meals = [
        meal(
            "1",
            "2026-10-20T13:00:00.000",
            items=[MealItem("Pan", "2 rebanadas"), MealItem("pan", "1")],
        ),
        meal("2", "2026-10-20T20:00:00.000", MealType.DINNER, items=[MealItem("Sopa", "un plato")]),
        meal("3", "2026-10-21T13:00:00.000", items=[]),
    ]

    q = audit_meals(meals)

    assert q.total == 3 and q.empty_items == 1
    assert q.items_total == 3
    assert q.quantity_numeric_leading == 2  # "2 rebanadas" y "1"
    assert q.quantity_free_text == 1  # "un plato"
    assert q.distinct_names_raw == 3 and q.distinct_names_normalized == 2
    assert q.type_distribution == {"lunch": 2, "dinner": 1}


def test_meal_duplicates_are_same_type_and_items_within_a_minute():
    items = [MealItem("Pan", "1")]
    meals = [
        meal("1", "2026-10-20T13:00:00.000", items=items),
        meal("2", "2026-10-20T13:00:30.000", items=items),
        meal("3", "2026-10-20T13:00:30.000", MealType.DINNER, items=items),
    ]
    assert audit_meals(meals).possible_duplicates == 1


# ------------------------------------------------------------------ medicamentos
def intake(uuid, when, items):
    return IntakeRecord(uuid, t(when), None, tuple(items))


def test_intake_summary_reports_units_and_inconsistent_units_per_medication():
    intakes = [
        intake("1", "2026-10-20T08:00:00.000", [IntakeItem("Met", 500.0, DoseUnit.MILLIGRAM)]),
        intake("2", "2026-10-21T08:00:00.000", [IntakeItem("Met", 1.0, DoseUnit.TABLET)]),
        intake("3", "2026-10-21T20:00:00.000", []),
    ]

    q = audit_intakes(intakes)

    assert q.total == 3 and q.empty_items == 1 and q.items_total == 2
    assert q.unit_distribution == {"milligram": 1, "tablet": 1}
    assert q.medications_with_multiple_units == 1
    assert q.distinct_medications_normalized == 1


# --------------------------------------------------------------------- biometría
def bio(uuid, when, weight, sys=None, dia=None, hr=None):
    return BiometricRecord(uuid, weight, sys, dia, hr, t(when), None)


def test_biometric_summary_reports_completeness_plausibility_and_jumps():
    records = [
        bio("1", "2026-10-20T07:00:00.000", 80.0, 120, 80, 70),
        bio("2", "2026-10-20T20:00:00.000", 85.0, 118, 120, None),  # salto 5 kg; sys < dia
        bio("3", "2026-10-22T07:00:00.000", 80.5),
    ]

    q = audit_biometrics(records)

    assert q.total == 3
    assert (q.with_blood_pressure, q.with_heart_rate) == (2, 1)
    assert q.systolic_not_above_diastolic == 1
    assert q.large_weight_jumps == 1
    assert (q.weight_min, q.weight_max) == (80.0, 85.0)
    assert q.measurement_days == 2
