"""Guardas de alcance de Alimentación (D2 a D4).

Las capas de datos y de indicadores de comidas (D2) no dependen de glucosa, LibreView, gráficos
ni interfaz; la asociación con glucosa (D3) y la interfaz (D4) viven en módulos propios.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "glucosa"
MEAL_MODULES = [
    SRC / "models" / "foods.py",
    SRC / "analytics" / "meal_view.py",
    SRC / "analytics" / "meal_summaries.py",
]
FORBIDDEN_PREFIXES = (
    "glucosa.analytics.glucose_sensor",
    "glucosa.analytics.glucose_match",
    "glucosa.analytics.glucose_summaries",
    "glucosa.sources.libre",
    "glucosa.ui",
    "plotly",
    "streamlit",
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_meal_analytics_modules_exist():
    assert all(path.exists() for path in MEAL_MODULES)


def test_meal_analytics_do_not_depend_on_glucose_series_libreview_charts_or_the_interface():
    for path in MEAL_MODULES:
        for module in imported_modules(path):
            assert not module.startswith(FORBIDDEN_PREFIXES), f"{path.name} importa {module}"


def test_only_the_d3_analytics_and_the_d4_dashboard_logic_exist():
    # D4 agrega solo la lógica de visualización (meal_dashboard) y la interfaz; nada de D5.
    assert {p.name for p in (SRC / "analytics").glob("meal_*.py")} == {
        "meal_view.py",
        "meal_summaries.py",
        "meal_readings.py",
        "meal_glucose.py",
        "meal_milestones.py",
        "meal_dashboard.py",
    }


def test_the_d4_interface_is_limited_to_the_page_filters_labels_cards_charts_and_tables():
    assert {p.name for p in (SRC / "ui").glob("meal_*.py")} == {
        "meal_page.py",
        "meal_filters_ui.py",
        "meal_kpi.py",
        "meal_labels.py",
        "meal_charts.py",
        "meal_table.py",
    }


def test_the_navigation_marks_alimentacion_as_available():
    from glucosa.ui.navigation import PLANNED_PHASE

    assert "disponible" in PLANNED_PHASE["Alimentación"]


def test_meal_summaries_expose_no_glucose_fields():
    import dataclasses

    from glucosa.analytics import meal_summaries

    for name in dir(meal_summaries):
        candidate = getattr(meal_summaries, name)
        if dataclasses.is_dataclass(candidate) and isinstance(candidate, type):
            fields = {f.name for f in dataclasses.fields(candidate)}
            assert not any("glucose" in field or "glucosa" in field for field in fields), name
