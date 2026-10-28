"""Fuente de mediciones de Firebase: error de lectura, colección vacía y ausencia en la ventana.

Tres situaciones que nunca deben confundirse:

* **Fuente no disponible** — la lectura falló o no hay sesión: no se sabe si hay mediciones.
* **Sin mediciones en Firebase** — la lectura funcionó y la colección está vacía.
* **Sin medición manual registrada** — hay mediciones, pero ninguna cerca de ese hito.
"""

import re
from datetime import timedelta

import pytest

from glucosa.analytics.meal_dashboard import MilestoneKpi
from glucosa.analytics.meal_glucose import AssociationParams, associate_meals
from glucosa.analytics.meal_milestones import MilestoneParams
from glucosa.analytics.meal_readings import ReadingSource as S
from glucosa.ui.glucose_kpi import Tone
from glucosa.ui.glucose_sources import SourceStatus
from glucosa.ui.meal_kpi import milestone_groups, milestone_groups_html
from glucosa.ui.meal_labels import (
    EMPTY_TEXT,
    UNAVAILABLE_TEXT,
    FirebaseState,
    firebase_state,
    milestone_text,
)
from glucosa.ui.meal_table import availability_table, meals_table, milestones_table
from tests.meal_glucose_helpers import NOW, T0, inputs, manual, meals, sensor_run

A, E, U = FirebaseState.AVAILABLE, FirebaseState.EMPTY, FirebaseState.UNAVAILABLE
ALL = frozenset({S.MANUAL, S.IMPORTED, S.SENSOR})


def build(*readings, now=NOW, specs=(("a", 0),)):
    views = meals(*specs)
    association = associate_meals(
        views, inputs(*readings), now, AssociationParams(milestones=MilestoneParams(10))
    )
    return views, association


def table(*readings, firebase=A, sources=ALL, now=NOW, specs=(("a", 0),)):
    views, association = build(*readings, now=now, specs=specs)
    return meals_table(
        association.meals,
        {v.uuid: v for v in views},
        sources,
        has_imported=False,
        firebase=firebase,
    )


# ------------------------------------------------------------------------ estado
@pytest.mark.parametrize(
    ("status", "count", "expected"),
    [
        (SourceStatus.OK, 12, A),
        (SourceStatus.OK, 0, E),
        (SourceStatus.ERROR, 0, U),
        (SourceStatus.ERROR, 12, U),  # aunque queden datos en memoria, no se usan
        (SourceStatus.NO_SESSION, 0, U),
        (SourceStatus.SESSION_EXPIRED, 5, U),
        (SourceStatus.CONFIG, 0, U),
    ],
)
def test_the_state_comes_from_the_read_status_and_only_then_from_the_record_count(
    status, count, expected
):
    assert firebase_state(status, count) is expected


def test_the_three_texts_are_all_different():
    assert UNAVAILABLE_TEXT == "Fuente no disponible"
    assert EMPTY_TEXT == "Sin mediciones en Firebase"
    assert len({UNAVAILABLE_TEXT, EMPTY_TEXT, "Sin medición manual registrada"}) == 3


# ------------------------------------------------------------------- texto de hito
def milestone(source, minutes_offset=None, now=NOW):
    _, association = build(now=now)
    return association.meals[0].milestones[60][source]


def test_not_registered_reads_differently_in_each_of_the_three_situations():
    result = milestone(S.MANUAL)

    assert milestone_text(result, A) == "Sin medición manual registrada"
    assert milestone_text(result, E) == "Sin mediciones en Firebase"
    assert milestone_text(result, U) == "Fuente no disponible"


def test_a_pending_milestone_is_a_time_fact_and_stays_pending_in_every_state():
    result = milestone(S.MANUAL, now=T0 + timedelta(minutes=10))

    assert [milestone_text(result, s) for s in (A, E, U)] == ["Hito pendiente"] * 3


def test_the_sensor_texts_never_depend_on_the_firebase_state():
    result = milestone(S.SENSOR)

    assert {milestone_text(result, s) for s in (A, E, U)} == {milestone_text(result)}


def test_a_measured_milestone_is_never_shown_as_valid_when_the_source_is_unavailable():
    _, association = build(manual(61, 140))
    result = association.meals[0].milestones[60][S.MANUAL]

    assert milestone_text(result, A) == "140 mg/dL (+1 min del hito)"
    assert milestone_text(result, U) == "Fuente no disponible"


# ------------------------------------------------------------------ tabla de comidas
FIREBASE_COLUMNS = ["Previa (manual)", "Referencia (manual)", "+60 (manual)", "+90 (manual)"]


def test_unavailable_source_marks_every_firebase_cell_and_keeps_the_meals_visible():
    frame = table(*sensor_run(-120, 300), firebase=U, specs=(("a", 0), ("b", 1000)))

    assert len(frame) == 2
    for column in FIREBASE_COLUMNS:
        assert set(frame[column]) == {"Fuente no disponible"}


def test_empty_collection_says_so_in_every_firebase_cell():
    frame = table(firebase=E)

    for column in FIREBASE_COLUMNS:
        assert set(frame[column]) == {"Sin mediciones en Firebase"}


def test_absence_in_the_window_keeps_its_own_text_when_the_source_is_healthy():
    frame = table(manual(-500))  # hay mediciones, pero ninguna cerca

    assert frame.iloc[0]["Previa (manual)"] == "—"
    assert frame.iloc[0]["+60 (manual)"] == "Sin medición manual registrada"


def test_sensor_results_are_identical_whether_firebase_is_available_or_not():
    readings = sensor_run(-120, 300)
    healthy, failed = table(*readings, firebase=A), table(*readings, firebase=U)

    sensor_columns = [c for c in healthy.columns if "sensor" in c or c in ("Fecha y hora", "Tipo")]
    assert healthy[sensor_columns].equals(failed[sensor_columns])


def test_pending_milestones_stay_pending_while_the_source_is_down():
    frame = table(firebase=U, now=T0 + timedelta(minutes=10))

    assert frame.iloc[0]["+60 (manual)"] == "Hito pendiente"


def test_glucose_availability_column_names_the_unavailable_source():
    only_firebase = table(firebase=U, sources={S.MANUAL}).iloc[0]["Datos de glucosa"]
    with_sensor = table(*sensor_run(-120, 300), firebase=U).iloc[0]["Datos de glucosa"]
    no_readings = table(firebase=U).iloc[0]["Datos de glucosa"]

    assert only_firebase == "Fuente no disponible"
    assert with_sensor == "Con previa y posterior · sin Firebase"
    assert no_readings == "Fuente no disponible"


def test_a_healthy_empty_window_is_still_reported_as_having_no_nearby_measurements():
    assert table(firebase=A).iloc[0]["Datos de glucosa"].startswith("Sin mediciones")
    assert table(firebase=E).iloc[0]["Datos de glucosa"].startswith("Sin mediciones")


# ---------------------------------------------------------- hitos y cobertura
def test_milestones_table_marks_the_unavailable_source_and_leaves_the_sensor_alone():
    _, association = build(*sensor_run(-120, 300))
    outcome = association.meals[0]

    healthy = milestones_table(outcome, ALL, has_imported=False, firebase=A)
    failed = milestones_table(outcome, ALL, has_imported=False, firebase=U)

    assert set(failed["Manual (Firebase)"]) == {"Fuente no disponible"}
    assert failed["Sensor (LibreView)"].equals(healthy["Sensor (LibreView)"])
    assert set(failed["Tolerancia"]) == {"±10 min"}  # la tolerancia configurada se conserva


def test_coverage_table_drops_the_unavailable_firebase_rows_instead_of_showing_zeros():
    _, association = build(*sensor_run(-120, 300))

    failed = availability_table(association, firebase=U)
    empty = availability_table(association, firebase=E)
    healthy = availability_table(association, firebase=A)

    assert list(failed["Fuente"]) == ["Sensor (LibreView)"]
    assert list(empty["Fuente"]) == list(healthy["Fuente"]) and len(healthy) == 3
    assert empty.iloc[0]["Con previa"] == 0  # colección vacía: el cero es un resultado válido


# ---------------------------------------------------------------------- tarjetas
def kpis(**kw):
    values = dict(eligible=5, measured=3, not_registered=2, pending=1, tolerance=10)
    values.update(kw)
    return {
        minutes: MilestoneKpi(
            minutes,
            values["tolerance"],
            values["eligible"],
            values["measured"],
            values["not_registered"],
            values["pending"],
        )
        for minutes in (60, 90)
    }


def test_unavailable_source_replaces_the_numbers_with_one_explicit_card_per_milestone():
    groups = milestone_groups({S.MANUAL: kpis()}, firebase=U)

    assert [[(c.label, c.value) for c in g] for g in groups] == [
        [("Manual +60", "Fuente no disponible")],
        [("Manual +90", "Fuente no disponible")],
    ]
    html = milestone_groups_html(groups, Tone.FIREBASE)
    assert (
        not re.search(r"\d+ de \d+", html) and ">0<" not in html
    )  # ningún cero presentado como resultado


def test_empty_collection_has_its_own_card_text():
    groups = milestone_groups({S.MANUAL: kpis(eligible=0, measured=0)}, firebase=E)

    assert [g[0].value for g in groups] == ["Sin mediciones en Firebase"] * 2


def test_healthy_source_keeps_the_three_cards_with_their_numbers():
    groups = milestone_groups({S.MANUAL: kpis()}, firebase=A)

    assert [c.value for c in groups[0]] == ["3 de 5", "5", "1"]


def test_the_single_state_cards_use_the_full_group_width():
    html = milestone_groups_html(milestone_groups({S.MANUAL: kpis()}, firebase=U), Tone.FIREBASE)

    assert html.count('class="kpi-grid kpi-solo') == 2


def test_state_cards_explain_themselves_in_their_help():
    unavailable = milestone_groups({S.MANUAL: kpis()}, firebase=U)[0][0]
    empty = milestone_groups({S.MANUAL: kpis()}, firebase=E)[0][0]

    assert "no se pudo leer" in unavailable.tip.lower()
    assert "colección" in empty.tip.lower()
