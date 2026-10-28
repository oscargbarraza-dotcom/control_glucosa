"""Prueba de humo del esqueleto de la interfaz (sin red ni credenciales)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from glucosa.ui.navigation import PAGES

TOKEN = "s" * 43
APP_FILE = Path(__file__).resolve().parents[1] / "src" / "glucosa" / "ui" / "app.py"


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # sin .env: la app debe arrancar igual
    monkeypatch.delenv("GLUCOSA_FIREBASE_API_KEY", raising=False)
    monkeypatch.setenv("GLUCOSA_ACCESS_TOKEN", TOKEN)
    at = AppTest.from_file(str(APP_FILE), default_timeout=30)
    at.query_params["t"] = TOKEN
    return at.run()


def test_app_starts_without_exceptions(app):
    assert not app.exception


def test_sidebar_lists_the_six_planned_sections(app):
    assert PAGES == (
        "Dashboard general",
        "Glucosa",
        "Alimentación",
        "Medicamentos",
        "Biometría",
        "Configuración",
    )
    assert tuple(app.sidebar.radio[0].options) == PAGES


def test_shows_clear_state_when_not_signed_in_or_configured(app):
    messages = " ".join(m.value for m in [*app.warning, *app.info])
    assert "GLUCOSA_FIREBASE_API_KEY" in messages
    assert "sesión" in messages.lower()


def test_each_page_renders_without_exceptions(app):
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
        assert app.header[0].value == page
