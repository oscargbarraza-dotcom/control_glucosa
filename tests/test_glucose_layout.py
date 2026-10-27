"""Refinamiento visual de la Fase C: tarjetas, encabezado, filtro de momento y contador de registros.

Las cifras no se recalculan en la interfaz: estas pruebas comprueban que lo que se muestra es
exactamente lo que dan las funciones de análisis, y que el rediseño no cambió ningún número.
"""

from datetime import date

import pytest

from glucosa.analytics.glucose_filters import filter_points, resolve_period
from glucosa.analytics.glucose_sensor import consolidate_history
from glucosa.analytics.glucose_summaries import summarize_manual, summarize_sensor
from glucosa.analytics.glucose_view import manual_points
from glucosa.ui.glucose_kpi import Kpi, Tone, kpi_grid_html
from glucosa.ui.glucose_style import COMPACT_CSS
from tests.glucose_fakes import NOW, libre_readings, manual_records
from tests.test_glucose_page import (
    kpis,
    metric,
    run,
    set_custom_period,
    table,
    texts,
)


# ------------------------------------------------------------------ tarjetas (KPI)
def test_kpi_cards_escape_every_text_and_keep_units_apart_from_values():
    html_text = kpi_grid_html(
        [Kpi('<b>"x"</b>', "<i>1</i>", "mg/dL", 'tip"<script>')], Tone.FIREBASE
    )

    assert "<script>" not in html_text and "<b>" not in html_text and "<i>" not in html_text
    assert '<span class="kpi-unit">mg/dL</span>' in html_text
    assert "&lt;b&gt;" in html_text and "kpi-firebase" in html_text


def test_kpi_tones_distinguish_firebase_and_libreview():
    assert "kpi-firebase" in kpi_grid_html([Kpi("a", "1")], Tone.FIREBASE)
    assert "kpi-libreview" in kpi_grid_html([Kpi("a", "1")], Tone.LIBREVIEW)


def test_kpi_without_unit_or_tip_has_no_empty_markup():
    card = kpi_grid_html([Kpi("Mediciones", "112")], Tone.FIREBASE)
    assert "kpi-unit" not in card and "title=" not in card


def test_the_compact_css_is_a_static_constant_without_templating():
    assert "{" in COMPACT_CSS and "%s" not in COMPACT_CSS and "{{" not in COMPACT_CSS
    assert "<script" not in COMPACT_CSS.lower() and "url(" not in COMPACT_CSS.lower()


def test_firebase_and_libreview_indicators_have_the_requested_short_labels(monkeypatch):
    labels = [k.label for k in kpis(run(monkeypatch))]

    assert labels[:6] == ["Última", "Mediciones", "Promedio", "Mediana", "Mínimo", "Máximo"]
    assert labels[6:] == ["Lecturas", "Promedio", "Mediana", "Mínimo", "Máximo", "Cobertura"]


def test_indicator_values_keep_the_mg_dl_unit(monkeypatch):
    app = run(monkeypatch)
    assert metric(app, "Última").value.endswith("mg/dL")
    assert metric(app, "Mediciones").value == "3"  # un conteo no lleva unidad
    assert metric(app, "Cobertura").value.endswith("%")


# --------------------------------------------- las cifras no cambian con el rediseño
def test_displayed_indicators_equal_the_analytics_output_for_the_same_period(monkeypatch):
    start, end = date(2026, 10, 20), date(2026, 10, 23)
    app = set_custom_period(run(monkeypatch), start, end)
    period = resolve_period("Rango personalizado", NOW, start, end)
    manual = summarize_manual(filter_points(manual_points(manual_records()), period), 70, 180)
    history = consolidate_history(libre_readings())
    from glucosa.analytics.glucose_sensor import SensorSample

    samples = [SensorSample(r.instant_utc, r.glucose_mg_dl) for r in history.readings]
    sensor = summarize_sensor(samples, period, 70, 180)

    shown = {(k.label, i): k.value for i, k in enumerate(kpis(app))}
    assert shown[("Mediciones", 1)] == str(manual.count)
    assert shown[("Promedio", 2)] == f"{manual.mean:.0f} mg/dL"
    assert shown[("Lecturas", 6)] == str(sensor.count)
    assert shown[("Promedio", 7)] == f"{sensor.mean:.0f} mg/dL"
    assert shown[("Cobertura", 11)] == f"{sensor.tir.coverage:.0%}"


# -------------------------------------------------------------- encabezado compacto
def test_header_shows_period_range_and_the_state_and_last_update_of_each_source(monkeypatch):
    app = run(monkeypatch)
    line = next(m.value for m in app.markdown if "Período:" in str(m.value))

    assert "Rango objetivo:** 70–180 mg/dL" in line
    assert "Firebase" in line and "disponible" in line and "consulta 26-10-2026 14:55" in line
    assert "LibreView" in line and "importación 26-10-2026 15:00" in line  # hora de Santiago
    assert "Base de fuego" not in texts(app.markdown) + texts(app.caption) + texts(app.subheader)


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("no_session", "sin sesión"),
        ("firebase_error", "con error"),
        ("libre_empty", "sin datos"),
        ("libre_error", "con error"),
    ],
)
def test_header_reports_when_a_source_is_not_available(monkeypatch, scenario, expected):
    app = run(monkeypatch, scenario)
    line = next(m.value for m in app.markdown if "Período:" in str(m.value))
    assert expected in line


def test_the_header_does_not_claim_a_query_time_when_firebase_failed(monkeypatch):
    line = next(
        m.value for m in run(monkeypatch, "firebase_error").markdown if "Período:" in str(m.value)
    )
    assert "consulta" not in line


def test_source_details_are_inside_a_collapsible_section(monkeypatch):
    app = run(monkeypatch)
    labels = [e.label for e in app.expander]

    assert "Detalle de las fuentes" in labels and "Importar un CSV de LibreView" in labels


# --------------------------------------------------- filtro de momento compacto
def moment_widget(app):
    return app.sidebar.multiselect(key="glucosa_momentos")


def test_the_moment_filter_starts_with_everything_selected_including_no_moment(monkeypatch):
    app = run(monkeypatch)
    options = moment_widget(app).options

    assert len(options) == 10 and "Sin momento declarado" in options
    assert moment_widget(app).value == options


def test_clear_selection_and_select_all_buttons_work(monkeypatch):
    app = run(monkeypatch)

    app.sidebar.button(key="glucosa_momentos_ninguno").click()
    app.run()
    assert moment_widget(app).value == []
    assert len(metrics_count(app, "Mediciones")) == 0  # sin momentos no hay mediciones de Firebase

    app.sidebar.button(key="glucosa_momentos_todos").click()
    app.run()
    assert moment_widget(app).value == moment_widget(app).options
    assert metric(app, "Mediciones").value == "3"


def popover_labels(app) -> list[str]:
    return [p.proto.popover.label for p in app.sidebar.get("popover")]


def metrics_count(app, label):
    return [k for k in kpis(app) if k.label == label]


def test_the_moment_filter_summarises_the_selection_in_its_button(monkeypatch):
    app = run(monkeypatch)
    labels = popover_labels(app)
    assert "Momento declarado: todos" in labels

    options = moment_widget(app).options
    moment_widget(app).set_value(options[:3])
    app.run()
    assert "Momento declarado: 3 de 10" in popover_labels(app)


def test_the_moment_filter_does_not_change_the_sensor_indicators(monkeypatch):
    app = run(monkeypatch)
    before = [k.value for k in kpis(app)[6:]]

    app.sidebar.button(key="glucosa_momentos_ninguno").click()
    app.run()

    assert [k.value for k in kpis(app)] == before  # solo quedan los del sensor, idénticos


# ----------------------------------------------------------- contador de registros
def counter(app) -> tuple[int, int]:
    text = next(m.value for m in app.markdown if "Registros mostrados" in str(m.value))
    shown, total = text.split("Registros mostrados:")[1].split("**")[0].split(" de ")
    return int(shown), int(total)


def test_counter_shows_displayed_records_over_available_records_and_matches_the_table(
    monkeypatch,
):
    app = run(monkeypatch)
    shown, total = counter(app)

    assert shown == len(table(app))
    assert total > shown  # los escaneos están ocultos por defecto pero cuentan como disponibles
    assert "escaneos ocultos: 1" in texts(app.markdown)


def test_showing_scans_raises_the_displayed_count_to_the_available_total(monkeypatch):
    app = run(monkeypatch)
    _, total = counter(app)

    app.sidebar.checkbox(key="glucosa_escaneos").set_value(True)
    app.run()

    assert counter(app) == (total, total)
    assert "escaneos ocultos" not in texts(app.markdown)


def test_display_filters_change_the_displayed_count_but_not_the_available_total(monkeypatch):
    app = run(monkeypatch)
    shown, total = counter(app)

    app.sidebar.multiselect(key="glucosa_clasificacion").set_value(["Sobre el rango"])
    app.run()
    shown_filtered, total_filtered = counter(app)

    assert shown_filtered < shown and total_filtered == total
    assert shown_filtered == len(table(app))


def test_search_changes_the_displayed_count(monkeypatch):
    app = run(monkeypatch)
    _, total = counter(app)

    app.text_input(key="glucosa_buscar").set_value("después almuerzo")
    app.run()

    shown, total_after = counter(app)
    assert 0 < shown < total and total_after == total


def test_the_classification_column_uses_color_badges_and_the_table_keeps_its_rules(monkeypatch):
    frame = table(run(monkeypatch))
    assert set(frame["Clasificación"]) <= {
        "🔴 Bajo el rango",
        "🟢 Dentro del rango",
        "🟠 Sobre el rango",
    }
    low = frame[frame["Glucosa (mg/dL)"] < 70]
    high = frame[frame["Glucosa (mg/dL)"] > 180]
    assert set(low["Clasificación"]) <= {"🔴 Bajo el rango"}
    assert set(high["Clasificación"]) <= {"🟠 Sobre el rango"}


# --------------------------------------------------------------- resumen por momento
def test_moment_summary_uses_short_headers_and_explains_units_and_percentages(monkeypatch):
    app = run(monkeypatch)
    summary = next(d.value for d in app.dataframe if "Momento declarado" in d.value.columns)

    assert list(summary.columns) == [
        "Momento declarado",
        "Mediciones",
        "Promedio",
        "Mediana",
        "Mín.",
        "Máx.",
        "% en rango",
    ]
    assert "mg/dL" in texts(app.caption) and "no es tiempo en rango" in texts(app.caption)
    assert "no se infiere desde Alimentación" in texts(app.caption)
