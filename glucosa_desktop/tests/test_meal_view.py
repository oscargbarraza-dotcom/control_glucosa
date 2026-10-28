"""Vista de comidas (hora local, alimentos normalizados) y filtros de población."""

from datetime import UTC, date, datetime

import pytest

from glucosa.analytics.meal_view import (
    NO_TYPE_LABEL,
    TYPE_LABELS,
    filter_meals,
    meal_views,
)
from glucosa.models.foods import normalize_food_name
from glucosa.models.records import MealItem, MealRecord, MealType
from tests.meal_helpers import WEEK, meal, period, sample_meals


def test_views_keep_every_meal_in_chronological_order_and_do_not_touch_the_records():
    records = list(reversed(sample_meals()))
    snapshot = list(records)

    views = meal_views(records)

    assert [v.uuid for v in views] == ["m1", "m2", "m3", "m4", "m5", "m6", "m7"]
    assert records == snapshot  # la entrada no se muta


def test_view_exposes_local_date_time_weekday_and_declared_type():
    (view,) = meal_views([meal("a", "2026-10-20T13:30", MealType.LUNCH)])

    assert view.local_date == date(2026, 10, 20)
    assert view.minute_of_day == 13 * 60 + 30
    assert view.hour == 13
    assert view.weekday == 1  # martes
    assert view.type is MealType.LUNCH
    assert view.type_label == TYPE_LABELS[MealType.LUNCH]


def test_unknown_type_is_labelled_not_guessed_from_the_hour():
    (view,) = meal_views([meal("a", "2026-10-25T22:30", None)])

    assert view.type is None and view.type_label == NO_TYPE_LABEL


def test_a_breakfast_logged_at_night_stays_a_breakfast():
    (view,) = meal_views([meal("a", "2026-10-25T20:40", MealType.BREAKFAST)])

    assert view.type is MealType.BREAKFAST and view.hour == 20


def test_items_keep_the_original_text_and_add_a_normalized_name():
    (view,) = meal_views(
        [meal("a", "2026-10-20T08:00", MealType.BREAKFAST, [("  Plátano ", "1/2 u")])]
    )

    (item,) = view.items
    assert item.name == "  Plátano " and item.quantity == "1/2 u"  # texto original intacto
    assert item.normalized == normalize_food_name("  Plátano ") == "platano"
    assert view.item_count == 1 and view.normalized_foods == frozenset({"platano"})


def test_local_date_uses_chile_time_across_the_repeated_hour_of_april():
    first = MealRecord("a", MealType.DINNER, datetime(2026, 4, 5, 2, 30, tzinfo=UTC), None)
    second = MealRecord("b", MealType.DINNER, datetime(2026, 4, 5, 3, 0, tzinfo=UTC), None)

    views = meal_views([first, second])

    assert [v.local_date for v in views] == [date(2026, 4, 4), date(2026, 4, 4)]
    assert [v.minute_of_day for v in views] == [23 * 60 + 30, 23 * 60]  # 23:30 y 23:00 (2.ª vez)


def test_a_meal_just_after_local_midnight_belongs_to_the_next_local_day():
    (view,) = meal_views([MealRecord("a", None, datetime(2026, 10, 21, 3, 10, tzinfo=UTC), None)])

    assert view.local_date == date(2026, 10, 21) and view.minute_of_day == 10


def test_a_meal_without_items_has_zero_items_and_no_foods():
    (view,) = meal_views([meal("a", "2026-10-20T08:00", MealType.BREAKFAST, [])])

    assert view.item_count == 0 and view.normalized_foods == frozenset()


def test_the_same_food_written_twice_in_a_meal_counts_two_items_and_one_food():
    (view,) = meal_views(
        [meal("a", "2026-10-20T08:00", MealType.BREAKFAST, [("Pan", "1"), ("pan", "2")])]
    )

    assert view.item_count == 2 and view.normalized_foods == frozenset({"pan"})


# -------------------------------------------------------------------- filtros
def uuids(views):
    return [v.uuid for v in views]


def test_no_criteria_returns_everything():
    views = meal_views(sample_meals())
    assert filter_meals(views) == views


def test_period_uses_local_days_and_an_exclusive_end():
    views = meal_views(sample_meals())

    first_day = filter_meals(views, period=period(date(2026, 10, 20), date(2026, 10, 20)))
    assert uuids(first_day) == ["m1", "m2", "m3"]

    later = filter_meals(views, period=period(date(2026, 10, 21), date(2026, 10, 24)))
    assert uuids(later) == ["m4", "m5"]


def test_meal_at_the_period_end_instant_is_excluded():
    views = meal_views(sample_meals())
    p = period(*WEEK)
    boundary = [m for m in views if m.eaten_at == p.end]
    assert boundary == []


def test_type_filter_includes_the_unknown_type_only_when_asked():
    views = meal_views(sample_meals())

    only_breakfast = filter_meals(views, types={MealType.BREAKFAST})
    assert uuids(only_breakfast) == ["m1", "m4", "m6"]

    breakfast_or_unknown = filter_meals(views, types={MealType.BREAKFAST, None})
    assert uuids(breakfast_or_unknown) == ["m1", "m4", "m6", "m7"]


def test_an_empty_type_selection_returns_no_meals():
    assert filter_meals(meal_views(sample_meals()), types=set()) == []


def test_food_filter_matches_any_selected_food_using_normalized_names():
    views = meal_views(sample_meals())

    assert uuids(filter_meals(views, foods={"pan"})) == ["m1", "m3", "m4", "m7"]
    assert uuids(filter_meals(views, foods={"palta", "arroz"})) == ["m2", "m4"]  # O, no Y


def test_food_filter_normalizes_what_the_user_types():
    views = meal_views(sample_meals())

    assert uuids(filter_meals(views, foods={normalize_food_name("CAFÉ")})) == ["m6"]


def test_meals_without_foods_never_match_a_food_filter():
    views = meal_views(sample_meals())
    assert "m5" not in uuids(filter_meals(views, foods={"pan", "arroz", "palta"}))


def test_filters_combine_with_and_between_different_criteria():
    views = meal_views(sample_meals())

    result = filter_meals(
        views,
        period=period(date(2026, 10, 20), date(2026, 10, 21)),
        types={MealType.BREAKFAST, MealType.DINNER},
        foods={"pan"},
    )

    assert uuids(result) == ["m1", "m3"]


@pytest.mark.parametrize("empty", [set(), frozenset()])
def test_empty_food_selection_returns_no_meals(empty):
    assert filter_meals(meal_views(sample_meals()), foods=empty) == []


def test_meal_items_are_immutable():
    (view,) = meal_views([meal("a", "2026-10-20T08:00", MealType.LUNCH, [("Pan", "1")])])
    with pytest.raises((AttributeError, TypeError)):
        view.items[0].name = "otro"  # type: ignore[misc]
    assert isinstance(view.items, tuple)
    assert MealItem("Pan", "1") is not None
