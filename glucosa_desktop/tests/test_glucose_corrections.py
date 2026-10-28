"""Correcciones de la Etapa C: procedencia (D-1), filtro de momento (M-5), histograma (M-8),
«Hoy» a medianoche y representación de la hora repetida del cambio de horario."""

from datetime import UTC, date, datetime, timedelta

import pytest

from glucosa.analytics.glucose_filters import CUSTOM, filter_points, resolve_period
from glucosa.analytics.glucose_summaries import (
    IMPORTED_PERCENT_LABEL,
    MANUAL_PERCENT_LABEL,
    histogram,
    summarize_imported,
    summarize_manual,
)
from glucosa.analytics.glucose_view import (
    BAND_LABELS,
    KIND_LABELS,
    Band,
    GlucosePoint,
    Kind,
    Source,
    manual_points,
)
from glucosa.data.timeutil import SANTIAGO, parse_timestamp, repeated_hour_pass
from glucosa.models.records import GlucoseMoment, GlucoseRecord, Origin
from glucosa.ui.glucose_charts import (
    BAND_COLORS,
    COLOR_MANUAL,
    IMPORTED_NAME,
    PLOT_CONFIG,
    evolution_figure,
    sensor_histogram_figure,
)
from glucosa.ui.glucose_table import TABLE_COLUMNS, points_table

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def record(uuid, value, origin, moment=GlucoseMoment.NOW, minutes=0):
    return GlucoseRecord(
        uuid,
        value,
        moment,
        parse_timestamp(f"2026-10-20T09:{minutes:02d}:00.000000"),
        None,
        origin,
        "OtraApp" if origin is Origin.IMPORTED else None,
    )


def fb_point(minutes, value, kind=Kind.MANUAL, moment=GlucoseMoment.NOW):
    return GlucosePoint(T0 + timedelta(minutes=minutes), value, Source.FIREBASE, kind, moment)


def sensor_point(minutes, value):
    return GlucosePoint(T0 + timedelta(minutes=minutes), value, Source.LIBREVIEW, Kind.SENSOR)


# ------------------------------------------------------------- D-1: procedencia
def test_firebase_records_are_split_by_origin_without_dropping_any():
    records = [
        record("a", 100, Origin.MANUAL),
        record("b", 110, Origin.IMPORTED, minutes=1),
        record("c", 120, Origin.MANUAL, minutes=2),
    ]

    points = manual_points(records)

    assert len(points) == 3
    assert [p.kind for p in points] == [Kind.MANUAL, Kind.IMPORTED, Kind.MANUAL]
    assert all(p.source is Source.FIREBASE for p in points)  # siguen siendo de Firebase


def test_imported_measurements_have_their_own_label_and_are_not_called_sensor_readings():
    assert KIND_LABELS[Kind.IMPORTED] == "Medición importada"
    assert Kind.IMPORTED not in (Kind.SENSOR, Kind.SCAN)


def test_manual_statistics_exclude_imported_measurements():
    points = [fb_point(0, 100), fb_point(5, 300, Kind.IMPORTED), fb_point(10, 140)]

    manual = summarize_manual(points, 70, 180)

    assert manual.count == 2 and manual.maximum == 140
    assert manual.label == MANUAL_PERCENT_LABEL and "manuales" in manual.label


def test_imported_measurements_get_their_own_labelled_indicators():
    points = [fb_point(0, 100), fb_point(5, 300, Kind.IMPORTED), fb_point(10, 90, Kind.IMPORTED)]

    imported = summarize_imported(points, 70, 180)

    assert imported.count == 2 and imported.maximum == 300 and imported.minimum == 90
    assert imported.label == IMPORTED_PERCENT_LABEL
    assert "importadas" in imported.label and "no es tiempo en rango" in imported.label
    assert (imported.below, imported.in_range, imported.above) == (0, 1, 1)


def test_summaries_of_either_origin_are_empty_without_numbers_when_there_are_none():
    only_manual = [fb_point(0, 100)]
    assert summarize_imported(only_manual, 70, 180).count == 0
    assert summarize_imported(only_manual, 70, 180).mean is None


def test_imported_measurements_are_drawn_apart_from_manual_ones_with_the_firebase_color():
    fig = evolution_figure(
        manual=[fb_point(0, 100)],
        sensor=[sensor_point(0, 120)],
        scans=[],
        low=70,
        high=180,
        imported=[fb_point(5, 130, Kind.IMPORTED)],
    )

    traces = {t.name: t for t in fig.data}

    assert IMPORTED_NAME in traces and "Manual Firebase" in traces
    assert traces[IMPORTED_NAME].marker.symbol != traces["Manual Firebase"].marker.symbol
    assert traces[IMPORTED_NAME].marker.line.color == COLOR_MANUAL  # misma fuente: Firebase
    assert list(traces[IMPORTED_NAME].y) == [130]


def test_table_labels_imported_rows_with_their_own_type():
    frame = points_table([fb_point(0, 100), fb_point(5, 130, Kind.IMPORTED)], 70, 180)

    assert set(frame["Tipo de registro"]) == {"Medición manual", "Medición importada"}
    assert set(frame["Fuente"]) == {"Firebase"}


# ----------------------------------------------- M-5: «sin momento declarado» filtrable
def test_points_without_a_declared_moment_survive_only_if_the_filter_includes_them():
    with_moment = fb_point(0, 100, moment=GlucoseMoment.NOW)
    without = fb_point(5, 110, moment=None)

    only_now = filter_points([with_moment, without], moments={GlucoseMoment.NOW})
    with_none = filter_points([with_moment, without], moments={GlucoseMoment.NOW, None})
    only_none = filter_points([with_moment, without], moments={None})

    assert only_now == [with_moment]
    assert with_none == [with_moment, without]
    assert only_none == [without]


def test_the_moment_filter_applies_to_manual_and_imported_but_never_to_the_sensor():
    points = [
        fb_point(0, 100, Kind.MANUAL, GlucoseMoment.NOW),
        fb_point(1, 101, Kind.IMPORTED, GlucoseMoment.NOW),
        sensor_point(2, 102),
    ]

    kept = filter_points(points, moments={GlucoseMoment.WAKING_UP})

    assert kept == [points[2]]


def test_frozensets_are_valid_filter_arguments():
    point = fb_point(0, 100)
    assert filter_points([point], bands=frozenset(Band), moments=frozenset({GlucoseMoment.NOW}))


# -------------------------------------------------- M-8: histograma sin clases falsas
def test_histogram_counts_each_value_in_its_own_band_even_inside_a_mixed_bar():
    bins = histogram([65, 66, 75, 150, 181], width=20, low=70, high=180)

    mixed = next(b for b in bins if b.start == 60)  # [60, 80): dos bajos y uno en rango
    assert (mixed.below, mixed.in_range, mixed.above) == (2, 1, 0)
    assert sum(b.count for b in bins) == 5
    assert sum(b.below for b in bins) == 2
    assert sum(b.in_range for b in bins) == 2
    assert sum(b.above for b in bins) == 1


def test_histogram_limits_are_inclusive_on_the_range_edges():
    bins = histogram([69, 70, 180, 181], width=20, low=70, high=180)

    assert sum(b.below for b in bins) == 1  # 69
    assert sum(b.in_range for b in bins) == 2  # 70 y 180
    assert sum(b.above for b in bins) == 1  # 181


def test_histogram_figure_stacks_one_trace_per_band_with_the_right_color():
    fig = sensor_histogram_figure(histogram([65, 66, 75, 150, 181], 20, 70, 180), 70, 180)

    by_name = {t.name: t for t in fig.data}
    assert set(by_name) == set(BAND_LABELS.values())
    for band, label in BAND_LABELS.items():
        assert by_name[label].marker.color == BAND_COLORS[band]
    assert sum(by_name[BAND_LABELS[Band.BELOW]].y) == 2
    assert sum(by_name[BAND_LABELS[Band.IN_RANGE]].y) == 2
    assert sum(by_name[BAND_LABELS[Band.ABOVE]].y) == 1
    assert fig.layout.barmode == "stack"


def test_histogram_hover_does_not_suggest_the_upper_edge_is_included():
    fig = sensor_histogram_figure(histogram([65], 20, 70, 180), 70, 180)

    hover = fig.data[0].hovertemplate
    assert "%{customdata[1]}" in hover
    assert fig.data[0].customdata[0][1] == 79  # el intervalo [60, 80) se rotula 60–79


# ------------------------------------------------------------ «Hoy» a medianoche
def test_today_exactly_at_local_midnight_is_a_valid_nonempty_period():
    midnight_local = datetime(2026, 10, 26, 0, 0, tzinfo=SANTIAGO).astimezone(UTC)

    period = resolve_period("Hoy", midnight_local)

    assert period.end > period.start


def test_other_relative_periods_are_also_valid_at_midnight():
    midnight_local = datetime(2026, 10, 26, 0, 0, tzinfo=SANTIAGO).astimezone(UTC)
    for option in ("Últimos 7 días", "Últimos 30 días", "Últimos 3 meses"):
        assert (
            resolve_period(option, midnight_local).end
            > resolve_period(option, midnight_local).start
        )


def test_a_custom_period_ending_today_at_midnight_is_valid():
    midnight_local = datetime(2026, 10, 26, 0, 0, tzinfo=SANTIAGO).astimezone(UTC)
    period = resolve_period(CUSTOM, midnight_local, date(2026, 10, 26), date(2026, 10, 26))
    assert period.end > period.start


# ---------------------------------------------- hora repetida (fin del horario de verano)
# 2026-04-04 24:00 los relojes de Chile vuelven a las 23:00: la hora 23:00–24:00 ocurre dos veces.
FIRST_2330 = datetime(2026, 4, 5, 2, 30, tzinfo=UTC)  # 23:30 (UTC-3), primera vez
SECOND_2300 = datetime(2026, 4, 5, 3, 0, tzinfo=UTC)  # 23:00 (UTC-4), segunda vez
SECOND_2315 = datetime(2026, 4, 5, 3, 15, tzinfo=UTC)


def dst_sensor(instants_values):
    return [GlucosePoint(i, v, Source.LIBREVIEW, Kind.SENSOR) for i, v in instants_values]


def test_repeated_hour_pass_identifies_first_and_second_occurrence():
    assert repeated_hour_pass(FIRST_2330) == 1
    assert repeated_hour_pass(SECOND_2300) == 2
    assert repeated_hour_pass(datetime(2026, 4, 5, 12, 0, tzinfo=UTC)) is None
    assert repeated_hour_pass(datetime(2026, 7, 1, 12, 0, tzinfo=UTC)) is None


def test_sensor_line_never_runs_backwards_on_the_repeated_hour():
    sensor = dst_sensor(
        [
            (datetime(2026, 4, 5, 2, 15, tzinfo=UTC), 100),
            (FIRST_2330, 101),
            (datetime(2026, 4, 5, 2, 45, tzinfo=UTC), 102),
            (SECOND_2300, 103),
            (SECOND_2315, 104),
        ]
    )

    fig = evolution_figure(manual=[], sensor=sensor, scans=[], low=70, high=180)

    xs, ys = list(fig.data[0].x), list(fig.data[0].y)
    previous_x = None
    previous_gap = False
    for x, y in zip(xs, ys, strict=True):
        if y is None:
            previous_gap = True
            continue
        if previous_x is not None and x < previous_x:
            assert previous_gap, "la línea retrocede en el tiempo sin cortarse"
        previous_x, previous_gap = x, False


def test_hover_flags_points_that_fall_in_the_repeated_hour():
    sensor = dst_sensor([(FIRST_2330, 101), (SECOND_2300, 103)])

    fig = evolution_figure(manual=[], sensor=sensor, scans=[], low=70, high=180)

    hovers = [h for h in fig.data[0].hovertext if h]
    assert "1.ª vez" in hovers[0] and "2.ª vez" in hovers[1]


def test_table_marks_repeated_hour_rows_and_leaves_the_rest_blank():
    sensor = dst_sensor(
        [(FIRST_2330, 101), (SECOND_2300, 103), (datetime(2026, 7, 1, 12, 0, tzinfo=UTC), 99)]
    )

    frame = points_table(sensor, 70, 180)

    marks = dict(zip(frame["Glucosa (mg/dL)"], frame["Cambio de hora"], strict=True))
    assert "1.ª vez" in marks[101] and "2.ª vez" in marks[103] and marks[99] == ""
    assert "Cambio de hora" in TABLE_COLUMNS


# ------------------------------------------------------------------ exportaciones
def test_plotly_config_removes_the_png_export_button():
    assert "toImage" in PLOT_CONFIG["modeBarButtonsToRemove"]
    assert PLOT_CONFIG["displaylogo"] is False


@pytest.mark.parametrize("scenario", ["manual", "imported"])
def test_empty_firebase_summaries_do_not_raise(scenario):
    summarize = summarize_manual if scenario == "manual" else summarize_imported
    assert summarize([], 70, 180).count == 0
