"""Glucosa de referencia y glucosa previa: son cosas distintas y se rotulan como tales."""

import pytest

from glucosa.analytics.meal_glucose import Window, associate_meals
from glucosa.analytics.meal_readings import ReadingSource as S
from tests.meal_glucose_helpers import (
    NOW,
    at,
    imported,
    inputs,
    manual,
    meal_at,
    sensor,
    sensor_run,
)


def outcome_for(*readings):
    (outcome,) = associate_meals([meal_at("m1")], inputs(*readings), NOW).meals
    return outcome


# ---------------------------------------------------------------------- referencia
def test_reference_is_the_nearest_reading_to_the_record_within_minus_60_and_plus_5():
    outcome = outcome_for(manual(-40, 100), manual(-12, 110), manual(20, 130))

    reference = outcome.reference[S.MANUAL]
    assert (reference.reading.reading.value, reference.reading.delta_minutes) == (110, -12.0)
    assert reference.after_record is False and reference.window is Window.PRE


def test_a_tie_in_distance_prefers_the_earlier_reading():
    outcome = outcome_for(manual(3, 150), manual(-3, 100))

    reference = outcome.reference[S.MANUAL]
    assert (reference.reading.reading.value, reference.reading.delta_minutes) == (100, -3.0)


def test_the_reading_exactly_at_plus_5_is_eligible_but_later_ones_are_not():
    assert outcome_for(manual(5, 140)).reference[S.MANUAL].reading.reading.value == 140
    assert S.MANUAL not in outcome_for(manual(5.02, 140)).reference


def test_the_reading_exactly_at_minus_60_is_eligible_but_earlier_ones_are_not():
    assert outcome_for(manual(-60, 90)).reference[S.MANUAL].reading.delta_minutes == -60.0
    assert S.MANUAL not in outcome_for(manual(-60.02, 90)).reference


def test_a_reference_after_the_record_is_flagged_and_never_presented_as_previous():
    outcome = outcome_for(manual(3, 150))

    reference = outcome.reference[S.MANUAL]
    assert reference.after_record is True and reference.window is Window.AT
    assert S.MANUAL not in outcome.previous  # no hay lectura previa: solo una posterior al registro


def test_a_reference_at_the_exact_record_instant_is_not_after_the_record():
    reference = outcome_for(manual(0, 120)).reference[S.MANUAL]

    assert reference.after_record is False and reference.reading.delta_minutes == 0.0


def test_reference_keeps_source_time_and_offset():
    outcome = outcome_for(sensor(-4, 111))

    reference = outcome.reference[S.SENSOR]
    assert reference.reading.reading.source is S.SENSOR
    assert reference.reading.reading.instant == at(-4)
    assert reference.reading.delta_minutes == -4.0
    assert reference.window is Window.AT  # −4 cae en «Al comer», aunque es anterior al registro


def test_references_are_computed_separately_for_each_source():
    outcome = outcome_for(manual(-30, 100), sensor(-2, 140), imported(-10, 120))

    assert {s: r.reading.reading.value for s, r in outcome.reference.items()} == {
        S.MANUAL: 100,
        S.SENSOR: 140,
        S.IMPORTED: 120,
    }


def test_no_reference_when_nothing_lies_in_the_reference_range():
    outcome = outcome_for(manual(-61), manual(6), manual(90))

    assert outcome.reference == {} and outcome.previous == {}


# ------------------------------------------------------------------- glucosa previa
def test_previous_is_the_last_reading_strictly_before_the_at_window_and_inside_the_pre_window():
    outcome = outcome_for(manual(-50, 100), manual(-20, 110), manual(-5, 130), manual(2, 140))

    previous = outcome.previous[S.MANUAL]
    assert (previous.reading.value, previous.delta_minutes) == (110, -20.0)  # −5 ya es «Al comer»


def test_previous_excludes_the_reading_exactly_at_minus_5_and_includes_minus_60():
    assert outcome_for(manual(-5, 130)).previous == {}
    assert outcome_for(manual(-60, 90)).previous[S.MANUAL].delta_minutes == -60.0
    assert outcome_for(manual(-5.0001, 130)).previous[S.MANUAL].delta_minutes == pytest.approx(
        -5.0001
    )


def test_previous_and_reference_can_be_different_readings():
    outcome = outcome_for(manual(-30, 100), manual(-1, 125))

    assert outcome.previous[S.MANUAL].reading.value == 100
    assert outcome.reference[S.MANUAL].reading.reading.value == 125


def test_previous_is_computed_per_source():
    outcome = outcome_for(manual(-30, 100), sensor(-25, 140))

    assert outcome.previous[S.MANUAL].reading.value == 100
    assert outcome.previous[S.SENSOR].reading.value == 140


# -------------------------------------------------------- selección combinada (representativa)
def test_the_combined_representative_is_the_nearest_reading_among_sources():
    outcome = outcome_for(manual(-8, 100), sensor(-3, 140))

    assert outcome.combined_reference.reading.reading.source is S.SENSOR


def test_the_combined_tie_on_distance_prefers_the_earlier_reading_even_over_source_priority():
    outcome = outcome_for(manual(3, 100), sensor(-3, 140))

    assert (
        outcome.combined_reference.reading.reading.source is S.SENSOR
    )  # anterior, aunque no sea manual


def test_the_combined_tie_with_same_distance_and_side_uses_manual_imported_sensor_priority():
    only_sensor_and_imported = outcome_for(sensor(-10, 140), imported(-10, 120))
    all_three = outcome_for(sensor(-10, 140), imported(-10, 120), manual(-10, 100))

    assert only_sensor_and_imported.combined_reference.reading.reading.source is S.IMPORTED
    assert all_three.combined_reference.reading.reading.source is S.MANUAL


def test_the_combined_previous_is_the_latest_previous_reading_with_the_same_priority_rule():
    outcome = outcome_for(manual(-30, 100), sensor(-20, 140), imported(-20, 120))

    assert outcome.combined_previous.reading.source is S.IMPORTED


def test_no_combined_representative_without_readings():
    outcome = outcome_for()

    assert outcome.combined_reference is None and outcome.combined_previous is None


# --------------------------------------------------------- estadísticos descriptivos
def test_post_window_reports_the_observed_maximum_minimum_and_when_they_occurred():
    outcome = outcome_for(manual(10, 150), manual(45, 210), manual(120, 180), manual(150, 95))

    post = outcome.summary(Window.POST, S.MANUAL)
    assert post.n == 4 and post.stats_allowed is True
    assert (post.maximum.reading.value, post.maximum.delta_minutes) == (210, 45.0)
    assert (post.minimum.reading.value, post.minimum.delta_minutes) == (95, 150.0)


def test_equal_maxima_report_the_earliest_one():
    post = outcome_for(manual(30, 200), manual(90, 200)).summary(Window.POST, S.MANUAL)

    assert post.maximum.delta_minutes == 30.0


def test_the_maximum_minus_reference_uses_the_same_source_only():
    covered = [sensor(m, 160 if m == 60 else 130) for m in range(-120, 301, 15)]
    outcome = outcome_for(manual(-2, 100), manual(60, 190), *covered)

    assert outcome.rise[S.MANUAL] == 90 and outcome.rise[S.SENSOR] == 30


def test_the_rise_is_not_reported_without_a_reference_in_that_source():
    outcome = outcome_for(manual(60, 190))

    assert S.MANUAL not in outcome.rise


def test_sensor_statistics_are_withheld_when_the_window_is_not_covered_enough():
    gappy = [sensor(10, 150), sensor(170, 100)]  # una lectura al inicio y otra al final: gran hueco

    post = outcome_for(*gappy).summary(Window.POST, S.SENSOR)

    assert post.n == 2 and post.stats_allowed is False
    assert (
        post.maximum is None and post.minimum is None
    )  # no se muestran estadísticos sin cobertura


def test_sensor_statistics_are_available_with_enough_coverage():
    post = outcome_for(*sensor_run(-60, 180, 15, 120)).summary(Window.POST, S.SENSOR)

    assert post.stats_allowed is True and post.coverage >= 0.7 and post.maximum is not None
