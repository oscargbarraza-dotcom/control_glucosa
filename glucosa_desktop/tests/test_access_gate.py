"""Puerta de acceso local: sin el token de esta ejecución la interfaz no muestra ni importa nada."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from glucosa.access_config import ENV_ACCESS_TOKEN
from glucosa.ui.access import AccessDecision, decide_access

APP_FILE = Path(__file__).resolve().parents[1] / "src" / "glucosa" / "ui" / "app.py"
TOKEN = "t" * 43


# ------------------------------------------------------------------ decisión pura
def test_matching_token_grants_access():
    assert decide_access(TOKEN, TOKEN) is AccessDecision.GRANTED


@pytest.mark.parametrize("provided", [None, "", "otro", TOKEN + "x", TOKEN[:-1], " " + TOKEN])
def test_missing_or_wrong_token_is_denied(provided):
    assert decide_access(TOKEN, provided) is AccessDecision.DENIED


@pytest.mark.parametrize("expected", [None, ""])
def test_without_a_configured_token_the_app_fails_closed(expected):
    assert decide_access(expected, TOKEN) is AccessDecision.NOT_CONFIGURED
    assert decide_access(expected, None) is AccessDecision.NOT_CONFIGURED


def test_non_ascii_tokens_do_not_raise():
    assert decide_access(TOKEN, "tóken-ñ") is AccessDecision.DENIED


# --------------------------------------------------------- la app completa (AppTest)
def run_app(monkeypatch, tmp_path, *, env_token=TOKEN, url_token=None) -> AppTest:
    monkeypatch.chdir(tmp_path)
    if env_token is None:
        monkeypatch.delenv(ENV_ACCESS_TOKEN, raising=False)
    else:
        monkeypatch.setenv(ENV_ACCESS_TOKEN, env_token)
    app = AppTest.from_file(str(APP_FILE), default_timeout=30)
    if url_token is not None:
        app.query_params["t"] = url_token
    return app.run()


def test_the_app_shows_nothing_without_the_token_in_the_url(monkeypatch, tmp_path):
    app = run_app(monkeypatch, tmp_path)

    assert not app.exception
    assert "acceso" in " ".join(e.value for e in app.error).lower()
    assert len(app.sidebar.radio) == 0  # ni la navegación ni ninguna página
    assert len(app.header) == 0 and len(app.metric) == 0 and len(app.dataframe) == 0


def test_the_app_denies_a_wrong_token_without_echoing_it(monkeypatch, tmp_path):
    app = run_app(monkeypatch, tmp_path, url_token="incorrecto-123")

    shown = " ".join(e.value for e in [*app.error, *app.warning, *app.info, *app.markdown])
    assert "incorrecto-123" not in shown and TOKEN not in shown
    assert len(app.sidebar.radio) == 0


def test_the_app_fails_closed_when_started_without_the_launcher_token(monkeypatch, tmp_path):
    app = run_app(monkeypatch, tmp_path, env_token=None, url_token=TOKEN)

    assert "python -m glucosa" in " ".join(e.value for e in app.error)
    assert len(app.sidebar.radio) == 0


def test_the_app_opens_with_the_right_token_and_keeps_access_for_that_session(
    monkeypatch, tmp_path
):
    app = run_app(monkeypatch, tmp_path, url_token=TOKEN)
    assert not app.exception and len(app.sidebar.radio) == 1

    app.query_params.clear()  # p. ej. el usuario navega dentro de la misma sesión
    app.run()
    assert len(app.sidebar.radio) == 1
