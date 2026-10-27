"""Disponibilidad y cobertura del sensor por comida: export desactualizado ≠ huecos ≠ sin mediciones."""

import pytest

from glucosa.analytics.meal_glucose import (
    AssociationParams,
    Availability,
    Window,
    associate_meals,
    availability_label,
    coverage_counts,
    export_notice,
)
from glucosa.analytics.meal_readings import ReadingSource as S
from tests.meal_glucose_helpers import (
    NOW,
    at,
    inputs,
    manual,
    meals,
    sensor,
    sensor_run,
)


def run(specs, *readings, now=NOW, params=None):
    return associate_meals(meals(*specs), inputs(*readings), now, params or AssociationParams())


def post(association, index=0, source=S.SENSOR):
    return association.meals[index].summary(Window.POST, source)


# ------------------------------------------------------------------ cobertura suficiente
def test_a_continuous_sensor_run_has_sufficient_coverage_with_the_real_percentage():
    summary = post(run([("a", 0)], *sensor_run(-120, 300)))

    assert summary.availability is Availability.SUFFICIENT
    assert summary.coverage == pytest.approx(1.0) and summary.stats_allowed is True


def test_there_is_no_complete_availability_state_and_the_label_shows_the_real_percentage():
    assert "COMPLETE" not in Availability.__members__
    summary = post(run([("a", 0)], *sensor_run(-120, 300)))

    label = availability_label(summary)
    assert "100 %" in label and "suficiente" in label.lower() and "completo" not in label.lower()


def test_the_coverage_threshold_is_inclusive_and_configurable():
    readings = sensor_run(-120, 60) + sensor_run(120, 300)  # hueco de 60 a 120
    association = run([("a", 0)], *readings)
    coverage = post(association).coverage
    assert 0.0 < coverage < 1.0

    at_threshold = run([("a", 0)], *readings, params=AssociationParams(min_coverage=coverage))
    above = run([("a", 0)], *readings, params=AssociationParams(min_coverage=coverage + 0.001))

    assert (
        post(at_threshold).stats_allowed is True
        and post(at_threshold).availability is Availability.SUFFICIENT
    )
    assert post(above).stats_allowed is False and post(above).availability is Availability.GAPS


def test_the_default_minimum_coverage_is_70_percent():
    assert AssociationParams().min_coverage == 0.70


# ------------------------------------------------------------------------- huecos reales
def test_gaps_inside_the_export_are_labelled_gaps_with_their_coverage_and_no_statistics():
    readings = sensor_run(-120, 20) + sensor_run(170, 300)  # solo ≈ 25 % de la ventana posterior

    summary = post(run([("a", 0)], *readings))

    assert summary.availability is Availability.GAPS
    assert summary.coverage < 0.7 and summary.stats_allowed is False
    assert summary.maximum is None and summary.n >= 1  # las lecturas se listan, sin estadísticos


# ---------------------------------------------------------------- export desactualizado
def test_a_window_after_the_end_of_the_export_is_outdated_not_a_gap():
    summary = post(run([("a", 400)], *sensor_run(-120, 300)))

    assert summary.availability is Availability.EXPORT_OUTDATED
    assert summary.n == 0 and summary.coverage == 0.0 and summary.stats_allowed is False


def test_a_window_before_the_export_starts_is_reported_as_before_the_export():
    summary = post(run([("a", -600)], *sensor_run(0, 300)))

    assert summary.availability is Availability.BEFORE_EXPORT


def test_a_window_crossing_the_end_of_the_export_is_partial_and_reports_both_coverages():
    summary = post(run([("a", 0)], *sensor_run(-120, 90)))  # el export termina en +90

    assert summary.availability is Availability.PARTIAL_EXPORT
    assert summary.coverage < 0.7  # contra la ventana completa
    assert summary.coverage_within_export > summary.coverage  # contra la parte que el export abarca
    assert summary.stats_allowed is False


def test_a_partial_window_still_allows_statistics_if_the_whole_window_reaches_the_threshold():
    summary = post(run([("a", 0)], *sensor_run(-120, 170)))  # termina en +170 de 180

    assert summary.availability is Availability.PARTIAL_EXPORT
    assert summary.coverage >= 0.7 and summary.stats_allowed is True


def test_without_any_sensor_data_the_state_is_no_sensor_data():
    summary = post(run([("a", 0)], manual(30)))

    assert summary.availability is Availability.NO_SENSOR_DATA and summary.coverage is None


# -------------------------------------------------------------------------- manuales
def test_manual_availability_distinguishes_present_from_absent():
    association = run([("a", 0)], manual(30), manual(-20))

    assert post(association, source=S.MANUAL).availability is Availability.PRESENT
    assert association.meals[0].summary(Window.AT, S.MANUAL).availability is Availability.ABSENT
    assert post(association, source=S.MANUAL).n == 1


def test_a_window_with_no_reading_from_any_source_is_reported_as_no_measurements():
    association = run([("a", 0)], manual(500))

    outcome = association.meals[0]
    assert outcome.any_readings[Window.POST] is False and outcome.any_readings[Window.PRE] is False
    assert run([("a", 0)], manual(30)).meals[0].any_readings[Window.POST] is True


def test_manual_only_windows_are_not_confused_with_missing_sensor_data():
    summary = run([("a", 0)], manual(30), *sensor_run(500, 600)).meals[0]

    assert summary.summary(Window.POST, S.MANUAL).availability is Availability.PRESENT
    assert summary.summary(Window.POST, S.SENSOR).availability is Availability.BEFORE_EXPORT


# ------------------------------------------------------------------ ventana completa
def test_a_window_that_is_still_open_is_marked_incomplete():
    association = run([("a", 0)], manual(30), now=at(100))

    outcome = association.meals[0]
    assert outcome.summary(Window.POST, S.MANUAL).complete is False  # +180 aún no llega
    assert outcome.summary(Window.PRE, S.MANUAL).complete is True


# ----------------------------------------------------- aviso de comidas tras el export
def test_the_notice_counts_meals_after_the_export_and_those_that_cross_its_end():
    association = run(
        [("old", 0), ("crossing", 300), ("after", 600), ("after2", 800)],
        *sensor_run(-120, 405),
    )

    notice = export_notice(association)

    assert notice.has_export is True
    assert (notice.meals_after_export, notice.meals_crossing_export_end) == (2, 1)
    assert notice.export_end == at(405) and notice.first_meal_after == at(600)


def test_no_notice_is_needed_when_the_export_covers_every_meal():
    notice = export_notice(run([("a", 0)], *sensor_run(-120, 405)))

    assert notice.meals_after_export == 0 and notice.meals_crossing_export_end == 0
    assert notice.needs_attention is False


def test_the_notice_flags_the_absence_of_any_export():
    notice = export_notice(run([("a", 0)], manual(10)))

    assert notice.has_export is False and notice.needs_attention is True


def test_a_meal_that_started_before_the_export_begins_is_not_counted_as_after():
    notice = export_notice(run([("early", -600)], *sensor_run(0, 100)))

    assert notice.meals_after_export == 0


# ---------------------------------------------------------------- cobertura por fuente
def test_coverage_counts_report_meals_with_previous_posterior_and_both_per_source():
    association = run(
        [("a", 0), ("b", 1000)],
        manual(-30),
        manual(60),
        manual(1060),
    )

    counts = coverage_counts(association)[S.MANUAL]

    assert (counts.meals, counts.with_pre, counts.with_post, counts.with_both) == (2, 1, 2, 1)


def test_sensor_coverage_counts_distinguish_any_reading_from_sufficient_coverage():
    association = run([("a", 0)], sensor(-30), sensor(60))  # lecturas sueltas: cobertura baja

    counts = coverage_counts(association)[S.SENSOR]

    assert counts.with_post == 1 and counts.sufficient_post == 0
