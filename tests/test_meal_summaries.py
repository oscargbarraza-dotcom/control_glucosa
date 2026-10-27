"""Indicadores de Alimentación: conteos por tipo, día, horario y alimento, y promedios por día."""

import dataclasses
from datetime import date

import pytest

from glucosa.analytics.meal_summaries import (
    MIN_MEALS_FOR_SUMMARY,
    food_ranking,
    hour_histogram,
    meals_by_day,
    most_common_quantity,
    summarize_meals,
    time_of_day_by_type,
    type_counts,
    weekday_counts,
)
from glucosa.analytics.meal_view import meal_views
from glucosa.models.records import MealType
from tests.meal_helpers import WEEK, meal, period, sample_meals


def views(records=None):
    return meal_views(sample_meals() if records is None else records)


# ----------------------------------------------------------------- resumen general
def test_totals_days_and_per_day_averages_use_separate_labelled_denominators():
    summary = summarize_meals(views(), period(*WEEK))

    assert summary.meals == 7
    assert summary.days_with_records == 3  # días 20, 22 y 25
    assert summary.days_in_period == 7
    assert summary.meals_per_active_day == pytest.approx(7 / 3)
    assert summary.meals_per_period_day == pytest.approx(1.0)
    assert (summary.min_per_active_day, summary.max_per_active_day) == (2, 3)
    assert summary.median_per_active_day == 2


def test_days_since_first_record_does_not_count_days_before_the_sync_started():
    summary = summarize_meals(views(), period(date(2026, 9, 21), date(2026, 10, 26)))

    assert summary.days_in_period == 36
    assert summary.first_record_day == date(2026, 10, 20)
    assert summary.days_since_first_record == 7  # del 20 al 26
    assert summary.meals_per_since_first_record_day == pytest.approx(1.0)
    assert summary.meals_per_period_day == pytest.approx(7 / 36)


def test_items_per_meal_and_meals_without_items():
    summary = summarize_meals(views(), period(*WEEK))

    assert summary.items_total == 10
    assert summary.items_per_meal_mean == pytest.approx(10 / 7)
    assert summary.items_per_meal_median == 1
    assert summary.meals_without_items == 1


def test_meals_with_unknown_type_are_counted_apart():
    summary = summarize_meals(views(), period(*WEEK))

    assert summary.meals_with_unknown_type == 1


def test_an_empty_period_has_no_averages_instead_of_zeros():
    summary = summarize_meals([], period(*WEEK))

    assert summary.meals == 0 and summary.days_with_records == 0
    assert summary.days_in_period == 7
    assert summary.meals_per_active_day is None and summary.meals_per_period_day == 0.0
    assert summary.items_per_meal_mean is None and summary.median_per_active_day is None
    assert summary.first_record_day is None and summary.days_since_first_record is None


def test_only_meals_inside_the_period_are_summarized():
    summary = summarize_meals(views(), period(date(2026, 10, 21), date(2026, 10, 24)))

    assert summary.meals == 2 and summary.days_with_records == 1


def test_summary_does_not_mutate_its_input():
    data = views()
    before = list(data)
    summarize_meals(data, period(*WEEK))
    assert data == before


# -------------------------------------------------------------------------- tipos
def test_type_counts_follow_the_enum_order_include_zeros_and_unknown_with_shares():
    counts = type_counts(views())

    assert [(c.label, c.meals) for c in counts] == [
        ("Desayuno", 3),
        ("Almuerzo", 2),
        ("Once/Merienda", 0),
        ("Cena", 1),
        ("Otro/Snack", 0),
        ("Tipo desconocido", 1),
    ]
    assert sum(c.meals for c in counts) == 7
    assert counts[0].share == pytest.approx(3 / 7)
    assert counts[2].share == 0.0


def test_type_counts_of_nothing_have_no_shares():
    assert all(c.meals == 0 and c.share is None for c in type_counts([]))


# --------------------------------------------------------------------------- días
def test_meals_by_day_lists_every_day_of_the_period_with_zeros_for_days_without_records():
    days = meals_by_day(views(), period(*WEEK))

    assert [(d.day.day, d.meals) for d in days] == [
        (20, 3),
        (21, 0),
        (22, 2),
        (23, 0),
        (24, 0),
        (25, 2),
        (26, 0),
    ]
    assert days[1].has_records is False and days[0].has_records is True  # sin registro ≠ sin comer


def test_weekday_counts_and_weekend_share():
    counts = weekday_counts(views())

    assert counts.by_weekday == (0, 3, 0, 2, 0, 0, 2)  # lunes … domingo
    assert counts.weekend == 2 and counts.weekday == 5


# ------------------------------------------------------------------------ horario
def test_hour_histogram_uses_local_hours_and_always_has_24_bins():
    histogram = hour_histogram(views())

    assert len(histogram) == 24
    assert {h.hour: h.meals for h in histogram if h.meals} == {
        8: 2,
        13: 1,
        14: 1,
        20: 1,
        21: 1,
        22: 1,
    }
    assert sum(h.meals for h in histogram) == 7


def test_typical_time_by_type_needs_a_minimum_number_of_meals():
    rows = {r.label: r for r in time_of_day_by_type(views())}

    assert MIN_MEALS_FOR_SUMMARY == 5
    assert rows["Desayuno"].meals == 3 and rows["Desayuno"].sufficient is False
    assert rows["Desayuno"].median_minute is None  # 3 < 5: «datos insuficientes»


def test_typical_time_by_type_with_enough_meals_is_the_median_of_the_declared_times():
    lunches = [
        meal(f"l{i}", f"2026-10-2{i}T{hour:02d}:{minute:02d}", MealType.LUNCH)
        for i, (hour, minute) in enumerate([(13, 0), (13, 30), (14, 0), (14, 30), (15, 0)])
    ]

    (row,) = [r for r in time_of_day_by_type(views(lunches)) if r.type is MealType.LUNCH]

    assert row.sufficient and row.median_minute == 14 * 60
    assert (row.earliest_minute, row.latest_minute) == (13 * 60, 15 * 60)


def test_typical_time_threshold_is_configurable():
    rows = {r.label: r for r in time_of_day_by_type(views(), min_meals=2)}

    assert rows["Almuerzo"].median_minute == 13 * 60 + 45
    assert rows["Cena"].sufficient is False  # solo 1


def test_typical_time_does_not_break_for_meals_around_midnight():
    dinners = [
        meal(f"d{i}", f"2026-10-2{i}T{hhmm}", MealType.DINNER)
        for i, hhmm in enumerate(["23:50", "00:10", "23:55", "00:05"])
    ]

    (row,) = [
        r for r in time_of_day_by_type(views(dinners), min_meals=2) if r.type is MealType.DINNER
    ]

    assert row.median_minute in (0, 1439)  # medianoche, no las 12:00 de un promedio lineal


def test_types_without_meals_have_no_typical_time():
    rows = time_of_day_by_type(views(), min_meals=1)
    snack = next(r for r in rows if r.type is MealType.SNACK)

    assert snack.meals == 0 and snack.median_minute is None


# ---------------------------------------------------------------------- alimentos
def test_ranking_counts_meals_containing_each_food_by_normalized_name():
    ranking = food_ranking(views())

    top = ranking[0]
    assert (top.normalized, top.meals, top.occurrences) == ("pan", 4, 4)
    assert top.display_name == "Pan"  # la escritura más frecuente («Pan» 3 veces, «pan» 1)
    assert top.share_of_meals == pytest.approx(4 / 7)
    assert len(ranking) == 7  # pan, arroz, cafe, ensalada, huevo, palta, pollo


def test_ranking_ties_are_ordered_alphabetically_for_a_stable_result():
    ranking = food_ranking(views())

    assert [r.normalized for r in ranking[1:]] == [
        "arroz",
        "cafe",
        "ensalada",
        "huevo",
        "palta",
        "pollo",
    ]


def test_ranking_does_not_merge_different_foods_or_change_the_original_spelling():
    ranking = food_ranking(
        views(
            [
                meal(
                    "a", "2026-10-20T08:00", MealType.BREAKFAST, [("Huevo", "1"), ("Huevos", "2")]
                ),
                meal("b", "2026-10-21T08:00", MealType.BREAKFAST, [("HUEVO", "1")]),
            ]
        )
    )

    assert {r.normalized: r.meals for r in ranking} == {"huevo": 2, "huevos": 1}
    assert next(r for r in ranking if r.normalized == "huevo").display_name in {"Huevo", "HUEVO"}


def test_a_food_repeated_inside_one_meal_counts_one_meal_and_two_occurrences():
    ranking = food_ranking(
        views([meal("a", "2026-10-20T08:00", MealType.LUNCH, [("Pan", "1"), ("pan", "2")])])
    )

    (row,) = ranking
    assert (row.meals, row.occurrences) == (1, 2)


def test_ranking_top_limit_and_summary_of_the_long_tail():
    ranking = food_ranking(views(), top=3)

    assert len(ranking) == 3 and ranking[0].normalized == "pan"


def test_distinct_foods_and_foods_seen_once():
    from glucosa.analytics.meal_summaries import food_diversity

    diversity = food_diversity(views())

    assert diversity.distinct_foods == 7
    assert diversity.seen_once == 6
    assert diversity.items == 10


def test_ranking_of_no_meals_is_empty():
    assert food_ranking([]) == []


def test_most_common_quantity_returns_the_original_text_and_its_count():
    quantity = most_common_quantity(views(), "pan")

    assert quantity == ("2 rebanadas", 2)
    assert most_common_quantity(views(), "no-existe") is None


def test_quantities_are_free_text_and_are_never_added_up():
    fields = {f.name for f in dataclasses.fields(food_ranking(views())[0])}

    assert not any(name in fields for name in ("total_quantity", "sum_quantity", "quantity_total"))
    # «150 g», «1 tz» y «1/2» son incompatibles: ningún resumen numérico de cantidades.
    summary_fields = {f.name for f in dataclasses.fields(summarize_meals(views(), period(*WEEK)))}
    assert not any("quantity" in name for name in summary_fields)
