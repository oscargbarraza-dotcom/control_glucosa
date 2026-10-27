"""Figuras de Alimentación: distribuciones y gráfico de glucosa de −60 a +180 min (sin Streamlit)."""

import json

import pytest

from glucosa.analytics.meal_glucose import AssociationParams, associate_meals
from glucosa.analytics.meal_milestones import MilestoneParams
from glucosa.analytics.meal_readings import ReadingSource as S
from glucosa.analytics.meal_summaries import (
    food_ranking,
    hour_histogram,
    meals_by_day,
    type_counts,
)
from glucosa.analytics.meal_view import meal_views
from glucosa.models.records import MealRecord, MealType
from glucosa.ui.glucose_charts import COLOR_MANUAL, COLOR_SCAN, COLOR_SENSOR
from glucosa.ui.meal_charts import (
    daily_figure,
    hours_figure,
    meal_window_figure,
    ranking_figure,
    type_figure,
)
from glucosa.ui.meal_labels import LEGEND_NAMES, WINDOW_LABELS, signed_minutes
from tests.meal_glucose_helpers import (
    NOW,
    at,
    imported,
    inputs,
    manual,
    meals,
    scan,
    sensor_run,
)
from tests.meal_helpers import WEEK, period, sample_meals


def traces(fig):
    return {t.name: t for t in fig.data}


def figure_for(
    readings, *, tolerance=10, show_scans=False, specs=(("a", 0),), selected="a", range_=(70, 180)
):
    association = associate_meals(
        meals(*specs),
        inputs(*readings),
        NOW,
        AssociationParams(milestones=MilestoneParams(tolerance)),
    )
    outcome = next(m for m in association.meals if m.uuid == selected)
    view = next(v for v in meals(*specs) if v.uuid == selected)
    return meal_window_figure(
        view,
        outcome,
        association,
        tolerance_minutes=tolerance,
        sources=frozenset({S.MANUAL, S.IMPORTED, S.SENSOR}),
        show_scans=show_scans,
        target_range=range_,
    )


# ------------------------------------------------------------- distribuciones
def test_type_figure_has_one_bar_per_type_with_counts_and_shares():
    fig = type_figure(type_counts(meal_views(sample_meals())))

    bar = fig.data[0]
    assert sum(bar.x) == 7 and len(bar.y) == 6 and bar.marker.color == COLOR_MANUAL
    assert "Desayuno" in list(bar.y) and "Tipo desconocido" in list(bar.y)


def test_type_figure_hides_the_unknown_type_when_there_are_none():
    records = [MealRecord("a", MealType.LUNCH, at(0), None)]

    fig = type_figure(type_counts(meal_views(records)))

    assert "Tipo desconocido" not in list(fig.data[0].y) and len(fig.data[0].y) == 5


def test_hours_figure_has_24_bars_in_local_hours():
    fig = hours_figure(hour_histogram(meal_views(sample_meals())))

    assert list(fig.data[0].x) == list(range(24)) and sum(fig.data[0].y) == 7
    assert fig.layout.xaxis.title.text.lower().startswith("hora")


def test_ranking_figure_orders_foods_by_meals_and_escapes_the_names():
    records = [
        MealRecord("a", MealType.LUNCH, at(0), None, (_item("<b>Pan</b> & <i>x</i>"),)),
        MealRecord(
            "b", MealType.LUNCH, at(500), None, (_item("<b>Pan</b> & <i>x</i>"), _item("Palta"))
        ),
    ]

    fig = ranking_figure(food_ranking(meal_views(records)))

    shown = json.dumps(
        [fig.data[0].to_plotly_json(), list(fig.layout.yaxis.ticktext)], ensure_ascii=False
    )
    assert "<b>" not in shown and "<i>" not in shown  # el HTML del usuario nunca llega a Plotly
    assert "&lt;b&gt;" in shown
    assert sorted(fig.data[0].x) == [1, 2]  # «Pan» está en 2 comidas; «Palta» en 1


def _item(name):
    from glucosa.models.records import MealItem

    return MealItem(name, "1")


def test_ranking_figure_shows_only_the_top_n_and_none_without_foods():
    ranking = food_ranking(meal_views(sample_meals()))

    assert len(ranking_figure(ranking, top=3).data[0].x) == 3
    assert ranking_figure([]) is None


def test_daily_figure_marks_days_without_records_instead_of_zero_bars_alone():
    days = meals_by_day(meal_views(sample_meals()), period(*WEEK))

    fig = daily_figure(days)

    names = traces(fig)
    assert sum(names["Comidas"].y) == 7
    assert list(names["Días sin registro"].x) and all(v == 0 for v in names["Días sin registro"].y)
    assert len(names["Días sin registro"].x) == 4
    assert "sin registro" in fig.layout.title.text.lower()


# --------------------------------------------------------- gráfico de una comida
def test_manual_readings_are_markers_only_never_a_connected_series():
    fig = figure_for([manual(-20, 100), manual(10, 140), manual(80, 150)])

    manual_trace = traces(fig)[LEGEND_NAMES[S.MANUAL]]
    assert manual_trace.mode == "markers" and manual_trace.marker.symbol == "diamond"
    assert manual_trace.marker.color == COLOR_MANUAL
    assert list(manual_trace.x) == [-20.0, 10.0, 80.0]


def test_the_sensor_is_a_line_cut_at_interruptions_longer_than_30_minutes():
    readings = sensor_run(-60, 0) + sensor_run(60, 180)  # hueco de 60 min entre 0 y 60

    sensor_trace = traces(figure_for(readings))[LEGEND_NAMES[S.SENSOR]]

    assert "lines" in sensor_trace.mode and sensor_trace.line.color == COLOR_SENSOR
    assert None in list(sensor_trace.y)  # la línea no cruza el hueco
    assert [v for v in sensor_trace.y if v is not None]


def test_imported_readings_have_their_own_hollow_marker():
    fig = figure_for([imported(30, 120)])

    trace = traces(fig)[LEGEND_NAMES[S.IMPORTED]]
    assert trace.marker.symbol == "diamond-open" and trace.mode == "markers"


def test_scans_are_hidden_by_default_and_shown_only_when_asked():
    assert LEGEND_NAMES[S.SCAN] not in traces(figure_for([scan(30, 120)]))

    shown = traces(figure_for([scan(30, 120)], show_scans=True))[LEGEND_NAMES[S.SCAN]]
    assert shown.marker.color == COLOR_SCAN and shown.mode == "markers"


def test_x_axis_is_minutes_from_the_record_with_the_approved_window_limits():
    fig = figure_for([manual(10)])

    low, high = fig.layout.xaxis.range
    assert low <= -60 and high >= 180
    assert fig.layout.xaxis.title.text.lower().startswith("minutos")


def test_marks_at_record_plus_60_and_plus_90_with_tolerance_bands():
    fig = figure_for([manual(60)], tolerance=15)

    lines = [s for s in fig.layout.shapes if s.type == "line"]
    bands = [s for s in fig.layout.shapes if s.type == "rect" and s.x1 - s.x0 in (30, 30.0)]
    assert sorted({s.x0 for s in lines if s.x0 in (0, 60, 90)}) == [0, 60, 90]
    assert sorted(b.x0 for b in bands) == [45, 75]  # ±15 alrededor de +60 y de +90


def test_a_wider_sensor_tolerance_gets_its_own_band_when_the_minimum_applies():
    fig = figure_for([manual(60)], tolerance=5)

    widths = sorted(
        round(s.x1 - s.x0)
        for s in fig.layout.shapes
        if s.type == "rect" and s.x0 in (52, 55, 82, 85)
    )
    assert widths == [10, 10, 16, 16]  # ±5 para manuales y ±8 para el sensor


def test_the_window_areas_are_named_with_the_approved_limits():
    fig = figure_for([manual(10)])

    text = " ".join(a.text for a in fig.layout.annotations)
    for label in ("Previa", "Al comer", "Posterior"):
        assert label in text
    assert WINDOW_LABELS and "Previa" in WINDOW_LABELS[next(iter(WINDOW_LABELS))]


def test_the_reference_after_the_record_is_flagged_in_its_hover_and_not_called_previous():
    fig = figure_for([manual(3, 150)])

    reference = traces(fig)["Referencia"]
    assert list(reference.x) == [3.0]
    assert "posterior al registro" in reference.hovertext[0].lower()
    assert "previa" not in reference.hovertext[0].lower()


def test_a_reference_before_the_record_is_not_labelled_as_posterior():
    reference = traces(figure_for([manual(-3, 150)]))["Referencia"]

    assert "posterior al registro" not in reference.hovertext[0].lower()


def test_the_nearest_reading_to_each_milestone_is_highlighted_with_its_offset():
    fig = figure_for([manual(62, 150), manual(88, 160)])

    nearest = traces(fig)["Más cercana al hito"]
    assert sorted(nearest.x) == [62.0, 88.0]
    assert any("+60" in h and "+2 min" in h for h in nearest.hovertext)


def test_nearby_meals_are_marked_so_shared_windows_are_visible():
    fig = figure_for([manual(10)], specs=(("a", 0), ("b", 45)))

    text = " ".join(a.text for a in fig.layout.annotations)
    assert "Otra comida" in text and "+45" in text


def test_a_meal_without_readings_still_gets_a_figure_that_says_so():
    fig = figure_for([])

    assert any("sin mediciones" in a.text.lower() for a in fig.layout.annotations)


def test_the_target_range_band_is_drawn():
    fig = figure_for([manual(10)], range_=(80, 160))

    assert any(s.type == "rect" and s.y0 == 80 and s.y1 == 160 for s in fig.layout.shapes)


def test_hover_texts_contain_no_markup_from_user_text():
    fig = figure_for([manual(10, 150)])

    for trace in fig.data:
        for hover in trace.hovertext or []:
            assert "<script" not in str(hover).lower()


def test_signed_minutes_uses_the_typographic_minus():
    assert signed_minutes(-12) == "−12 min" and signed_minutes(3) == "+3 min"


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (0.0, "0 s"),
        (0.2, "+12 s"),
        (-0.4, "−24 s"),
        (0.5, "+30 s"),
        (-0.99, "−59 s"),
        (0.0001, "+1 s"),  # un desfase distinto de cero nunca se muestra como «0»
        (-0.0001, "−1 s"),
        (0.9999, "+1 min"),  # redondea a 60 s: se expresa en minutos
        (-0.9999, "−1 min"),
        (1.0, "+1 min"),
        (1.4, "+1 min"),
        (-59.6, "−60 min"),
        (180.0, "+180 min"),
    ],
)
def test_offsets_under_a_minute_are_shown_in_seconds_keeping_the_sign(minutes, expected):
    assert signed_minutes(minutes) == expected


def test_decimals_are_kept_only_when_requested_and_needed():
    assert signed_minutes(62.5, 1) == "+62.5 min" and signed_minutes(30.0, 1) == "+30 min"
    assert signed_minutes(-1.5, 1) == "−1.5 min" and signed_minutes(62.04, 1) == "+62 min"


def test_the_reference_hover_uses_seconds_when_the_gap_is_under_a_minute():
    fig = figure_for([manual(0.4, 150)])

    hover = traces(fig)["Referencia"].hovertext[0]
    assert "+24 s" in hover and "0 min" not in hover and "posterior al registro" in hover.lower()


@pytest.mark.parametrize("tolerance", [5, 10, 20])
def test_the_figure_is_serializable_for_every_allowed_tolerance(tolerance):
    assert json.loads(figure_for([manual(60)], tolerance=tolerance).to_json())["data"]


def test_bar_charts_leave_room_on_the_right_for_their_value_labels():
    types = type_figure(type_counts(meal_views(sample_meals())))
    foods = ranking_figure(food_ranking(meal_views(sample_meals())))

    for fig in (types, foods):
        low, high = fig.layout.xaxis.range
        assert low == 0 and high > max(fig.data[0].x)
