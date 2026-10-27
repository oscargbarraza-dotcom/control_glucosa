"""Ventanas [−60,−5), [−5,+5] y (+5,+180] min alrededor de la comida, sobre instantes UTC."""

import random
import time
from datetime import UTC, datetime, timedelta

import pytest

from glucosa.analytics.meal_glucose import (
    WINDOW_ORDER,
    Window,
    WindowParams,
    associate_meals,
)
from glucosa.analytics.meal_readings import ReadingSource as S
from glucosa.analytics.meal_view import meal_views
from glucosa.models.records import MealRecord, MealType
from tests.meal_glucose_helpers import NOW, at, inputs, manual, meal_at, meals, scan, sensor


def result_for(readings, minutes=0):
    (outcome,) = associate_meals([meal_at("m1", minutes)], inputs(*readings), NOW).meals
    return outcome


def offsets(summary):
    return [round(r.delta_minutes, 4) for r in summary.readings]


# ------------------------------------------------------------------ límites exactos
@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (-60.01, None),
        (-60.0, Window.PRE),
        (-30.0, Window.PRE),
        (-5.0001, Window.PRE),
        (-5.0, Window.AT),
        (0.0, Window.AT),
        (5.0, Window.AT),
        (5.0001, Window.POST),
        (90.0, Window.POST),
        (180.0, Window.POST),
        (180.0001, None),
    ],
)
def test_each_reading_falls_in_exactly_one_window_with_exact_boundaries(minutes, expected):
    outcome = result_for([manual(minutes)])

    holders = [w for w in WINDOW_ORDER if outcome.summary(w, S.MANUAL).readings]
    assert holders == ([] if expected is None else [expected])


def test_approved_window_parameters_are_the_defaults():
    params = WindowParams()

    assert (
        params.pre_minutes,
        params.at_before_minutes,
        params.at_after_minutes,
        params.post_minutes,
    ) == (
        60,
        5,
        5,
        180,
    )


def test_windows_are_mutually_exclusive_within_a_meal():
    outcome = result_for([manual(m) for m in range(-70, 190, 1)])

    ids = [r.reading.id for w in WINDOW_ORDER for r in outcome.summary(w, S.MANUAL).readings]
    assert len(ids) == len(set(ids))  # ninguna lectura en dos ventanas de la misma comida


def test_every_reading_keeps_its_source_time_and_signed_offset():
    outcome = result_for([manual(-20, 100), sensor(30, 150)])

    pre = outcome.summary(Window.PRE, S.MANUAL).readings[0]
    post = outcome.summary(Window.POST, S.SENSOR).readings[0]
    assert (pre.reading.source, pre.reading.value, pre.reading.instant, pre.delta_minutes) == (
        S.MANUAL,
        100,
        at(-20),
        -20.0,
    )
    assert (post.reading.source, post.reading.instant, post.delta_minutes) == (
        S.SENSOR,
        at(30),
        30.0,
    )


def test_sources_are_never_mixed_inside_a_window_summary():
    outcome = result_for([manual(-20), sensor(-20), sensor(-30)])

    assert [r.reading.source for r in outcome.summary(Window.PRE, S.MANUAL).readings] == [S.MANUAL]
    assert {r.reading.source for r in outcome.summary(Window.PRE, S.SENSOR).readings} == {S.SENSOR}


def test_scans_are_listed_apart_and_never_counted_as_a_source_series():
    outcome = result_for([scan(-20), manual(-20)])

    assert [r.reading.source for r in outcome.scans[Window.PRE]] == [S.SCAN]
    assert outcome.summary(Window.PRE, S.MANUAL).n == 1
    assert (Window.PRE, S.SCAN) not in outcome.summaries


def test_readings_inside_a_window_are_sorted_by_time():
    outcome = result_for([manual(150), manual(10), manual(60)])

    assert offsets(outcome.summary(Window.POST, S.MANUAL)) == [10.0, 60.0, 150.0]


# ------------------------------------------------------------- orden de entrada y mutación
def test_input_order_does_not_change_the_result():
    pool = [manual(m, 100 + m) for m in (-50, -20, -3, 0, 4, 40, 90, 170)] + [
        sensor(m, 90 + m) for m in range(-60, 181, 15)
    ]
    reference = associate_meals(meals(("a", 0), ("b", 70)), inputs(*pool), NOW)
    rng = random.Random(7)

    for _ in range(5):
        shuffled = pool[:]
        rng.shuffle(shuffled)
        assert associate_meals(meals(("b", 70), ("a", 0)), inputs(*shuffled), NOW) == reference


def test_the_inputs_are_not_mutated():
    pool = [manual(-10), sensor(20)]
    data = inputs(*pool)
    before = (data.manual, data.sensor)

    associate_meals(meals(("a", 0)), data, NOW)

    assert (data.manual, data.sensor) == before and pool[0].value == 120


# ------------------------------------------------------- cambios de horario de Chile
def test_a_25_hour_day_uses_real_elapsed_time_not_wall_clock_time():
    # 2026-04-04 24:00 los relojes vuelven a las 23:00: la hora 23:00–24:00 ocurre dos veces.
    base = datetime(2026, 4, 5, 2, 30, tzinfo=UTC)  # 23:30 (1.ª vez, UTC-3)
    record = MealRecord("m", MealType.DINNER, base, None)
    second_pass = datetime(
        2026, 4, 5, 3, 0, tzinfo=UTC
    )  # 23:00 (2.ª vez): en la hora de pared «retrocede»
    data = inputs(manual(30, base=base))
    assert second_pass == at(30, base)

    (outcome,) = associate_meals(meal_views([record]), data, base + timedelta(days=1)).meals

    (found,) = outcome.summary(Window.POST, S.MANUAL).readings
    assert found.delta_minutes == 30.0  # no −30 por la hora de pared


def test_a_23_hour_day_does_not_lose_or_invent_minutes():
    base = datetime(
        2026, 9, 6, 3, 30, tzinfo=UTC
    )  # 23:30 del 5-9 (UTC-4) antes del salto de verano
    record = MealRecord("m", MealType.DINNER, base, None)
    reading_at = manual(40, base=base)  # 01:10 locales (UTC-3): la hora de pared saltó 100 min

    (outcome,) = associate_meals(
        meal_views([record]), inputs(reading_at), base + timedelta(days=1)
    ).meals

    (found,) = outcome.summary(Window.POST, S.MANUAL).readings
    assert found.delta_minutes == 40.0


# ----------------------------------------------------------------------- rendimiento
def test_many_meals_and_readings_are_handled_with_binary_search_speed():
    readings = [sensor(m, 100 + (m % 50)) for m in range(-600, 60 * 24 * 40, 15)]
    many = meals(*[(f"m{i}", i * 300.0) for i in range(300)])
    started = time.perf_counter()

    outcome = associate_meals(many, inputs(*readings), NOW + timedelta(days=60))

    assert len(outcome.meals) == 300 and time.perf_counter() - started < 15
