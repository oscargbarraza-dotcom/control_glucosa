"""Página Alimentación de punta a punta con fuentes simuladas (AppTest, sin red ni datos reales)."""

import html
import json
import re
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

SCRIPT = Path(__file__).resolve().parent / "meal_app_for_tests.py"
# 21:30 locales del 25-10-2026: la última comida (21:00) aún tiene sus hitos pendientes.
EARLY_NOW = "2026-10-26T00:30:00+00:00"
_KPI = re.compile(
    r'<div class="kpi"[^>]*><div class="kpi-label">(.*?)</div><div class="kpi-value">(.*?)</div></div>'
)


def run(monkeypatch, scenario="full", now=None) -> AppTest:
    monkeypatch.setenv("GLUCOSA_TEST_SCENARIO", scenario)
    if now:
        monkeypatch.setenv("GLUCOSA_TEST_NOW", now)
    return AppTest.from_file(str(SCRIPT), default_timeout=60).run()


@pytest.fixture
def app(monkeypatch):
    return run(monkeypatch)


def cards(app: AppTest) -> dict[str, str]:
    found = {}
    for element in app.get("html"):
        body = element.proto.body
        if "kpi-grid" not in body:
            continue
        for label, value in _KPI.findall(body):
            text = " ".join(re.sub(r"<[^>]+>", " ", value).split())
            found[html.unescape(label)] = html.unescape(text)
    return found


def figures(app: AppTest) -> dict[str, dict]:
    return {e.proto.id: json.loads(e.proto.spec) for e in app.get("plotly_chart")}


def title_of(figure: dict) -> str:
    return (figure["layout"].get("title") or {}).get("text", "")


def texts(app: AppTest) -> str:
    elements = [*app.markdown, *app.caption, *app.info, *app.warning, *app.error, *app.text]
    return " | ".join(str(e.value) for e in elements)


def frames(app: AppTest) -> dict[str, object]:
    return {"/".join(df.value.columns[:2]): df.value for df in app.dataframe}


def meals_frame(app: AppTest):
    return next(df.value for df in app.dataframe if "Fecha y hora" in df.value.columns)


# ----------------------------------------------------------------------- estructura
def test_the_page_renders_without_exceptions_and_with_the_expected_sections(app):
    assert not app.exception
    assert app.header[0].value == "Alimentación"
    subheaders = [s.value for s in app.subheader]
    assert any(s.startswith("Comida individual") for s in subheaders)
    assert "Detalle de comidas y mediciones cercanas" in subheaders


def test_the_status_line_names_the_period_and_the_three_sources(app):
    line = app.markdown[0].value

    assert "Período" in line and "Comidas · Firebase" in line
    assert "Mediciones · Firebase" in line and "LibreView" in line


# ----------------------------------------------------------------------------- KPI
def test_meal_kpis_count_meals_days_average_and_distinct_foods(app):
    found = cards(app)

    assert found["Comidas"] == "6"
    assert found["Días registrados"] == "4"  # 21, 22, 23 y 25 de octubre
    assert found["Promedio por día"] == "1.5"  # sobre días CON registros: 6 / 4
    assert int(found["Alimentos distintos"]) >= 6


def test_milestone_kpis_show_measured_eligible_and_pending_separately(app):
    found = cards(app)

    for minutes in (60, 90):
        assert f"Manual +{minutes}" in found
        assert found[f"Elegibles +{minutes}"] == "6"
        assert found[f"Pendientes +{minutes}"] == "0"
    assert re.fullmatch(r"\d+ de 6", found["Manual +60"])


def test_pending_milestones_are_not_counted_as_eligible_nor_as_missing(monkeypatch):
    found = cards(run(monkeypatch, now=EARLY_NOW))

    assert found["Pendientes +60"] == "1" and found["Pendientes +90"] == "1"
    assert found["Elegibles +60"] == "5" and found["Elegibles +90"] == "5"


def test_the_kpis_are_descriptive_and_never_talk_about_compliance(app):
    for text in texts(app).split(" | "):
        if "cumplimiento" in text:
            assert "no indica cumplimiento" in text
    assert "cumple" not in texts(app).lower().replace("cumplimiento", "")


def test_imported_kpis_appear_only_when_there_are_imported_measurements(monkeypatch):
    assert "Importada +60" not in cards(run(monkeypatch))

    with_imported = cards(run(monkeypatch, "with_imported"))
    assert with_imported["Importada +60"] and with_imported["Eleg. imp. +60"]


# ------------------------------------------------------------------------- gráficos
def test_the_page_draws_the_four_distributions_and_the_individual_meal_chart(app):
    titles = [title_of(f) for f in figures(app).values()]

    assert len(titles) == 5
    assert any("tipo" in t.lower() for t in titles)
    assert any("hora" in t.lower() for t in titles)
    assert any("alimento" in t.lower() for t in titles)
    assert any("día" in t.lower() for t in titles)


def test_user_markup_in_food_names_never_reaches_the_charts(app):
    payload = json.dumps(list(figures(app).values()), ensure_ascii=False)

    assert "<b>Pan</b>" not in payload


# ------------------------------------------------------------------------- filtros
def test_the_type_filter_narrows_the_population(app):
    app.multiselect(key="alimentacion_tipos").set_value(["Desayuno"]).run()

    assert cards(app)["Comidas"] == "2"
    assert "Comidas mostradas: 2 de 2" in texts(app)


def test_the_food_filter_keeps_meals_containing_any_selected_food(app):
    options = list(app.multiselect(key="alimentacion_alimentos").options)
    assert "Pan" in options

    app.multiselect(key="alimentacion_alimentos").set_value(["Pan"]).run()

    # «Pan» está en 2 comidas; «<b>Pan</b>» es otro alimento y no se mezcla con él.
    assert not app.exception and cards(app)["Comidas"] == "2"


def test_the_period_filter_changes_the_population(app):
    app.selectbox(key="alimentacion_periodo").set_value("Hoy").run()

    assert cards(app)["Comidas"] == "0"
    assert "No hay comidas con los filtros elegidos." in texts(app)


def test_a_custom_date_range_selects_whole_local_days(app):
    app.selectbox(key="alimentacion_periodo").set_value("Rango personalizado").run()
    app.date_input(key="alimentacion_fechas").set_value(
        (date(2026, 10, 21), date(2026, 10, 22))
    ).run()

    assert not app.exception and cards(app)["Comidas"] == "4"


def test_an_incomplete_custom_range_asks_for_the_end_date_and_shows_no_data(app):
    app.selectbox(key="alimentacion_periodo").set_value("Rango personalizado").run()
    app.date_input(key="alimentacion_fechas").set_value((date(2026, 10, 21),)).run()

    assert not app.exception and not cards(app)
    assert any("fecha de fin" in i.value for i in app.sidebar.info)


def window_chart(app: AppTest) -> dict:
    return next(
        f
        for f in figures(app).values()
        if (f["layout"].get("xaxis", {}).get("title", {}).get("text") or "").startswith("Minutos")
    )


def test_the_glucose_source_filter_removes_that_source_from_the_table_and_the_chart(app):
    app.selectbox(key="alimentacion_comida").select_index(4).run()  # con lecturas del sensor
    assert any(t.get("name") == "Sensor LibreView" for t in window_chart(app)["data"])

    app.multiselect(key="alimentacion_fuentes").set_value(["Manual (Firebase)"]).run()

    assert not any("sensor" in c.lower() for c in meals_frame(app).columns)
    assert all(t.get("name") != "Sensor LibreView" for t in window_chart(app)["data"])


def test_visualization_filters_limit_the_table_but_not_the_indicators(app):
    app.selectbox(key="alimentacion_disponibilidad").set_value("Sin ninguna medición cercana").run()
    shown = meals_frame(app)

    assert cards(app)["Comidas"] == "6"
    assert len(shown) < 6
    assert all(v.startswith("Sin mediciones") for v in shown["Datos de glucosa"])
    assert f"Comidas mostradas: {len(shown)} de 6" in texts(app)


def test_the_isolated_only_filter_hides_meals_that_share_windows(app):
    everything = len(meals_frame(app))

    app.checkbox(key="alimentacion_aisladas").set_value(True).run()

    assert 0 < len(meals_frame(app)) < everything and cards(app)["Comidas"] == "6"


def test_the_tolerance_control_is_bounded_and_reaches_the_milestone_tables(app):
    widget = app.number_input(key="alimentacion_tolerancia")
    assert (widget.min, widget.max, widget.value) == (5, 20, 10)

    widget.set_value(15).run()

    assert not app.exception
    milestones = next(df.value for df in app.dataframe if "Hito" in df.value.columns)
    assert set(milestones["Tolerancia"]) == {"±15 min"}


# ------------------------------------------------------------- comida individual
def test_the_selector_lists_meals_newest_first_and_defaults_to_the_latest(app):
    selector = app.selectbox(key="alimentacion_comida")

    assert selector.options[0].startswith("25-10-2026 21:00")
    assert selector.options[-1].startswith("21-10-2026 09:30")
    assert len(selector.options) == 6


def test_choosing_another_meal_redraws_the_window_chart_and_flags_shared_windows(app):
    selector = app.selectbox(key="alimentacion_comida")
    selector.select_index(4).run()  # 21-10 13:30: cerca de otra comida a 13:50

    assert not app.exception
    assert "Ventana compartida con" in " ".join(w.value for w in app.warning)
    notes = " ".join(a["text"] for a in window_chart(app)["layout"].get("annotations", []))
    assert "Otra comida" in notes


def test_a_meal_without_glucose_stays_selectable_and_says_so(app):
    app.selectbox(key="alimentacion_comida").select_index(0).run()  # 25-10: fuera del export

    assert not app.exception
    notes = " ".join(a["text"] for a in window_chart(app)["layout"].get("annotations", [])).lower()
    assert "sin mediciones" in notes


def test_the_selected_meals_free_text_is_shown_as_plain_text(app):
    shown = " ".join(t.value for t in app.text)

    assert "Comentario: texto libre" in shown  # la última comida


def test_the_selection_resets_when_the_chosen_meal_no_longer_passes_the_filters(app):
    app.selectbox(key="alimentacion_comida").select_index(5).run()
    app.multiselect(key="alimentacion_tipos").set_value(["Cena"]).run()

    assert not app.exception
    assert app.selectbox(key="alimentacion_comida").options  # sigue habiendo una comida elegible


# ------------------------------------------------------------------------- tablas
def test_the_detail_table_has_every_meal_with_reference_milestones_and_coverage(app):
    frame = meals_frame(app)

    assert len(frame) == 6
    for column in ("Previa (manual)", "Referencia (manual)", "+60 (manual)", "+90 (manual)"):
        assert column in frame.columns
    assert "Sensor posterior (cobertura)" in frame.columns
    assert "Sin mediciones cercanas de las fuentes elegidas" in set(frame["Datos de glucosa"])


def test_the_detail_table_pins_date_type_and_foods_and_drops_no_column(app):
    element = next(e for e in app.dataframe if "Fecha y hora" in e.value.columns)
    config = json.loads(element.proto.columns)

    pinned = [name for name, c in config.items() if c.get("pinned")]
    assert pinned == ["Fecha y hora", "Tipo", "Alimentos"]
    assert set(element.value.columns) <= set(config)  # cada columna conserva su ancho
    assert all(c["width"] >= 95 for name, c in config.items() if name != "_index")


def test_the_sub_minute_reference_is_shown_in_seconds_never_as_zero_minutes(app):
    references = list(meals_frame(app)["Referencia (manual)"])

    assert not any("(0 min)" in text for text in references)


def test_the_export_notice_distinguishes_an_outdated_export_from_sensor_gaps(app):
    notice = " ".join(i.value for i in app.info)

    assert "export desactualizado" in notice.lower() and "no un hueco del sensor" in notice
    assert any("export fuera de cobertura" in str(v) for v in meals_frame(app)["+60 (sensor)"])


def test_the_coverage_table_lists_one_row_per_glucose_source(app):
    coverage = next(df.value for df in app.dataframe if "Con previa" in df.value.columns)

    assert list(coverage["Fuente"]) == [
        "Manual (Firebase)",
        "Importada (Firebase)",
        "Sensor (LibreView)",
    ]
    assert set(coverage["Comidas"]) == {6}


# ------------------------------------------------------------ estados de las fuentes
def test_without_a_firebase_session_the_page_explains_it_and_shows_no_data(monkeypatch):
    app = run(monkeypatch, "no_session")

    assert not app.exception
    assert any("login" in w.value for w in app.warning)
    assert not app.dataframe and not cards(app)


def test_a_firebase_error_is_reported_without_breaking_the_page(monkeypatch):
    app = run(monkeypatch, "meals_error")

    assert not app.exception
    assert any("Sin conexión con Firebase" in w.value for w in app.warning)
    assert not app.dataframe


def test_with_no_meals_synced_the_page_says_so(monkeypatch):
    app = run(monkeypatch, "no_meals")

    assert not app.exception
    assert any("Aún no hay comidas" in i.value for i in app.info)


def test_rejected_documents_are_counted_not_hidden(monkeypatch):
    app = run(monkeypatch, "meals_rejected")

    assert any("1 documento(s) de comidas no pasaron la validación" in w.value for w in app.warning)


def test_without_libreview_data_meals_stay_visible_with_the_sensor_state(monkeypatch):
    app = run(monkeypatch, "libre_empty")

    frame = meals_frame(app)
    assert not app.exception and len(frame) == 6
    assert set(frame["+60 (sensor)"]) <= {"Sin datos del sensor", "No aplica"}
    assert any("Sin datos de LibreView" in i.value for i in app.info)


# ----------------------------------------------------------------------- caché
def test_reruns_reuse_the_cache_and_the_refresh_button_reads_again(app):
    sources = app.session_state["fuentes"]
    assert (sources.meal_calls, sources.manual_calls) == (1, 1)

    app.selectbox(key="alimentacion_disponibilidad").set_value("Con glucosa previa").run()
    assert sources.meal_calls == 1 and sources.manual_calls == 1

    app.sidebar.button(key="alimentacion_actualizar").click().run()
    assert sources.meal_calls == 2 and sources.manual_calls == 2


def test_the_page_is_read_only_it_never_asks_the_sources_to_write(app):
    sources = app.session_state["fuentes"]

    assert sources.saved_range is None and sources.imported == []
