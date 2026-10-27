"""Tablas de comidas y de mediciones cercanas (sin Streamlit)."""

import pytest

from glucosa.analytics.meal_glucose import AssociationParams, associate_meals
from glucosa.analytics.meal_milestones import MilestoneParams
from glucosa.analytics.meal_readings import ReadingSource as S
from glucosa.ui.meal_table import (
    PINNED_BUDGET_PX,
    PINNED_COLUMNS,
    availability_table,
    column_width,
    meals_table,
    milestones_table,
    nearby_readings_table,
)
from tests.meal_glucose_helpers import (
    NOW,
    imported,
    inputs,
    manual,
    meals,
    scan,
    sensor,
    sensor_run,
)

ALL = frozenset({S.MANUAL, S.IMPORTED, S.SENSOR})


def build(specs, *readings, now=NOW, tolerance=10):
    views = meals(*specs)
    association = associate_meals(
        views, inputs(*readings), now, AssociationParams(milestones=MilestoneParams(tolerance))
    )
    return views, association


def table(specs, *readings, sources=ALL, has_imported=False, **kw):
    views, association = build(specs, *readings, **kw)
    return meals_table(
        association.meals, {v.uuid: v for v in views}, sources, has_imported=has_imported
    )


# ------------------------------------------------------------------- tabla de comidas
def test_every_meal_is_a_row_newest_first_including_those_without_any_glucose():
    frame = table([("a", 0), ("b", 1000), ("c", 2000)], manual(10))

    assert list(frame["Fecha y hora"]) == sorted(frame["Fecha y hora"], reverse=True)
    assert len(frame) == 3
    sin_datos = frame[frame["Datos de glucosa"].str.startswith("Sin mediciones")]
    assert len(sin_datos) == 2  # las comidas sin glucosa siguen visibles y dicen por qué


def test_the_previous_and_the_reference_are_separate_columns_and_the_posterior_one_is_flagged():
    frame = table([("a", 0)], manual(-30, 100), manual(2, 150))

    row = frame.iloc[0]
    assert row["Previa (manual)"] == "100 mg/dL (−30 min)"
    assert row["Referencia (manual)"] == "150 mg/dL (+2 min) · posterior al registro"


def test_a_reference_less_than_a_minute_after_the_record_is_shown_in_seconds():
    row = table([("a", 0)], manual(0.4, 150)).iloc[0]

    assert row["Referencia (manual)"] == "150 mg/dL (+24 s) · posterior al registro"
    assert "0 min" not in row["Referencia (manual)"]


def test_a_reference_just_before_the_record_keeps_its_negative_sign_in_seconds():
    row = table([("a", 0)], manual(-0.5, 150)).iloc[0]

    assert row["Referencia (manual)"] == "150 mg/dL (−30 s)"  # previa: no lleva «posterior»


def test_a_reading_at_the_exact_record_instant_is_zero_seconds_and_not_posterior():
    row = table([("a", 0)], manual(0, 150)).iloc[0]

    assert row["Referencia (manual)"] == "150 mg/dL (0 s)"


def test_nearby_table_expresses_sub_minute_offsets_in_seconds():
    frame = nearby(manual(0.2, 120))

    assert list(frame["Desfase"]) == ["+12 s"]


def test_without_a_previous_reading_the_cell_says_so_instead_of_showing_the_reference():
    row = table([("a", 0)], manual(2, 150)).iloc[0]

    assert row["Previa (manual)"] == "—"
    assert "posterior al registro" in row["Referencia (manual)"]


def test_milestone_cells_show_the_nearest_reading_with_its_offset_or_the_reason_it_is_missing():
    row = table([("a", 0)], manual(62, 140)).iloc[0]

    assert row["+60 (manual)"] == "140 mg/dL (+2 min del hito)"
    assert row["+90 (manual)"] == "Sin medición manual registrada"
    assert row["+60 (sensor)"] == "Sin datos del sensor"


def test_sensor_states_are_not_confused_with_missing_manual_readings():
    outdated = table([("a", 3000)], *sensor_run(-120, 300)).iloc[0]
    gap = table([("a", 0)], *(sensor_run(-120, 30) + sensor_run(150, 300))).iloc[0]

    assert outdated["+60 (sensor)"] == "Sin datos del sensor: export fuera de cobertura"
    assert gap["+60 (sensor)"] == "Sin datos del sensor: hueco dentro del export"
    assert outdated["+60 (manual)"] == "Sin medición manual registrada"


def test_pending_milestones_are_not_reported_as_missing():
    from datetime import timedelta

    from tests.meal_glucose_helpers import T0

    row = table([("a", 0)], manual(10), now=T0 + timedelta(minutes=30)).iloc[0]

    assert row["+60 (manual)"] == "Hito pendiente" and row["+90 (sensor)"] == "Hito pendiente"


def test_the_real_sensor_coverage_is_shown_for_the_posterior_window():
    sufficient = table([("a", 0)], *sensor_run(-120, 300)).iloc[0]
    partial = table([("a", 0)], *sensor_run(-120, 90)).iloc[0]
    outdated = table([("a", 3000)], *sensor_run(-120, 300)).iloc[0]

    assert "100 %" in sufficient["Sensor posterior (cobertura)"]
    assert "suficiente" in sufficient["Sensor posterior (cobertura)"].lower()
    assert "Parcialmente fuera del export" in partial["Sensor posterior (cobertura)"]
    assert "Export desactualizado" in outdated["Sensor posterior (cobertura)"]


def test_the_windows_column_flags_shared_windows_near_simultaneous_and_crossed_milestones():
    frame = table([("a", 0), ("b", 10), ("c", 1000)])
    by_time = frame.sort_values("Fecha y hora").reset_index(drop=True)

    assert "Casi simultánea" in by_time.loc[0, "Ventanas"]
    assert "Ventana compartida con" in by_time.loc[0, "Ventanas"]
    assert "Hito cruzado: +60, +90" in by_time.loc[0, "Ventanas"]
    assert by_time.loc[2, "Ventanas"] == "Aislada"


def test_only_the_selected_sources_have_columns_and_imported_hides_when_there_are_none():
    only_manual = table([("a", 0)], manual(10), sources={S.MANUAL})
    with_imported = table([("a", 0)], manual(10), imported(20), has_imported=True)
    without = table([("a", 0)], manual(10))

    assert not any("sensor" in c for c in only_manual.columns)
    assert any("importada" in c for c in with_imported.columns)
    assert not any("importada" in c for c in without.columns)


def test_data_availability_text_follows_the_selected_sources():
    both = table([("a", 0)], manual(-30), manual(40))
    only_sensor = table([("a", 0)], manual(-30), manual(40), sources={S.SENSOR})

    assert both.iloc[0]["Datos de glucosa"] == "Con previa y posterior"
    assert only_sensor.iloc[0]["Datos de glucosa"].startswith("Sin mediciones")


def test_the_table_never_uses_compliance_or_causal_wording():
    frame = table([("a", 0)], manual(60), *sensor_run(-60, 200))
    text = " ".join(frame.columns) + " " + " ".join(map(str, frame.iloc[0].tolist()))

    for word in ("cumpl", "omit", "recordatorio", "causa", "efecto", "pico"):
        assert word not in text.lower()


def test_food_text_collapses_spaces_and_keeps_the_original_names():
    from glucosa.analytics.meal_view import meal_views
    from glucosa.models.records import MealItem, MealRecord, MealType
    from tests.meal_glucose_helpers import at

    views = meal_views(
        [MealRecord("a", MealType.LUNCH, at(0), None, (MealItem("  Pan   integral ", "1"),))]
    )
    association = associate_meals(views, inputs(), NOW)

    frame = meals_table(association.meals, {v.uuid: v for v in views}, ALL, has_imported=False)

    assert frame.iloc[0]["Alimentos"] == "Pan integral"


# ------------------------------------------------------------ lecturas cercanas (una comida)
def nearby(*readings, specs=(("a", 0),), show_scans=False, sources=ALL):
    views, association = build(list(specs), *readings)
    return nearby_readings_table(association.meals[0], association, sources, show_scans=show_scans)


def test_nearby_readings_list_each_source_window_time_and_signed_offset():
    frame = nearby(manual(-20, 100), sensor(30, 130))

    assert list(frame.columns) == [
        "Fuente",
        "Ventana",
        "Hora local",
        "Glucosa (mg/dL)",
        "Desfase",
        "Observaciones",
    ]
    assert list(frame["Fuente"]) == ["Manual (Firebase)", "Sensor (LibreView)"]
    assert list(frame["Desfase"]) == ["−20 min", "+30 min"]
    assert frame.iloc[0]["Ventana"].startswith("Previa")


def test_the_reference_previous_and_nearest_to_milestone_are_annotated():
    frame = nearby(manual(-30, 100), manual(2, 150), manual(61, 170))

    notes = dict(zip(frame["Desfase"], frame["Observaciones"], strict=True))
    assert "Glucosa previa" in notes["−30 min"]
    assert "Referencia (posterior al registro)" in notes["+2 min"]
    assert "Más cercana al hito +60" in notes["+61 min"]


def test_probable_coincidences_and_shared_readings_are_annotated_without_removing_anything():
    frame = nearby(manual(0, 120), sensor(0, 120), specs=(("a", 0), ("b", 10)))
    sensor_row = frame[frame["Fuente"] == "Sensor (LibreView)"].iloc[0]

    assert len(frame) == 2  # ambas lecturas siguen en la tabla
    assert "Coincidencia probable con una medición manual" in sensor_row["Observaciones"]
    assert "Compartida con otra comida" in sensor_row["Observaciones"]


def test_scans_appear_only_when_requested():
    assert nearby(scan(10, 120)).empty
    assert len(nearby(scan(10, 120), show_scans=True)) == 1


def test_a_meal_without_readings_gives_an_empty_table_with_its_columns():
    frame = nearby()

    assert frame.empty and "Fuente" in frame.columns


# ---------------------------------------------------------------- cobertura por fuente
def test_availability_table_counts_meals_with_readings_per_source():
    views, association = build([("a", 0), ("b", 1000)], manual(-30), manual(1060))

    frame = availability_table(association)

    row = frame[frame["Fuente"] == "Manual (Firebase)"].iloc[0]
    assert (row["Comidas"], row["Con previa"], row["Con posterior"], row["Con ambas"]) == (
        2,
        1,
        1,
        0,
    )
    assert len(frame) == 3


@pytest.mark.parametrize(
    "source_name", ["Manual (Firebase)", "Importada (Firebase)", "Sensor (LibreView)"]
)
def test_availability_table_has_one_row_per_series_source(source_name):
    _, association = build([("a", 0)])

    assert source_name in set(availability_table(association)["Fuente"])


# ------------------------------------------------------------------ hitos de una comida
def milestones(*readings, sources=ALL, has_imported=False, **kw):
    _, association = build([("a", 0)], *readings, **kw)
    return milestones_table(association.meals[0], sources, has_imported=has_imported)


def test_milestones_table_has_one_row_per_milestone_and_one_column_per_source():
    frame = milestones(manual(62, 140), has_imported=True)

    assert list(frame["Hito"]) == ["+60 min", "+90 min"]
    assert list(frame.columns) == [
        "Hito",
        "Manual (Firebase)",
        "Importada (Firebase)",
        "Sensor (LibreView)",
        "Tolerancia",
    ]
    assert frame.iloc[0]["Manual (Firebase)"] == "140 mg/dL (+2 min del hito)"
    assert frame.iloc[1]["Manual (Firebase)"] == "Sin medición manual registrada"
    assert frame.iloc[0]["Importada (Firebase)"] == "No aplica"  # no hay importadas en la serie


def test_milestones_table_shows_the_tolerance_used_and_follows_the_selected_sources():
    frame = milestones(manual(62), tolerance=15, sources={S.MANUAL})

    assert set(frame["Tolerancia"]) == {"±15 min"}
    assert "Sensor (LibreView)" not in frame.columns


# ------------------------------------------------------------ anchos de la tabla de detalle
def test_the_three_leading_columns_are_pinned_and_every_column_gets_a_readable_width():
    frame = table([("a", 0)], manual(10), imported(20), has_imported=True)

    assert PINNED_COLUMNS == ("Fecha y hora", "Tipo", "Alimentos")
    assert list(frame.columns[:3]) == list(PINNED_COLUMNS)
    widths = {name: column_width(name) for name in frame.columns}
    assert min(widths.values()) >= 90
    assert (
        sum(widths[name] for name in PINNED_COLUMNS) <= PINNED_BUDGET_PX
    )  # bajo el ~60 % de Streamlit
    assert widths["Referencia (manual)"] >= 300 and widths["+60 (sensor)"] >= 340


@pytest.mark.parametrize(
    "name", ["+60 (manual)", "+90 (importada)", "Previa (sensor)", "Columna futura"]
)
def test_unknown_or_new_columns_keep_a_legible_default_width(name):
    assert column_width(name) >= 170
