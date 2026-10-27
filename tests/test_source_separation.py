"""Separación de fuentes: LibreView no depende de Firebase ni de la red (y viceversa)."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "glucosa"
LIBRE = SRC / "sources" / "libre"
# Módulos de Firebase / red que LibreView no puede importar.
FORBIDDEN_FOR_LIBRE = (
    "glucosa.data.firestore_client",
    "glucosa.data.firestore_decode",
    "glucosa.data.parsing",
    "glucosa.auth",
    "glucosa.http",
    "requests",
    "urllib.request",
    "socket",
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


def test_libreview_package_never_imports_firebase_or_network_modules():
    offenders = {
        f"{path.name} → {module}"
        for path in LIBRE.glob("*.py")
        for module in imported_modules(path)
        if module.startswith(FORBIDDEN_FOR_LIBRE)
    }
    assert offenders == set()


def test_sensor_and_scan_analytics_do_not_depend_on_firebase_either():
    for name in ("glucose_sensor.py",):
        modules = imported_modules(SRC / "analytics" / name)
        assert not any(m.startswith(("glucosa.data.firestore", "glucosa.auth")) for m in modules)


def test_firebase_data_layer_never_imports_the_libreview_package():
    offenders = {
        f"{path.name} → {module}"
        for folder in ("data", "auth")
        for path in (SRC / folder).glob("*.py")
        for module in imported_modules(path)
        if module.startswith("glucosa.sources")
    }
    assert offenders == set()
