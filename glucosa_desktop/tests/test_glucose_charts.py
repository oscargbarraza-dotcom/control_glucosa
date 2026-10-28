"""Gráficos Plotly y tabla del módulo Glucosa (estructura de las figuras, sin renderizar)."""

from datetime import UTC, datetime, timedelta

import pytest

from glucosa.analytics.glucose_sensor import SensorSample
from glucosa.analytics.glucose_summaries import summarize_manual
from glucosa.analytics.glucose_view import GlucosePoint, Kind, Source
from glucosa.models.records import GlucoseMoment
from glucosa.ui.glucose_charts import (
    COLOR_MANUAL,
    COLOR_SCAN,
    COLOR_SENSOR,
    evolution_figure,
    manual_bands_figure,
    sensor_bands_figure,
    sensor_histogram_figure,
)
from glucosa.ui.glucose_table import TABLE_COLUMNS, points_table

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)  # 09:00 en Santiago (UTC-3)


def sensor(offset_min, value):
    return GlucosePoint(T0 + timedelta(minutes=offset_min), value, Source.LIBREVIEW, Kind.SENSOR)


def scan(offset_min, value):
    return GlucosePoint(T0 + timedelta(minutes=offset_min), value, Source.LIBREVIEW, Kind.SCAN)


def manual(offset_min, value, moment=GlucoseMoment.AFTER_LUNCH, comment=None):
    return GlucosePoint(
        T0 + timedelta(minutes=offset_min), value, Source.FIREBASE, Kind.MANUAL, moment, comment
    )


def traces_by_name(fig):
    return {t.name: t for t in fig.data}


# ---------------------------------------------------------------- evolución
def test_sources_are_distinguished_by_name_color_and_symbol():
    fig = evolution_figure(
        manual=[manual(10, 150)],
        sensor=[sensor(0, 120), sensor(15, 125)],
        scans=[],
        low=70,
        high=180,
    )
    traces = traces_by_name(fig)

    assert set(traces) == {"Sensor LibreView", "Manual Firebase"}
    assert traces["Sensor LibreView"].line.color == COLOR_SENSOR
    assert traces["Manual Firebase"].marker.color == COLOR_MANUAL
    assert traces["Manual Firebase"].marker.symbol == "diamond"
    assert traces["Manual Firebase"].mode == "markers"  # puntos independientes, sin línea


def test_scan_layer_is_absent_by_default_and_present_when_enabled():
    kwargs = dict(manual=[], sensor=[sensor(0, 120)], scans=[scan(5, 130)], low=70, high=180)
    assert "Escaneo LibreView" not in traces_by_name(evolution_figure(**kwargs))

    enabled = traces_by_name(evolution_figure(**kwargs, show_scans=True))
    assert enabled["Escaneo LibreView"].marker.line.color == COLOR_SCAN
    assert enabled["Escaneo LibreView"].mode == "markers"


def test_sensor_line_is_broken_across_interruptions_longer_than_30_minutes():
    points = [
        sensor(0, 100),
        sensor(15, 101),
        sensor(30, 102),
        sensor(31 + 45, 103),
        sensor(31 + 60, 104),
    ]
    fig = evolution_figure(manual=[], sensor=points, scans=[], low=70, high=180)
    trace = traces_by_name(fig)["Sensor LibreView"]

    assert trace.connectgaps is False
    assert sum(y is None for y in trace.y) == 1  # un solo corte (el hueco de 46 min)
    assert [y for y in trace.y if y is not None] == [
        100,
        101,
        102,
        103,
        104,
    ]  # sin valores inventados


def test_a_gap_of_exactly_30_minutes_is_not_broken():
    fig = evolution_figure(
        manual=[], sensor=[sensor(0, 100), sensor(30, 101)], scans=[], low=70, high=180
    )
    assert None not in traces_by_name(fig)["Sensor LibreView"].y


def test_x_values_are_local_santiago_wall_clock_times():
    fig = evolution_figure(manual=[manual(0, 150)], sensor=[], scans=[], low=70, high=180)
    assert traces_by_name(fig)["Manual Firebase"].x[0] == datetime(2026, 10, 20, 9, 0)


def test_hover_shows_date_value_source_and_declared_moment_and_escapes_comments():
    fig = evolution_figure(
        manual=[manual(0, 150, GlucoseMoment.AFTER_LUNCH, comment="<script>alert(1)</script>")],
        sensor=[sensor(5, 120)],
        scans=[],
        low=70,
        high=180,
    )
    manual_hover = traces_by_name(fig)["Manual Firebase"].hovertext[0]
    assert "150 mg/dL" in manual_hover and "Firebase" in manual_hover
    assert "Después almuerzo" in manual_hover
    assert "<script>" not in manual_hover and "&lt;script&gt;" in manual_hover
    sensor_hover = traces_by_name(fig)["Sensor LibreView"].hovertext[0]
    assert "120 mg/dL" in sensor_hover and "LibreView" in sensor_hover
    assert "Momento" not in sensor_hover


def test_target_range_band_is_drawn_and_zoom_pan_are_enabled():
    fig = evolution_figure(manual=[manual(0, 150)], sensor=[], scans=[], low=80, high=160)
    band = [s for s in fig.layout.shapes if s.type == "rect"]
    assert len(band) == 1 and (band[0].y0, band[0].y1) == (80, 160)
    assert fig.layout.dragmode == "zoom"
    assert fig.layout.xaxis.rangeslider.visible is False
    assert fig.layout.hovermode == "closest"


def test_figure_with_no_data_is_still_valid_and_serializable():
    fig = evolution_figure(manual=[], sensor=[], scans=[], low=70, high=180)
    assert fig.to_json()
    assert len(fig.data) == 0


def test_large_sensor_series_uses_webgl():
    points = [sensor(15 * i, 100 + i % 50) for i in range(5000)]
    fig = evolution_figure(manual=[], sensor=points, scans=[], low=70, high=180)
    assert traces_by_name(fig)["Sensor LibreView"].type == "scattergl"


# ------------------------------------------------------------- distribuciones
def test_manual_bands_figure_shows_percentages_of_measurements_not_time():
    summary = summarize_manual([manual(i, v) for i, v in enumerate([60, 100, 120, 200])], 70, 180)

    fig = manual_bands_figure(summary)

    assert [t.name for t in fig.data] == ["Bajo el rango", "Dentro del rango", "Sobre el rango"]
    assert [t.x[0] for t in fig.data] == [25.0, 50.0, 25.0]
    assert "mediciones manuales" in fig.layout.title.text.lower()
    assert "tiempo en rango" in fig.layout.title.text.lower()  # aclara que NO lo es


def test_manual_bands_figure_is_none_without_measurements():
    assert manual_bands_figure(summarize_manual([], 70, 180)) is None


def test_sensor_bands_figure_requires_enough_data_and_is_labelled_as_an_estimate():
    from glucosa.analytics.glucose_filters import Period
    from glucosa.analytics.glucose_summaries import summarize_sensor

    samples = [
        SensorSample(T0 + timedelta(minutes=15 * i), 100 if i % 2 else 200) for i in range(96)
    ]
    start = T0 - timedelta(minutes=7.5)
    period = Period(start, start + timedelta(days=1), "x", start.date(), start.date())

    summary = summarize_sensor(samples, period, 70, 180)
    fig = sensor_bands_figure(summary.tir)

    assert fig is not None
    assert pytest.approx(sum(t.x[0] for t in fig.data)) == 100.0
    assert (
        "estimado" in fig.layout.title.text.lower() and "libreview" in fig.layout.title.text.lower()
    )

    insufficient = summarize_sensor(samples[:10], period, 70, 180)
    assert sensor_bands_figure(insufficient.tir) is None


def test_histogram_has_one_colored_trace_per_band():
    from glucosa.analytics.glucose_summaries import histogram

    fig = sensor_histogram_figure(histogram([40, 100, 200], low=70, high=180), low=70, high=180)
    assert len({trace.marker.color for trace in fig.data}) == 3  # bajo / dentro / sobre


# --------------------------------------------------------------------- tabla
def test_table_has_the_requested_columns_and_hides_technical_identifiers():
    frame = points_table(
        [manual(0, 150, comment="almuerzo"), sensor(5, 120), scan(6, 130)], 70, 180
    )

    assert list(frame.columns) == list(TABLE_COLUMNS)
    assert not any("uuid" in c.lower() or "dispositivo" in c.lower() for c in frame.columns)
    rows = {r["Tipo de registro"]: r for r in frame.to_dict("records")}
    assert rows["Medición manual"]["Fuente"] == "Firebase"
    assert rows["Medición manual"]["Momento declarado"] == "Después almuerzo"
    assert rows["Medición manual"]["Observaciones"] == "almuerzo"
    assert rows["Historial del sensor"]["Fuente"] == "LibreView"
    assert rows["Historial del sensor"]["Momento declarado"] == ""
    assert rows["Escaneo del sensor"]["Clasificación"] == "Dentro del rango"


def test_table_is_sorted_newest_first_and_uses_local_time():
    frame = points_table([sensor(0, 100), sensor(60, 101)], 70, 180)
    assert list(frame["Glucosa (mg/dL)"]) == [101, 100]
    assert frame["Fecha y hora"].iloc[1] == datetime(2026, 10, 20, 9, 0)


def test_empty_table_keeps_its_columns():
    frame = points_table([], 70, 180)
    assert list(frame.columns) == list(TABLE_COLUMNS) and frame.empty
