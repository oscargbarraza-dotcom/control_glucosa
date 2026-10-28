"""Hitos posprandiales +60 y +90 min: lectura más cercana por fuente, sin inferir cumplimiento."""

import dataclasses
import random
from datetime import UTC, datetime, timedelta

import pytest

from glucosa.analytics.meal_glucose import AssociationParams, associate_meals
from glucosa.analytics.meal_milestones import (
    MILESTONES,
    MilestoneParams,
    MilestoneStatus,
    effective_tolerance,
)
from glucosa.analytics.meal_readings import ReadingSource as S
from glucosa.analytics.meal_readings import readings_from_records
from glucosa.analytics.meal_view import meal_views
from glucosa.models.records import GlucoseMoment, GlucoseRecord, MealRecord, MealType, Origin
from tests.meal_glucose_helpers import (
    NOW,
    T0,
    at,
    imported,
    inputs,
    manual,
    meal_at,
    meals,
    sensor,
    sensor_run,
)


def milestones(readings, minutes=0, tolerance=10, now=NOW, meal_minutes=None):
    params = AssociationParams(milestones=MilestoneParams(tolerance_minutes=tolerance))
    specs = meals(*(meal_minutes or [("m1", minutes)]))
    return associate_meals(specs, inputs(*readings), now, params)


def first(outcome, source, minutes):
    return outcome.meals[0].milestones[minutes][source]


# ---------------------------------------------------------------- parámetros
def test_milestones_are_60_and_90_with_a_default_tolerance_of_10_minutes():
    assert MILESTONES == (60, 90)
    assert (
        MilestoneParams().tolerance_minutes == 10 and MilestoneParams().sensor_minimum_minutes == 8
    )


@pytest.mark.parametrize("value", [5, 6, 10, 15, 19, 20])
def test_any_integer_tolerance_between_5_and_20_is_valid(value):
    assert MilestoneParams(tolerance_minutes=value).tolerance_minutes == value


@pytest.mark.parametrize("value", [0, 4, 21, 100, -5, 10.5, True, "10", None])
def test_tolerances_outside_5_to_20_or_not_integers_are_rejected(value):
    with pytest.raises(ValueError, match="5 y 20"):
        MilestoneParams(tolerance_minutes=value)


def test_the_effective_sensor_tolerance_is_never_below_8_minutes():
    assert effective_tolerance(S.SENSOR, MilestoneParams(tolerance_minutes=5)) == 8
    assert effective_tolerance(S.SENSOR, MilestoneParams(tolerance_minutes=8)) == 8
    assert effective_tolerance(S.SENSOR, MilestoneParams(tolerance_minutes=12)) == 12
    assert effective_tolerance(S.MANUAL, MilestoneParams(tolerance_minutes=5)) == 5
    assert effective_tolerance(S.IMPORTED, MilestoneParams(tolerance_minutes=7)) == 7


# --------------------------------------------------------------- selección
def test_the_nearest_reading_to_each_milestone_is_selected_per_source():
    outcome = milestones([manual(52), manual(58, 111), manual(64), manual(88, 140), manual(97)])

    sixty, ninety = first(outcome, S.MANUAL, 60), first(outcome, S.MANUAL, 90)
    assert (sixty.status, sixty.reading.reading.value, sixty.offset_minutes) == (
        MilestoneStatus.MEASURED,
        111,
        -2.0,
    )
    assert (ninety.reading.reading.value, ninety.offset_minutes) == (140, -2.0)


def test_the_tolerance_boundary_is_inclusive_and_one_second_more_is_outside():
    inside = milestones([manual(70)], tolerance=10)
    outside = milestones([manual(70 + 1 / 60)], tolerance=10)

    assert first(inside, S.MANUAL, 60).status is MilestoneStatus.MEASURED
    assert first(outside, S.MANUAL, 60).status is MilestoneStatus.NOT_REGISTERED


def test_a_distance_tie_selects_the_earlier_reading():
    outcome = milestones([manual(65, 150), manual(55, 100)])

    chosen = first(outcome, S.MANUAL, 60)
    assert (chosen.reading.reading.value, chosen.offset_minutes) == (100, -5.0)


def test_selection_is_deterministic_for_any_input_order():
    pool = [manual(m, 100 + m) for m in (50, 55, 65, 70, 85, 95)] + [
        sensor(m) for m in range(40, 110, 15)
    ]
    reference = milestones(pool)
    rng = random.Random(11)
    for _ in range(5):
        rng.shuffle(pool)
        assert milestones(pool) == reference


def test_the_tolerance_changes_what_can_be_selected():
    narrow = milestones([manual(72)], tolerance=10)
    wide = milestones([manual(72)], tolerance=15)

    assert first(narrow, S.MANUAL, 60).status is MilestoneStatus.NOT_REGISTERED
    assert first(wide, S.MANUAL, 60).status is MilestoneStatus.MEASURED


def test_the_milestone_reports_the_offset_from_the_target_and_the_meal():
    chosen = first(milestones([manual(63, 120)]), S.MANUAL, 60)

    assert chosen.offset_minutes == 3.0 and chosen.reading.delta_minutes == 63.0
    assert chosen.target == at(60) and chosen.tolerance_minutes == 10


# --------------------------------------------------------------- separación por fuente
def test_each_source_has_its_own_result_for_the_same_milestone():
    outcome = milestones([manual(60, 100), imported(58, 110), sensor(62, 140)])

    assert first(outcome, S.MANUAL, 60).reading.reading.value == 100
    assert first(outcome, S.IMPORTED, 60).reading.reading.value == 110
    assert first(outcome, S.SENSOR, 60).reading.reading.value == 140


def test_a_manual_reading_never_satisfies_the_sensor_milestone_and_vice_versa():
    only_manual = milestones([manual(60)] + [sensor(0), sensor(200)])
    only_sensor = milestones([sensor(60)] + [manual(300)])

    assert first(only_manual, S.SENSOR, 60).status is MilestoneStatus.SENSOR_GAP
    assert first(only_sensor, S.MANUAL, 60).status is MilestoneStatus.NOT_REGISTERED


def test_imported_is_not_applicable_when_there_are_no_imported_readings_at_all():
    outcome = milestones([manual(60)])

    assert first(outcome, S.IMPORTED, 60).status is MilestoneStatus.NOT_APPLICABLE


def test_imported_is_not_registered_when_imported_exist_elsewhere_but_not_near_the_milestone():
    outcome = milestones([imported(500)])

    assert first(outcome, S.IMPORTED, 60).status is MilestoneStatus.NOT_REGISTERED


def test_the_combined_representative_picks_the_nearest_with_the_manual_imported_sensor_tiebreak():
    outcome = milestones([manual(60), sensor(60), imported(60)])

    assert outcome.meals[0].milestone_representative[60].reading.reading.source is S.MANUAL


# --------------------------------------------------------------------- estados
def test_missing_manual_reading_is_reported_as_not_registered():
    outcome = milestones([manual(200)] + sensor_run(0, 200))

    assert first(outcome, S.MANUAL, 60).status is MilestoneStatus.NOT_REGISTERED
    assert first(outcome, S.SENSOR, 60).status is MilestoneStatus.MEASURED


def test_a_future_milestone_is_pending_for_every_source_and_never_a_miss():
    now = at(70)  # +60 ya ocurrió; +90 todavía no

    outcome = milestones([manual(200)], now=now)

    assert first(outcome, S.MANUAL, 60).status is MilestoneStatus.NOT_REGISTERED
    for source in (S.MANUAL, S.SENSOR):
        assert first(outcome, source, 90).status is MilestoneStatus.PENDING
    # Sin lecturas importadas en ninguna parte, esa fuente no aplica (no es «pendiente»).
    assert first(outcome, S.IMPORTED, 90).status is MilestoneStatus.NOT_APPLICABLE


def test_a_milestone_exactly_at_now_is_not_pending():
    outcome = milestones([manual(60)], now=at(60))

    assert first(outcome, S.MANUAL, 60).status is MilestoneStatus.MEASURED


def test_the_clock_is_an_injected_argument_and_the_modules_never_read_the_system_clock():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "glucosa" / "analytics"
    for name in ("meal_readings.py", "meal_glucose.py", "meal_milestones.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        calls = {
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not calls & {"datetime.now", "datetime.utcnow", "time.time", "date.today"}, name


def test_sensor_without_any_data_at_all_is_reported_apart_from_gaps():
    outcome = milestones([manual(60)])

    assert first(outcome, S.SENSOR, 60).status is MilestoneStatus.NO_SENSOR_DATA


def test_a_milestone_after_the_end_of_the_export_is_outside_coverage_not_a_gap():
    outcome = milestones(sensor_run(-120, 20))  # el export termina en +20

    assert first(outcome, S.SENSOR, 60).status is MilestoneStatus.OUTSIDE_EXPORT
    assert first(outcome, S.SENSOR, 90).status is MilestoneStatus.OUTSIDE_EXPORT


def test_a_milestone_before_the_start_of_the_export_is_also_outside_coverage():
    outcome = milestones(sensor_run(300, 500))

    assert first(outcome, S.SENSOR, 60).status is MilestoneStatus.OUTSIDE_EXPORT


def test_a_milestone_inside_the_export_without_a_reading_is_a_real_gap():
    readings = sensor_run(-120, 30) + sensor_run(150, 300)  # interrupción entre +30 y +150

    outcome = milestones(readings)

    assert first(outcome, S.SENSOR, 60).status is MilestoneStatus.SENSOR_GAP
    assert first(outcome, S.SENSOR, 90).status is MilestoneStatus.SENSOR_GAP


def test_a_reading_within_the_effective_sensor_tolerance_wins_over_the_outside_export_status():
    outcome = milestones(sensor_run(-120, 55))  # última lectura en +55; tolerancia efectiva ≥ 8

    assert first(outcome, S.SENSOR, 60).status is MilestoneStatus.MEASURED


def test_the_sensor_uses_at_least_8_minutes_even_with_a_5_minute_tolerance():
    outcome = milestones([sensor(7.5), sensor(52.5), sensor(120)], tolerance=5)

    assert first(outcome, S.SENSOR, 60).status is MilestoneStatus.MEASURED  # a 7,5 min del hito
    assert first(outcome, S.MANUAL, 60).status is MilestoneStatus.NOT_REGISTERED


# ------------------------------------------------- lecturas candidatas para varios hitos
def test_one_reading_can_be_the_nearest_for_both_milestones_and_both_are_flagged():
    outcome = milestones([manual(75, 150)], tolerance=20)

    sixty, ninety = first(outcome, S.MANUAL, 60), first(outcome, S.MANUAL, 90)
    assert sixty.reading.reading.id == ninety.reading.reading.id
    assert sixty.shared_with == (("m1", 90),) and ninety.shared_with == (("m1", 60),)


def test_one_reading_used_by_two_close_meals_is_flagged_for_both():
    outcome = milestones([manual(70, 150)], meal_minutes=[("m1", 0), ("m2", 15)], tolerance=10)

    first_meal, second_meal = outcome.meals
    assert first_meal.milestones[60][S.MANUAL].shared_with == (("m2", 60),)
    assert second_meal.milestones[60][S.MANUAL].shared_with == (("m1", 60),)


def test_unshared_readings_have_no_flags():
    outcome = milestones([manual(60), manual(90)])

    assert first(outcome, S.MANUAL, 60).shared_with == ()
    assert first(outcome, S.MANUAL, 90).shared_with == ()


# --------------------------------------------------- cambio de horario de Chile
def test_milestones_use_real_elapsed_minutes_across_the_repeated_hour_of_april():
    base = datetime(2026, 4, 5, 2, 30, tzinfo=UTC)  # 23:30 (1.ª vez)
    record = MealRecord("m", MealType.DINNER, base, None)
    marker = manual(
        60, 150, base=base
    )  # 23:30 (2.ª vez): misma hora de pared, 60 min reales después

    outcome = associate_meals(
        meal_views([record]), inputs(marker), base + timedelta(days=1), AssociationParams()
    )

    chosen = outcome.meals[0].milestones[60][S.MANUAL]
    assert chosen.status is MilestoneStatus.MEASURED and chosen.offset_minutes == 0.0


# -------------------------------------------------------------- comentarios y cumplimiento
def test_a_free_text_comment_never_changes_a_classification():
    def record(comment, minutes):
        return GlucoseRecord(
            "g",
            120,
            GlucoseMoment.AFTER_LUNCH,
            at(minutes),
            comment,
            Origin.MANUAL,
        )

    far = [record("60 minutos", 200)]  # dice «60 minutos» pero está a 200 min de la comida
    near_without_text = [record(None, 61)]
    far_result = associate_meals(meals(("m1", 0)), GlucoseInputsFrom(far), NOW, AssociationParams())
    near_result = associate_meals(
        meals(("m1", 0)), GlucoseInputsFrom(near_without_text), NOW, AssociationParams()
    )

    assert first(far_result, S.MANUAL, 60).status is MilestoneStatus.NOT_REGISTERED
    assert first(near_result, S.MANUAL, 60).status is MilestoneStatus.MEASURED


def GlucoseInputsFrom(records):  # noqa: N802 - pequeño helper de prueba
    return inputs(*readings_from_records(records))


def test_readings_carry_no_comment_and_results_expose_no_compliance_vocabulary():
    reading_fields = {f.name for f in dataclasses.fields(manual(1))}
    result_fields = {
        f.name
        for cls in (
            type(first(milestones([manual(60)]), S.MANUAL, 60)),
            type(milestones([manual(60)]).meals[0]),
        )
        for f in dataclasses.fields(cls)
    }

    assert "comment" not in reading_fields
    assert not any(
        word in name
        for name in result_fields
        for word in ("complian", "cumpl", "adher", "reminder")
    )


def test_the_default_params_object_uses_the_approved_tolerance():
    assert AssociationParams().milestones.tolerance_minutes == 10


def test_meal_at_helper_builds_chronological_views():
    assert meal_at("a", 0).eaten_at == T0
