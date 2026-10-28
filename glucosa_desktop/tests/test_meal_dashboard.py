"""Lógica pura de la página Alimentación: filtros de visualización y KPI de hitos (D4)."""

from datetime import timedelta

import pytest

from glucosa.analytics.meal_dashboard import (
    AVAILABILITY_LABELS,
    AvailabilityFilter,
    apply_visualization_filters,
    has_readings,
    milestone_kpis,
    select_association,
)
from glucosa.analytics.meal_glucose import AssociationParams, Window, associate_meals
from glucosa.analytics.meal_milestones import MilestoneParams
from glucosa.analytics.meal_readings import ReadingSource as S
from tests.meal_glucose_helpers import NOW, T0, imported, inputs, manual, meals, sensor, sensor_run

ALL_SOURCES = frozenset({S.MANUAL, S.IMPORTED, S.SENSOR})


def association(specs, *readings, now=NOW, tolerance=10):
    params = AssociationParams(milestones=MilestoneParams(tolerance_minutes=tolerance))
    return associate_meals(meals(*specs), inputs(*readings), now, params)


def uuids(outcomes):
    return [o.uuid for o in outcomes]


# --------------------------------------------------------------- disponibilidad
def test_has_readings_only_counts_the_selected_sources():
    result = association([("a", 0)], manual(-30), sensor(30)).meals[0]

    assert has_readings(result, Window.PRE, {S.MANUAL}) is True
    assert has_readings(result, Window.PRE, {S.SENSOR}) is False
    assert has_readings(result, Window.POST, {S.MANUAL, S.SENSOR}) is True
    assert has_readings(result, Window.POST, set()) is False


@pytest.fixture
def mixed():
    return association(
        [("pre_only", 0), ("post_only", 1000), ("both", 2000), ("none", 3000)],
        manual(-30),
        manual(1060),
        manual(1960),
        manual(2060),
        manual(5000),
    )


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        (AvailabilityFilter.ALL, ["pre_only", "post_only", "both", "none"]),
        (AvailabilityFilter.WITH_PRE, ["pre_only", "both"]),
        (AvailabilityFilter.WITH_POST, ["post_only", "both"]),
        (AvailabilityFilter.WITH_BOTH, ["both"]),
        (AvailabilityFilter.WITHOUT_PRE, ["post_only", "none"]),
        (AvailabilityFilter.WITHOUT_POST, ["pre_only", "none"]),
        (AvailabilityFilter.WITHOUT_ANY, ["none"]),
    ],
)
def test_the_availability_filter_uses_the_selected_sources(mixed, choice, expected):
    shown = apply_visualization_filters(mixed.meals, choice, False, ALL_SOURCES)

    assert uuids(shown) == expected


def test_without_any_means_no_reading_in_any_window_of_the_selected_sources():
    result = association([("a", 0)], manual(3), sensor(500))  # una lectura «al comer» solo manual

    assert (
        uuids(
            apply_visualization_filters(
                result.meals, AvailabilityFilter.WITHOUT_ANY, False, {S.MANUAL}
            )
        )
        == []
    )
    assert uuids(
        apply_visualization_filters(result.meals, AvailabilityFilter.WITHOUT_ANY, False, {S.SENSOR})
    ) == ["a"]


def test_changing_the_selected_sources_changes_what_availability_means(mixed):
    manual_only = apply_visualization_filters(
        mixed.meals, AvailabilityFilter.WITH_PRE, False, {S.MANUAL}
    )
    sensor_only = apply_visualization_filters(
        mixed.meals, AvailabilityFilter.WITH_PRE, False, {S.SENSOR}
    )

    assert uuids(manual_only) == ["pre_only", "both"] and sensor_only == []


def test_the_isolated_only_filter_keeps_meals_without_neighbors():
    result = association([("a", 0), ("b", 60), ("c", 1000)])

    kept = apply_visualization_filters(result.meals, AvailabilityFilter.ALL, True, ALL_SOURCES)

    assert uuids(kept) == ["c"]


def test_filters_combine_and_keep_the_chronological_order():
    result = association([("a", 0), ("b", 60), ("c", 1000)], manual(-10), manual(1050))

    kept = apply_visualization_filters(result.meals, AvailabilityFilter.WITH_PRE, True, ALL_SOURCES)

    assert kept == []  # c es la única aislada, pero su lectura está en la ventana posterior
    assert uuids(
        apply_visualization_filters(result.meals, AvailabilityFilter.ALL, False, ALL_SOURCES)
    ) == ["a", "b", "c"]


def test_meals_without_glucose_stay_visible_unless_the_user_filters_them_out(mixed):
    assert "none" in uuids(
        apply_visualization_filters(mixed.meals, AvailabilityFilter.ALL, False, ALL_SOURCES)
    )


def test_every_availability_option_has_a_spanish_label():
    assert set(AVAILABILITY_LABELS) == set(AvailabilityFilter)
    assert all(label for label in AVAILABILITY_LABELS.values())


def test_the_filters_do_not_modify_the_association(mixed):
    before = mixed.meals
    apply_visualization_filters(mixed.meals, AvailabilityFilter.WITH_BOTH, True, ALL_SOURCES)

    assert mixed.meals == before


# ------------------------------------------------------------------- KPI de hitos
def test_milestone_kpis_separate_eligible_measured_and_pending_meals():
    now = T0 + timedelta(minutes=70)  # +60 de «a» ya ocurrió; +90 y todo lo de «b» no
    result = association([("a", 0), ("b", 50)], manual(61), now=now)

    kpis = milestone_kpis(result.meals)

    sixty, ninety = kpis[60], kpis[90]
    assert (sixty.eligible, sixty.measured, sixty.not_registered, sixty.pending) == (1, 1, 0, 1)
    assert (ninety.eligible, ninety.measured, ninety.not_registered, ninety.pending) == (0, 0, 0, 2)


def test_eligible_excludes_pending_and_equals_measured_plus_not_registered():
    result = association([("a", 0), ("b", 500), ("c", 1000)], manual(60), manual(1500))

    for kpi in milestone_kpis(result.meals).values():
        assert kpi.eligible == kpi.measured + kpi.not_registered
        assert kpi.eligible + kpi.pending == 3


def test_milestone_kpis_count_only_the_selected_source():
    result = association([("a", 0)], manual(60), *sensor_run(-60, 200))

    manual_kpi = milestone_kpis(result.meals, S.MANUAL)[60]
    sensor_kpi = milestone_kpis(result.meals, S.SENSOR)[60]

    assert manual_kpi.measured == 1 and sensor_kpi.measured == 1
    assert milestone_kpis(result.meals, S.IMPORTED)[60].eligible == 0  # no hay importadas


def test_the_kpis_report_the_tolerance_used_and_use_the_given_params():
    wide = association([("a", 0)], manual(75), tolerance=15)
    narrow = association([("a", 0)], manual(75), tolerance=10)

    assert milestone_kpis(wide.meals)[60].tolerance_minutes == 15
    assert milestone_kpis(wide.meals)[60].measured == 1
    assert (
        milestone_kpis(narrow.meals)[60].measured == 0
        and milestone_kpis(narrow.meals)[60].not_registered == 1
    )


def test_a_reading_nearest_to_two_milestones_counts_for_both_without_inventing_compliance():
    result = association([("a", 0)], manual(75), tolerance=20)

    kpis = milestone_kpis(result.meals)

    assert kpis[60].measured == 1 and kpis[90].measured == 1
    assert not any("cumpl" in name or "complian" in name for name in kpis[60].__dataclass_fields__)


def test_kpis_of_an_empty_selection_are_zero():
    kpis = milestone_kpis(())

    assert kpis[60].eligible == kpis[60].pending == kpis[60].measured == 0


def test_imported_not_applicable_is_not_counted_as_eligible():
    result = association([("a", 0)], manual(60))

    assert milestone_kpis(result.meals, S.IMPORTED)[90].eligible == 0


# ------------------------------------------------------------ subconjuntos de la asociación
def test_select_association_keeps_the_selected_meals_and_shared_metadata():
    result = association([("a", 0), ("b", 60), ("c", 1000)], manual(30))

    subset = select_association(result, {"a", "c"})

    assert [m.uuid for m in subset.meals] == ["a", "c"]
    assert subset.export_span == result.export_span and subset.coincidences == result.coincidences
    assert (
        subset.meals[0].neighbors == result.meals[0].neighbors
    )  # la vecindad usa TODAS las comidas


def test_select_association_of_nothing_is_empty():
    assert select_association(association([("a", 0)]), set()).meals == ()


def test_helper_data_for_imported_readings_is_separate():
    result = association([("a", 0)], imported(30))

    assert result.meals[0].summary(Window.POST, S.IMPORTED).n == 1
