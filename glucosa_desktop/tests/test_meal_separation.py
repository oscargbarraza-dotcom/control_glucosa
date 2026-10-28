"""Separación de fuentes y límites de alcance de la capa analítica de D3."""

import ast
import dataclasses
from pathlib import Path

from glucosa.analytics.meal_glucose import AssociationParams, Window, associate_meals
from glucosa.analytics.meal_readings import ReadingSource as S
from glucosa.analytics.meal_readings import readings_from_history, readings_from_records
from glucosa.models.records import GlucoseMoment, GlucoseRecord, Origin
from glucosa.sources.libre.models import RecordType, StoredReading, TimeFlag
from tests.meal_glucose_helpers import NOW, at, imported, inputs, manual, meals, sensor, sensor_run

SRC = Path(__file__).resolve().parents[1] / "src" / "glucosa" / "analytics"
NEW_MODULES = ["meal_readings.py", "meal_glucose.py", "meal_milestones.py"]


def snapshot(outcome, source):
    """Todo lo que describe a una fuente en una comida (para compararlo antes y después)."""
    return (
        {w: outcome.summary(w, source) for w in Window},
        outcome.reference.get(source),
        outcome.previous.get(source),
        outcome.rise.get(source),
        {m: outcome.milestones[m][source] for m in outcome.milestones},
    )


def run(readings):
    return associate_meals(meals(("a", 0)), inputs(*readings), NOW, AssociationParams()).meals[0]


def test_adding_sensor_readings_never_changes_the_manual_or_imported_results():
    base = [manual(-20, 100), manual(60, 190), imported(30, 150)]
    plus_sensor = base + sensor_run(-120, 300, 15, 90)

    without, with_sensor = run(base), run(plus_sensor)

    assert snapshot(without, S.MANUAL) == snapshot(with_sensor, S.MANUAL)
    assert snapshot(without, S.IMPORTED) == snapshot(with_sensor, S.IMPORTED)


def test_adding_manual_or_imported_readings_never_changes_the_sensor_results():
    sensor_only = sensor_run(-120, 300, 15, 90)

    without = run(sensor_only)
    with_others = run(sensor_only + [manual(-20, 100), manual(60, 190), imported(30, 150)])

    assert snapshot(without, S.SENSOR) == snapshot(with_others, S.SENSOR)


def test_results_are_indexed_by_source_and_there_is_no_cross_source_aggregate():
    outcome = run([manual(10, 100), sensor(10, 200)])

    assert {s for (_, s) in outcome.summaries} == {S.MANUAL, S.IMPORTED, S.SENSOR}
    forbidden = ("mean", "average", "promedio", "median", "total_value", "sum_value")
    for cls in (type(outcome), type(outcome.summary(Window.POST, S.MANUAL))):
        assert not any(
            word in f.name.lower() for f in dataclasses.fields(cls) for word in forbidden
        )


def test_there_is_no_area_under_the_curve_or_causal_vocabulary():
    outcome = run([manual(10, 100)])
    names = {f.name.lower() for f in dataclasses.fields(type(outcome))}
    names |= {
        f.name.lower() for f in dataclasses.fields(type(outcome.summary(Window.POST, S.MANUAL)))
    }

    assert not any(
        word in name for name in names for word in ("auc", "area", "spike", "peak", "cause")
    )


# ------------------------------------------------------------ construcción de lecturas
def record(uuid, minutes, origin=Origin.MANUAL, comment=None):
    return GlucoseRecord(uuid, 120, GlucoseMoment.NOW, at(minutes), comment, origin)


def test_records_become_manual_or_imported_readings_without_their_comment_or_moment():
    readings = readings_from_records(
        [
            record("m", 1, comment="60 minutos"),
            record("i", 2, Origin.IMPORTED, comment="Importado desde X."),
        ]
    )

    assert {r.id: r.source for r in readings} == {"m": S.MANUAL, "i": S.IMPORTED}
    assert not {"comment", "moment", "text"} & {f.name for f in dataclasses.fields(readings[0])}


def stored(minutes, value, kind=RecordType.HISTORIC, device="d"):
    return StoredReading(device, "x", at(minutes), -180, TimeFlag.NORMAL, kind, value, 1)


def test_history_is_consolidated_and_scans_are_kept_apart():
    history = readings_from_history(
        [
            stored(0, 100),
            stored(0, 100, device="e"),
            stored(15, 110),
            stored(7, 105, RecordType.SCAN),
        ]
    )

    assert [r.source for r in history.sensor] == [
        S.SENSOR,
        S.SENSOR,
    ]  # el duplicado entre dispositivos cuenta una vez
    assert [r.source for r in history.scans] == [S.SCAN]
    assert history.duplicates == 1


def test_the_export_span_comes_from_the_consolidated_history_only():
    history = readings_from_history(
        [stored(0, 100), stored(30, 110), stored(500, 150, RecordType.SCAN)]
    )
    data = inputs(*history.sensor, *history.scans, export_span=history.span)

    assert data.export_span == (at(0), at(30))


def test_unique_ids_are_stable_for_the_same_reading():
    first = readings_from_history([stored(0, 100)])
    second = readings_from_history([stored(0, 100, device="otro")])

    assert first.sensor[0].id == second.sensor[0].id


# ----------------------------------------------------------------- alcance (guardas)
def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_new_modules_do_not_touch_the_interface_charts_network_or_storage():
    forbidden = (
        "glucosa.ui",
        "streamlit",
        "plotly",
        "requests",
        "keyring",
        "glucosa.data.firestore_client",
        "glucosa.sources.libre.store",
        "glucosa.sources.libre.importer",
        "glucosa.storage",
        "glucosa.auth",
    )
    for name in NEW_MODULES:
        for module in imported_modules(SRC / name):
            assert not module.startswith(forbidden), f"{name} importa {module}"


def test_the_new_modules_never_write_files_or_print():
    for name in NEW_MODULES:
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not calls & {"open", "print", "Path.write_text", "os.remove", "shutil.rmtree"}, name
