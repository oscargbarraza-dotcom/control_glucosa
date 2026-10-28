"""Comidas aisladas, casi simultáneas, con hitos cruzados y lecturas compartidas entre ventanas."""

import pytest

from glucosa.analytics.meal_glucose import Window, associate_meals
from glucosa.analytics.meal_readings import ReadingSource as S
from tests.meal_glucose_helpers import NOW, inputs, manual, meals, sensor


def outcomes(specs, *readings):
    association = associate_meals(meals(*specs), inputs(*readings), NOW)
    return {o.uuid: o for o in association.meals}


# -------------------------------------------------------------------------- aislada
def test_a_meal_with_no_other_meal_in_its_window_is_isolated():
    only = outcomes([("a", 0)])["a"]

    assert only.isolated is True and only.neighbors == () and only.near_simultaneous is False


@pytest.mark.parametrize(
    ("other", "isolated"),
    [(-61, True), (-60, False), (-30, False), (100, False), (180, False), (181, True), (400, True)],
)
def test_isolation_uses_the_minus_60_to_plus_180_range_of_each_meal(other, isolated):
    result = outcomes([("a", 0), ("b", other)])

    assert result["a"].isolated is isolated


def test_neighbors_report_the_other_meal_and_the_signed_separation():
    result = outcomes([("a", 0), ("b", 45), ("c", -20), ("d", 500)])

    assert [(n.uuid, n.minutes) for n in result["a"].neighbors] == [("c", -20.0), ("b", 45.0)]
    assert [(n.uuid, n.minutes) for n in result["b"].neighbors] == [("a", -45.0)]  # c queda a −65
    assert result["d"].neighbors == ()


def test_the_asymmetric_range_means_isolation_is_not_always_mutual():
    result = outcomes([("a", 0), ("b", 120)])

    # b está a +120 de a (dentro de su posterior); a está a −120 de b (fuera de su previa de −60).
    assert result["a"].isolated is False and result["b"].isolated is True


# ----------------------------------------------------------------- casi simultáneas
@pytest.mark.parametrize(
    ("separation", "flag"), [(0, True), (7.6, True), (15, True), (15.01, False), (-15, True)]
)
def test_near_simultaneous_meals_are_flagged_up_to_15_minutes_either_way(separation, flag):
    assert outcomes([("a", 0), ("b", separation)])["a"].near_simultaneous is flag


def test_two_meals_at_the_same_instant_are_each_other_neighbors_with_zero_separation():
    result = outcomes([("a", 0), ("b", 0)])

    assert result["a"].neighbors[0].minutes == 0.0 and result["b"].near_simultaneous is True


# --------------------------------------------------------------------- hitos cruzados
def test_another_meal_before_a_milestone_target_crosses_that_milestone():
    result = outcomes([("a", 0), ("b", 45)])

    assert result["a"].crossed_milestones == {60: ("b",), 90: ("b",)}


def test_a_meal_between_the_two_milestones_crosses_only_the_second():
    result = outcomes([("a", 0), ("b", 75)])

    assert result["a"].crossed_milestones == {60: (), 90: ("b",)}


def test_a_meal_exactly_at_the_target_counts_and_one_after_it_does_not():
    on_target = outcomes([("a", 0), ("b", 60)])["a"].crossed_milestones
    after = outcomes([("a", 0), ("b", 60.02)])["a"].crossed_milestones

    assert on_target[60] == ("b",) and after[60] == ()


def test_a_previous_meal_does_not_cross_the_milestones_of_a_later_one():
    result = outcomes([("a", 0), ("b", 45)])

    assert result["b"].crossed_milestones == {60: (), 90: ()}


# ------------------------------------------------------------- lecturas compartidas
def test_a_reading_in_the_windows_of_two_meals_is_shared_and_neither_window_is_clipped():
    shared = manual(50, 150, ident="shared")  # +50 de a y +20 de b
    result = outcomes([("a", 0), ("b", 30)], shared)

    for uuid in ("a", "b"):
        assert result[uuid].summary(Window.POST, S.MANUAL).n == 1
        assert result[uuid].shared_reading_ids == frozenset({"shared"})


def test_readings_used_by_only_one_meal_are_not_shared():
    result = outcomes([("a", 0), ("b", 500)], manual(20, ident="x"), manual(520, ident="y"))

    assert (
        result["a"].shared_reading_ids == frozenset()
        and result["b"].shared_reading_ids == frozenset()
    )


def test_windows_that_overlap_are_reported_even_when_the_meals_are_not_neighbors():
    result = outcomes([("a", 0), ("b", 200)])  # 200 ≤ 240: sus ventanas se superponen

    assert result["a"].isolated is True  # no hay otra comida dentro de su rango
    assert [o.uuid for o in result["a"].overlapping] == ["b"]
    assert result["a"].overlaps_windows is True


@pytest.mark.parametrize(
    ("separation", "overlaps"), [(239.9, True), (240, True), (240.02, False), (-240, True)]
)
def test_windows_overlap_when_the_meals_are_at_most_240_minutes_apart(separation, overlaps):
    # Con exactamente 240 min la lectura en +180 de una es la de −60 de la otra: se comparte.
    result = outcomes([("a", 0), ("b", separation)])

    assert bool(result["a"].overlapping) is overlaps


def test_nothing_is_silently_clipped_when_meals_are_close():
    readings = [sensor(m) for m in range(-60, 181, 15)]
    result = outcomes([("a", 0), ("b", 20)], *readings)

    assert result["a"].summary(Window.POST, S.SENSOR).n == 12  # (+5,+180]: todas, aunque b exista
    assert (
        result["b"].summary(Window.PRE, S.SENSOR).n == 3
    )  # lecturas en −30, −15 y 0 (relativo a a)
