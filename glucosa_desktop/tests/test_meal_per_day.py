"""Comidas por día: tres denominadores distintos, bien rotulados.

Principal: «Comidas por día con registros». Secundarios: «… calendario del período» y
«… desde el primer registro». Un día sin registro NO es un día sin comer.
"""

from datetime import date

import pytest

from glucosa.analytics.meal_summaries import (
    PERIOD_PER_DAY_LABEL,
    PRIMARY_PER_DAY_LABEL,
    SINCE_FIRST_PER_DAY_LABEL,
    per_day_indicators,
    summarize_meals,
)
from glucosa.analytics.meal_view import meal_views
from glucosa.models.records import MealType
from tests.meal_helpers import meal, period, sample_meals


def views(records=None):
    return meal_views(sample_meals() if records is None else records)


def by_label(summary):
    return {i.label: i for i in per_day_indicators(summary)}


# --------------------------------------------------------------- rotulado y jerarquía
def test_the_primary_indicator_is_meals_per_day_with_records_and_comes_first():
    indicators = per_day_indicators(
        summarize_meals(views(), period(date(2026, 10, 20), date(2026, 10, 26)))
    )

    assert [i.label for i in indicators] == [
        PRIMARY_PER_DAY_LABEL,
        PERIOD_PER_DAY_LABEL,
        SINCE_FIRST_PER_DAY_LABEL,
    ]
    assert [i.primary for i in indicators] == [True, False, False]
    assert PRIMARY_PER_DAY_LABEL == "Comidas por día con registros"
    assert "calendario" in PERIOD_PER_DAY_LABEL and "primer registro" in SINCE_FIRST_PER_DAY_LABEL


def test_each_indicator_reports_the_number_of_days_it_divides_by():
    summary = summarize_meals(views(), period(date(2026, 10, 15), date(2026, 10, 26)))
    indicators = by_label(summary)

    assert indicators[PRIMARY_PER_DAY_LABEL].days == summary.days_with_records == 3
    assert indicators[PERIOD_PER_DAY_LABEL].days == summary.days_in_period == 12
    assert indicators[SINCE_FIRST_PER_DAY_LABEL].days == summary.days_since_first_record == 7


# ----------------------------------------------------------------------- escenarios
def test_a_period_that_starts_on_the_first_record_has_equal_calendar_and_since_first_denominators():
    summary = summarize_meals(views(), period(date(2026, 10, 20), date(2026, 10, 26)))

    assert summary.days_in_period == summary.days_since_first_record == 7
    assert summary.meals_per_period_day == pytest.approx(summary.meals_per_since_first_record_day)
    assert summary.meals_per_active_day == pytest.approx(7 / 3)  # 20, 22 y 25


def test_a_period_that_includes_the_first_record_mid_period_does_not_count_days_before_it():
    summary = summarize_meals(views(), period(date(2026, 10, 15), date(2026, 10, 26)))

    assert summary.days_in_period == 12 and summary.days_since_first_record == 7
    assert summary.meals_per_period_day == pytest.approx(7 / 12)
    assert summary.meals_per_since_first_record_day == pytest.approx(1.0)
    assert summary.meals_per_active_day == pytest.approx(7 / 3)
    note = by_label(summary)[PERIOD_PER_DAY_LABEL].note
    assert note and "anteriores al primer registro" in note


def test_intermediate_days_without_meals_lower_the_secondary_averages_but_not_the_primary():
    # Días con comidas: 20, 22 y 25. Los días 21, 23, 24 y 26 no tienen registro.
    summary = summarize_meals(views(), period(date(2026, 10, 20), date(2026, 10, 26)))

    assert summary.days_with_records == 3
    assert summary.meals_per_active_day == pytest.approx(7 / 3)  # ignora los días sin registro
    assert summary.meals_per_period_day == pytest.approx(1.0)  # los cuenta como días del período


def test_trailing_days_without_records_after_the_last_meal_are_counted_in_both_secondary_averages():
    summary = summarize_meals(views(), period(date(2026, 10, 20), date(2026, 10, 30)))

    assert summary.days_in_period == 11 and summary.days_since_first_record == 11
    assert summary.meals_per_since_first_record_day == pytest.approx(7 / 11)
    assert summary.meals_per_active_day == pytest.approx(7 / 3)  # no cambia


def test_a_period_that_starts_after_the_first_record_uses_only_its_own_days():
    summary = summarize_meals(views(), period(date(2026, 10, 22), date(2026, 10, 26)))

    assert summary.first_record_day == date(2026, 10, 20)  # anterior al período
    assert summary.days_in_period == summary.days_since_first_record == 5
    assert summary.meals == 4 and summary.days_with_records == 2
    assert summary.meals_per_period_day == pytest.approx(4 / 5)


def test_a_period_before_the_first_record_has_no_synced_days_and_says_so():
    summary = summarize_meals(views(), period(date(2026, 10, 1), date(2026, 10, 10)))

    assert summary.meals == 0 and summary.days_in_period == 10
    assert summary.days_since_first_record == 0
    assert summary.meals_per_since_first_record_day is None and summary.meals_per_active_day is None
    indicators = by_label(summary)
    assert indicators[PERIOD_PER_DAY_LABEL].value is None  # no es «0 comidas por día»: no hay datos
    assert (
        indicators[PERIOD_PER_DAY_LABEL].note
        and "antes del primer registro" in indicators[PERIOD_PER_DAY_LABEL].note
    )
    assert indicators[SINCE_FIRST_PER_DAY_LABEL].value is None
    assert indicators[PRIMARY_PER_DAY_LABEL].value is None


def test_a_period_after_the_last_record_has_zero_meals_per_calendar_day():
    summary = summarize_meals(views(), period(date(2026, 10, 28), date(2026, 10, 30)))

    assert summary.meals == 0 and summary.days_with_records == 0
    assert summary.days_since_first_record == 3
    assert summary.meals_per_period_day == 0.0 and summary.meals_per_since_first_record_day == 0.0
    assert summary.meals_per_active_day is None  # sin días con registro no hay promedio principal
    assert by_label(summary)[PERIOD_PER_DAY_LABEL].value == 0.0


def test_with_no_meals_at_all_every_indicator_is_undefined_not_zero():
    summary = summarize_meals([], period(date(2026, 10, 20), date(2026, 10, 26)))

    assert all(i.value is None for i in per_day_indicators(summary))
    assert by_label(summary)[PERIOD_PER_DAY_LABEL].note  # explica que aún no hay comidas


def test_a_single_day_with_one_meal_gives_one_everywhere():
    only = meal_views([meal("a", "2026-10-20T08:00", MealType.BREAKFAST, [("Pan", "1")])])

    summary = summarize_meals(only, period(date(2026, 10, 20), date(2026, 10, 20)))

    assert [i.value for i in per_day_indicators(summary)] == [1.0, 1.0, 1.0]


def test_a_period_that_ends_before_the_first_record_never_reports_negative_days():
    summary = summarize_meals(views(), period(date(2026, 9, 1), date(2026, 9, 2)))

    assert summary.days_since_first_record == 0
    assert all(i.days is None or i.days >= 0 for i in per_day_indicators(summary))


def test_the_primary_value_is_always_meals_divided_by_days_with_records():
    for first, last in [
        (date(2026, 10, 20), date(2026, 10, 26)),
        (date(2026, 10, 15), date(2026, 10, 26)),
        (date(2026, 10, 22), date(2026, 10, 26)),
    ]:
        summary = summarize_meals(views(), period(first, last))
        primary = by_label(summary)[PRIMARY_PER_DAY_LABEL]
        assert primary.value == pytest.approx(summary.meals / summary.days_with_records)
        assert primary.days == summary.days_with_records


def test_indicators_are_a_pure_function_of_the_summary():
    summary = summarize_meals(views(), period(date(2026, 10, 20), date(2026, 10, 26)))

    assert per_day_indicators(summary) == per_day_indicators(summary)
