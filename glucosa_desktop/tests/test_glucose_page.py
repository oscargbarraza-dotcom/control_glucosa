"""Página Glucosa de punta a punta con fuentes simuladas (Streamlit AppTest, sin red ni datos reales)."""

import html
import json
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from glucosa.errors import SecureStoreError

TESTS = Path(__file__).resolve().parent
SCRIPT = TESTS / "glucose_app_for_tests.py"
IMPORT_SCRIPT = TESTS / "glucose_import_app.py"


def run(monkeypatch, scenario="full", script=SCRIPT) -> AppTest:
    monkeypatch.setenv("GLUCOSA_TEST_SCENARIO", scenario)
    return AppTest.from_file(str(script), default_timeout=60).run()


def texts(elements) -> str:
    return " | ".join(str(e.value) for e in elements)


_KPI = re.compile(
    r'<div class="kpi"[^>]*><div class="kpi-label">(.*?)</div><div class="kpi-value">(.*?)</div></div>'
)


def kpis(app: AppTest) -> list:
    """Todas las tarjetas de indicadores de la página, en orden (etiqueta y valor con unidad)."""
    cards = []
    for element in app.get("html"):
        body = element.proto.body
        if "kpi-grid" not in body:
            continue
        for label, value in _KPI.findall(body):
            text = " ".join(re.sub(r"<[^>]+>", " ", value).split())
            cards.append(SimpleNamespace(label=html.unescape(label), value=html.unescape(text)))
    return cards


def metrics(app: AppTest, label: str) -> list:
    return [k for k in kpis(app) if k.label == label]


def metric(app: AppTest, label: str):
    return metrics(app, label)[0]


def figures(app: AppTest) -> list[dict]:
    return [json.loads(e.proto.spec) for e in app.get("plotly_chart")]


def titled(app: AppTest) -> list[str]:
    return [f["layout"]["title"]["text"] for f in figures(app) if f["layout"].get("title")]


def trace_names(app: AppTest) -> set[str]:
    return {t.get("name") for fig in figures(app) for t in fig["data"]}


def evolution(app: AppTest) -> dict:
    return next(f for f in figures(app) if any("Sensor" in str(t.get("name")) for t in f["data"]))


def sensor_points_in_chart(app: AppTest) -> int:
    sensor = next(t for t in evolution(app)["data"] if "Sensor" in str(t["name"]))
    return sum(y is not None for y in sensor["y"])


def pick_source(app: AppTest, label: str) -> AppTest:
    app.sidebar.radio(key="glucosa_fuente").set_value(label)
    return app.run()


def set_custom_period(app: AppTest, start: date, end: date) -> AppTest:
    app.sidebar.selectbox(key="glucosa_periodo").set_value("Rango personalizado")
    app.run()
    app.sidebar.date_input(key="glucosa_fechas").set_value((start, end))
    return app.run()


def table(app: AppTest):
    return app.dataframe[-1].value


# --------------------------------------------------------------- estructura
def test_page_renders_both_sources_with_separate_headings_and_no_errors(monkeypatch):
    app = run(monkeypatch)
    assert not app.exception
    assert app.header[0].value == "Glucosa"
    headings = texts(app.subheader)
    assert "Mediciones manuales · Firebase" in headings
    assert "Sensor FreeStyle Libre · LibreView" in headings
    assert "Evolución temporal" in headings and "Detalle de registros" in headings


def test_manual_and_sensor_indicators_are_separate_and_labelled(monkeypatch):
    app = run(monkeypatch)
    labels = [m.label for m in kpis(app)]
    for expected in (
        "Última",
        "Mediciones",
        "Lecturas",
        "Cobertura",
    ):
        assert expected in labels
    assert metric(app, "Mediciones").value == "3"
    assert any("porcentaje de mediciones manuales" in t.lower() for t in titled(app))


def test_manual_percentages_are_never_called_time_in_range(monkeypatch):
    app = run(monkeypatch)
    assert any("no es tiempo en rango" in t.lower() for t in titled(app))


# ------------------------------------------------------- TIR y datos insuficientes
def test_default_30_day_period_has_low_sensor_coverage_so_tir_is_not_shown(monkeypatch):
    app = run(monkeypatch)
    assert "Datos insuficientes" in texts(app.warning)
    assert not any("estimado" in t.lower() for t in titled(app))


def test_with_enough_coverage_the_estimated_tir_is_shown_with_visible_coverage(monkeypatch):
    app = set_custom_period(run(monkeypatch), date(2026, 10, 20), date(2026, 10, 23))
    assert not app.exception
    assert any(
        "estimado" in t.lower() and "libreview" in t.lower() and "cobertura" in t.lower()
        for t in titled(app)
    )
    assert metric(app, "Cobertura").value.endswith("%")
    assert "Datos insuficientes" not in texts(app.warning)


def test_custom_period_with_only_one_date_asks_for_the_end_date_and_does_not_fail(monkeypatch):
    app = run(monkeypatch)
    app.sidebar.selectbox(key="glucosa_periodo").set_value("Rango personalizado")
    app.run()
    app.sidebar.date_input(key="glucosa_fechas").set_value((date(2026, 10, 20),))
    app.run()

    assert not app.exception
    assert "fecha de fin" in texts(app.sidebar.info)
    assert len(kpis(app)) == 0  # sin período completo no se muestra ningún indicador


# --------------------------------------------------------------- escenarios
def test_without_a_firebase_session_the_page_explains_it_and_still_shows_the_sensor(monkeypatch):
    app = run(monkeypatch, "no_session")
    assert not app.exception
    assert "glucosa.login" in texts(app.warning)
    assert "Sensor FreeStyle Libre · LibreView" in texts(app.subheader)


def test_empty_state_messages_say_what_actually_happened(monkeypatch):
    no_session = run(monkeypatch, "no_session")
    assert "No se pudieron cargar las mediciones de Firebase" in texts(no_session.info)
    assert "Sin mediciones manuales" not in texts(no_session.info)

    libre_error = run(monkeypatch, "libre_error")
    assert "No se pudo leer la base local de LibreView" in texts(libre_error.info)
    assert "importa un CSV" not in texts(libre_error.info)


def test_empty_libreview_invites_to_import_once_and_still_shows_manual_measurements(monkeypatch):
    app = run(monkeypatch, "libre_empty")
    assert not app.exception
    invitations = [i for i in app.info if "importa un csv" in str(i.value).lower()]
    assert len(invitations) == 1
    assert metric(app, "Mediciones").value == "3"


def test_libreview_error_is_reported_without_breaking_the_page(monkeypatch):
    app = run(monkeypatch, "libre_error")
    assert not app.exception
    assert "No se pudo abrir la base" in texts(app.error)
    assert metric(app, "Mediciones").value == "3"


# ------------------------------------------------------------------ filtros
def test_source_filter_shows_only_the_selected_source(monkeypatch):
    app = run(monkeypatch)
    firebase_only = pick_source(app, "Firebase (manual)")
    assert "Sensor FreeStyle Libre" not in texts(firebase_only.subheader)
    assert "Mediciones manuales" in texts(firebase_only.subheader)

    app = run(monkeypatch)
    libre_only = pick_source(app, "LibreView (sensor)")
    assert "Mediciones manuales · Firebase" not in texts(libre_only.subheader)
    assert "Sensor FreeStyle Libre" in texts(libre_only.subheader)


def test_chart_distinguishes_both_sources_in_its_legend(monkeypatch):
    names = trace_names(run(monkeypatch))
    assert {"Manual Firebase", "Sensor LibreView"} <= names


def test_classification_filter_changes_chart_and_table_but_not_any_period_indicator(monkeypatch):
    app = run(monkeypatch)
    rows_before = len(table(app))
    chart_points_before = sensor_points_in_chart(app)
    indicators_before = {
        label: metric(app, label).value
        for label in ("Mediciones", "Lecturas", "Cobertura", "Promedio")
    }

    app.sidebar.multiselect(key="glucosa_clasificacion").set_value(["Sobre el rango"])
    app.run()

    assert len(table(app)) < rows_before
    assert sensor_points_in_chart(app) < chart_points_before
    for label, value in indicators_before.items():
        assert metric(app, label).value == value, label  # el período completo no cambia


def test_refresh_button_forces_a_new_query_to_firebase(monkeypatch):
    app = run(monkeypatch)
    sources = app.session_state["fuentes"]
    assert sources.manual_calls == 1
    app.run()
    assert sources.manual_calls == 1  # se sirve de la caché

    app.sidebar.button(key="glucosa_actualizar").click()
    app.run()
    assert sources.manual_calls == 2


def test_table_search_filters_rows(monkeypatch):
    app = run(monkeypatch)
    before = len(table(app))
    app.text_input(key="glucosa_buscar").set_value("después almuerzo")
    app.run()
    assert 0 < len(table(app)) < before


# ----------------------------------------------- M-5: «sin momento declarado»
def test_measurements_without_a_declared_moment_are_not_hidden_by_the_moment_filter(monkeypatch):
    app = run(monkeypatch, "unset_moment")
    assert metric(app, "Mediciones").value == "4"
    assert "Sin momento declarado" in app.sidebar.multiselect(key="glucosa_momentos").options

    selected = [o for o in app.sidebar.multiselect(key="glucosa_momentos").options if o != "Ahora"]
    app.sidebar.multiselect(key="glucosa_momentos").set_value(selected)
    app.run()
    assert metric(app, "Mediciones").value == "3"  # solo salió la de «Ahora»

    selected.remove("Sin momento declarado")
    app.sidebar.multiselect(key="glucosa_momentos").set_value(selected)
    app.run()
    assert metric(app, "Mediciones").value == "2"  # ahora también salió la sin momento


# ------------------------------------------------------ D-1: procedencia en Firebase
def test_imported_measurements_have_their_own_block_and_never_count_as_manual(monkeypatch):
    app = run(monkeypatch, "with_imported")

    assert not app.exception
    headings = texts(app.subheader)
    assert "Mediciones manuales · Firebase" in headings
    assert "Mediciones importadas · Firebase" in headings
    manual_count, imported_count = [m.value for m in metrics(app, "Mediciones")]
    assert manual_count == "3" and imported_count == "1"
    assert any(
        "importadas" in t.lower() and "no es tiempo en rango" in t.lower() for t in titled(app)
    )
    assert any("manuales" in t.lower() for t in titled(app))


def test_imported_block_is_absent_when_firebase_has_no_imported_records(monkeypatch):
    app = run(monkeypatch)
    assert "importadas" not in texts(app.subheader).lower()
    assert len(metrics(app, "Mediciones")) == 1


def test_imported_measurements_are_drawn_apart_and_labelled_in_the_table(monkeypatch):
    app = run(monkeypatch, "with_imported")

    assert "Importado Firebase" in trace_names(app)
    assert {"Medición manual", "Medición importada"} <= set(table(app)["Tipo de registro"])
    # No se tratan como sensor: la tabla las rotula con la fuente Firebase.
    imported_rows = table(app)[table(app)["Tipo de registro"] == "Medición importada"]
    assert set(imported_rows["Fuente"]) == {"🟣 Firebase"}


def test_imported_measurements_are_excluded_from_the_moment_summary(monkeypatch):
    app = run(monkeypatch, "with_imported")
    summary = next(d for d in app.dataframe if "Momento declarado" in d.value.columns)
    assert summary.value["Mediciones"].sum() == 3  # solo las manuales


# --------------------------------------------------------------- D-2: frescura
def test_the_page_separates_last_query_time_from_the_last_available_measurement(monkeypatch):
    app = run(monkeypatch)
    captions = texts(app.caption)

    assert "Última consulta exitosa a Firebase:** 26-10-2026 14:55" in captions
    assert "Última medición disponible:** 25-10-2026 09:30" in captions
    assert "no confirma" in captions and "sincronizado" in captions


def test_without_a_successful_query_no_freshness_claim_is_shown(monkeypatch):
    for scenario in ("no_session", "firebase_error"):
        app = run(monkeypatch, scenario)
        assert "Última consulta exitosa" not in texts(app.caption)


# ------------------------------------------------------------- D-3: escaneos
def test_scans_are_hidden_by_default_in_chart_and_table_with_one_control(monkeypatch):
    app = run(monkeypatch)
    assert "Escaneo LibreView" not in trace_names(app)
    assert "Escaneo del sensor" not in set(table(app)["Tipo de registro"])
    assert not app.sidebar.checkbox(key="glucosa_escaneos").value


def test_the_scan_control_shows_scans_in_chart_and_table_without_touching_the_indicators(
    monkeypatch,
):
    app = run(monkeypatch)
    before = {m.label: m.value for m in kpis(app)}

    app.sidebar.checkbox(key="glucosa_escaneos").set_value(True)
    app.run()

    assert "Escaneo LibreView" in trace_names(app)
    assert "Escaneo del sensor" in set(table(app)["Tipo de registro"])
    assert {m.label: m.value for m in kpis(app)} == before  # escaneos fuera de los indicadores


# -------------------------------------------------- A-1: deduplicación entre dispositivos
def tir_figures(app: AppTest):
    return [
        f
        for f in figures(app)
        if f["layout"].get("title") and "TIR" in f["layout"]["title"]["text"]
    ]


def test_the_same_series_read_by_two_devices_is_counted_once_everywhere(monkeypatch):
    single = set_custom_period(run(monkeypatch), date(2026, 10, 20), date(2026, 10, 23))
    doubled = set_custom_period(
        run(monkeypatch, "two_devices"), date(2026, 10, 20), date(2026, 10, 23)
    )

    for label in ("Lecturas", "Cobertura", "Promedio", "Mediana"):
        assert metric(doubled, label).value == metric(single, label).value, label
    assert sensor_points_in_chart(doubled) == sensor_points_in_chart(single)
    assert len(table(doubled)) == len(table(single))
    assert "se contaron una sola vez" in texts(doubled.caption)
    assert tir_figures(doubled) == tir_figures(single)  # TIR y cobertura idénticos


def test_duplicates_do_not_let_a_short_series_pass_the_minimum_readings_gate(monkeypatch):
    app = set_custom_period(run(monkeypatch, "two_devices"), date(2026, 10, 20), date(2026, 10, 20))
    # un solo día parcial: con lecturas duplicadas parecería haber el doble
    assert int(metric(app, "Lecturas").value) <= 96


def test_same_minute_with_different_values_is_reported_and_never_merged(monkeypatch):
    app = set_custom_period(
        run(monkeypatch, "device_conflict"), date(2026, 10, 20), date(2026, 10, 23)
    )

    assert "valores distintos entre dispositivos" in texts(app.warning)
    assert "no se fusionaron" in texts(app.warning)


# --------------------------------------------------- M-1: actualizar al importar
def test_indicators_update_immediately_after_importing(monkeypatch):
    app = set_custom_period(
        run(monkeypatch, script=IMPORT_SCRIPT), date(2026, 10, 20), date(2026, 10, 28)
    )
    before = int(metric(app, "Lecturas").value)

    app.sidebar.button(key="simular").click()
    app.run()

    assert not app.exception
    assert int(metric(app, "Lecturas").value) > before
    assert "Importación completa" in texts(app.success)
    assert app.session_state["fuentes"].imported == ["x.csv"]


# ----------------------------------- M-2 / M-3: los errores no quedan como resultados válidos
def test_logging_in_after_a_no_session_state_is_noticed_without_waiting(monkeypatch):
    app = run(monkeypatch, "no_session")
    assert "glucosa.login" in texts(app.warning) and len(metrics(app, "Mediciones")) == 0

    app.session_state["fuentes"].marker = "marcador-nuevo"  # el usuario inició sesión por CLI
    app.run()

    assert metric(app, "Mediciones").value == "3"
    assert "glucosa.login" not in texts(app.warning)


def test_logging_out_discards_the_cached_firebase_data(monkeypatch):
    app = run(monkeypatch)
    assert metric(app, "Mediciones").value == "3"

    app.session_state["fuentes"].marker = None  # cerraron sesión por la línea de comandos
    app.run()

    assert len(metrics(app, "Mediciones")) == 0
    assert "glucosa.login" in texts(app.warning)


def test_switching_account_discards_the_previous_users_cached_data(monkeypatch):
    app = run(monkeypatch)
    sources = app.session_state["fuentes"]
    assert sources.manual_calls == 1

    sources.marker = "otra-cuenta"
    app.run()

    assert sources.manual_calls == 2


def test_a_firebase_error_is_retried_soon_instead_of_being_cached_for_minutes(monkeypatch):
    from glucosa.ui import glucose_page

    clock = {"now": 1000.0}
    monkeypatch.setattr(glucose_page.time, "monotonic", lambda: clock["now"])
    app = run(monkeypatch, "firebase_error")
    sources = app.session_state["fuentes"]
    assert "Sin conexión con Firebase" in texts(app.warning) and sources.manual_calls == 1

    app.run()
    assert sources.manual_calls == 1  # dentro de unos segundos no se insiste
    clock["now"] += glucose_page.ERROR_TTL_SECONDS + 1
    app.run()
    assert sources.manual_calls == 2  # pasado ese plazo se reintenta


def test_a_successful_firebase_read_is_cached_for_the_normal_ttl(monkeypatch):
    from glucosa.ui import glucose_page

    clock = {"now": 1000.0}
    monkeypatch.setattr(glucose_page.time, "monotonic", lambda: clock["now"])
    app = run(monkeypatch)
    sources = app.session_state["fuentes"]

    clock["now"] += glucose_page.ERROR_TTL_SECONDS + 1
    app.run()
    assert sources.manual_calls == 1
    clock["now"] += glucose_page.MANUAL_TTL_SECONDS
    app.run()
    assert sources.manual_calls == 2


def test_a_transient_libreview_error_is_not_cached_until_the_file_changes(monkeypatch):
    app = run(monkeypatch, "libre_flaky")
    assert "El archivo está en uso" in texts(app.error)
    assert len(metrics(app, "Lecturas")) == 0

    app.run()  # el archivo no cambió, pero el error no debe quedar pegado

    assert not app.error
    assert len(metrics(app, "Lecturas")) == 1
    assert app.session_state["fuentes"].libre_calls == 2


# ----------------------------------------- M-6 / M-7: rango objetivo y ajustes locales
def test_target_range_validation_and_saving(monkeypatch):
    app = run(monkeypatch)
    app.sidebar.number_input(key="glucosa_min").set_value(200)
    app.run()
    assert "mínimo del rango objetivo" in texts(app.error)

    app = run(monkeypatch)
    app.sidebar.number_input(key="glucosa_min").set_value(80)
    app.run()
    app.sidebar.button(key="glucosa_guardar_rango").click()
    app.run()
    assert app.session_state["fuentes"].saved_range == (80, 180)


def test_a_failure_saving_the_range_is_shown_as_a_message_not_a_crash(monkeypatch):
    app = run(monkeypatch)
    app.session_state["fuentes"].save_error = SecureStoreError("No se guardó: ajustes ilegibles.")
    app.sidebar.number_input(key="glucosa_min").set_value(80)
    app.run()

    app.sidebar.button(key="glucosa_guardar_rango").click()
    app.run()

    assert not app.exception
    assert "No se guardó: ajustes ilegibles." in texts(app.error)


def test_the_default_range_is_never_used_silently(monkeypatch):
    assert "Sin sesión de Firebase" in texts(run(monkeypatch, "no_session").sidebar.warning)
    assert not run(monkeypatch).sidebar.warning


# ------------------------------------------------------------------- tabla
def test_table_has_requested_columns_source_badges_and_no_technical_ids(monkeypatch):
    app = run(monkeypatch)
    app.sidebar.checkbox(key="glucosa_escaneos").set_value(True)
    app.run()
    frame = table(app)
    assert list(frame.columns) == [
        "Fecha y hora",
        "Glucosa (mg/dL)",
        "Fuente",
        "Tipo de registro",
        "Momento declarado",
        "Observaciones",
        "Clasificación",
    ]
    assert set(frame["Fuente"]) == {"🟣 Firebase", "🔵 LibreView"}
    assert {"Medición manual", "Historial del sensor", "Escaneo del sensor"} <= set(
        frame["Tipo de registro"]
    )
    assert not any(
        token in " ".join(frame.columns).lower() for token in ("uuid", "dispositivo", "serie")
    )


@pytest.mark.parametrize(
    "scenario",
    [
        "full",
        "no_session",
        "libre_empty",
        "libre_error",
        "with_imported",
        "unset_moment",
        "two_devices",
        "device_conflict",
        "firebase_error",
        "libre_flaky",
    ],
)
def test_every_scenario_ends_without_exceptions(monkeypatch, scenario):
    assert not run(monkeypatch, scenario).exception


# ------------------------------------------------------------------ exportaciones
def test_every_chart_is_sent_without_the_png_download_button(monkeypatch):
    app = set_custom_period(run(monkeypatch), date(2026, 10, 20), date(2026, 10, 23))
    app.sidebar.checkbox(key="glucosa_escaneos").set_value(True)
    app.run()

    charts = app.get("plotly_chart")
    assert len(charts) >= 3
    for element in charts:
        config = json.loads(element.proto.config)
        assert "toImage" in config["modeBarButtonsToRemove"]


def test_the_csv_uploader_is_renewed_after_importing_so_the_file_leaves_memory(monkeypatch):
    app = run(monkeypatch, script=IMPORT_SCRIPT)
    assert "glucosa_csv_nonce" not in app.session_state

    app.sidebar.button(key="simular").click()
    app.run()

    assert app.session_state["glucosa_csv_nonce"] == 1
