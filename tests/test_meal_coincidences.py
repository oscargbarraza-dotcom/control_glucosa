"""Coincidencias manual ↔ escaneo y manual ↔ historial: solo marcado, 1 a 1, sin borrar nada."""

import dataclasses
import random

import pytest

from glucosa.analytics.meal_glucose import Window, associate_meals, unique_reading_count
from glucosa.analytics.meal_readings import (
    CoincidenceKind,
    find_coincidences,
)
from glucosa.analytics.meal_readings import ReadingSource as S
from tests.meal_glucose_helpers import NOW, at, inputs, manual, meal_at, scan, sensor


def kinds(found):
    return sorted((c.kind.value, c.manual_id, c.other_id) for c in found)


# ------------------------------------------------------------------------ manual ↔ escaneo
def test_a_manual_and_a_scan_within_10_minutes_and_equal_value_are_a_probable_coincidence():
    m, s = manual(0, 120, ident="m"), scan(8, 120, ident="s")

    found = find_coincidences([m], [s], [])

    assert kinds(found) == [("manual_scan", "m", "s")]
    assert found[0].delta_seconds == 8 * 60


def test_the_scan_tolerance_is_10_minutes_inclusive():
    assert find_coincidences([manual(0, 120)], [scan(10, 120)], [])
    assert not find_coincidences([manual(0, 120)], [scan(10 + 1 / 60, 120)], [])
    assert find_coincidences([manual(0, 120)], [scan(-10, 120)], [])


def test_a_different_value_is_never_a_coincidence():
    assert not find_coincidences([manual(0, 120)], [scan(2, 121)], [])


# ----------------------------------------------------------------------- manual ↔ historial
def test_a_manual_and_a_history_reading_in_the_same_minute_with_equal_value_coincide():
    m, h = manual(0, 120, ident="m"), sensor(0.5, 120, ident="h")  # 30 s más tarde, mismo minuto

    assert kinds(find_coincidences([m], [], [h])) == [("manual_history", "m", "h")]


def test_history_coincidences_need_the_same_minute_not_just_proximity():
    assert not find_coincidences([manual(0, 120)], [], [sensor(1.1, 120)])
    assert not find_coincidences([manual(0, 120)], [], [sensor(-0.1, 120)])  # minuto anterior
    assert not find_coincidences([manual(0, 120)], [], [sensor(0, 125)])


# ----------------------------------------------------------------------------- uno a uno
def test_the_assignment_is_one_to_one_nearest_first_and_earlier_on_ties():
    s = scan(0, 120, ident="s")
    near, far = manual(2, 120, ident="near"), manual(-6, 120, ident="far")

    found = find_coincidences([far, near], [s], [])

    assert kinds(found) == [("manual_scan", "near", "s")]  # el escaneo se asigna una sola vez


def test_two_manuals_equidistant_from_one_scan_pick_the_earlier_manual():
    s = scan(0, 120, ident="s")
    early, late = manual(-4, 120, ident="early"), manual(4, 120, ident="late")

    assert kinds(find_coincidences([late, early], [s], [])) == [("manual_scan", "early", "s")]


def test_each_manual_is_matched_to_at_most_one_scan():
    m = manual(0, 120, ident="m")
    a, b = scan(-3, 120, ident="a"), scan(3, 120, ident="b")

    assert kinds(find_coincidences([m], [b, a], [])) == [("manual_scan", "m", "a")]  # la anterior


def test_chains_of_matches_are_not_created():
    m1, m2 = manual(0, 120, ident="m1"), manual(9, 120, ident="m2")
    s1, s2 = scan(5, 120, ident="s1"), scan(14, 120, ident="s2")

    found = find_coincidences([m1, m2], [s1, s2], [])

    assert len({c.manual_id for c in found}) == len(found)
    assert len({c.other_id for c in found}) == len(found)


def test_a_manual_can_coincide_with_one_scan_and_one_history_reading():
    m = manual(0, 120, ident="m")

    found = find_coincidences([m], [scan(6, 120, ident="s")], [sensor(0, 120, ident="h")])

    assert kinds(found) == [("manual_history", "m", "h"), ("manual_scan", "m", "s")]


def test_coincidences_do_not_depend_on_the_order_of_the_inputs():
    manuals = [manual(m, 120, ident=f"m{m}") for m in (0, 4, 9, 30)]
    scans = [scan(m, 120, ident=f"s{m}") for m in (2, 6, 12, 31)]
    reference = find_coincidences(manuals, scans, [])
    rng = random.Random(3)
    for _ in range(5):
        rng.shuffle(manuals)
        rng.shuffle(scans)
        assert find_coincidences(manuals, scans, []) == reference


# --------------------------------------------------------------- no destructivo / «probable»
def test_coincidences_are_labelled_probable_and_never_as_proven_identity():
    (found,) = find_coincidences([manual(0, 120)], [scan(1, 120)], [])

    assert found.certainty == "probable"
    names = {f.name for f in dataclasses.fields(found)}
    assert not names & {"identical", "duplicate", "same_reading", "confirmed"}
    assert CoincidenceKind.MANUAL_SCAN.value == "manual_scan"


def test_all_original_records_are_preserved_inside_the_association():
    m, h, sc = manual(0, 120), sensor(0, 120), scan(3, 120)
    data = inputs(m, h, sc)

    association = associate_meals([meal_at("m1")], data, NOW)

    assert data.manual == (m,) and data.sensor == (h,) and data.scans == (sc,)
    outcome = association.meals[0]
    assert outcome.summary(Window.AT, S.SENSOR).n == 1  # la lectura del sensor sigue en su serie
    assert association.coincidences  # y además queda marcada


def test_association_exposes_the_coincidence_map_by_reading_id():
    m, h = manual(0, 120, ident="m"), sensor(0, 120, ident="h")

    association = associate_meals([meal_at("m1")], inputs(m, h), NOW)

    assert association.equivalent_manual_of("h") == "m"
    assert association.equivalent_manual_of("m") is None


# ------------------------------------------------------------------- lecturas únicas
def test_unique_count_does_not_count_a_probable_equivalent_twice():
    m, h, other = manual(0, 120), sensor(0, 120), sensor(30, 150)
    association = associate_meals([meal_at("m1")], inputs(m, h, other), NOW)

    outcome = association.meals[0]
    assert outcome.summary(Window.AT, S.MANUAL).n + outcome.summary(Window.AT, S.SENSOR).n == 2
    assert (
        unique_reading_count(outcome, Window.AT, association) == 1
    )  # la del sensor equivale a la manual
    assert unique_reading_count(outcome, Window.POST, association) == 1


def test_unique_count_keeps_every_reading_when_there_are_no_coincidences():
    association = associate_meals([meal_at("m1")], inputs(manual(0, 120), sensor(0, 121)), NOW)

    assert unique_reading_count(association.meals[0], Window.AT, association) == 2


def test_scans_are_never_part_of_the_unique_count():
    association = associate_meals([meal_at("m1")], inputs(manual(0, 120), scan(1, 120)), NOW)

    assert unique_reading_count(association.meals[0], Window.AT, association) == 1


@pytest.mark.parametrize("window", list(Window))
def test_unique_count_is_zero_for_empty_windows(window):
    association = associate_meals([meal_at("m1")], inputs(), NOW)

    assert unique_reading_count(association.meals[0], window, association) == 0


def test_scan_coincidences_are_listed_even_when_the_scan_is_outside_every_window():
    association = associate_meals([meal_at("m1")], inputs(manual(500, 120), scan(502, 120)), NOW)

    assert len(association.coincidences) == 1 and at(500)
