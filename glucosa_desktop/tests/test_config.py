from pathlib import Path

import pytest

from glucosa.config import AppConfig, load_config
from glucosa.errors import ConfigError


def test_defaults_to_shared_firebase_project_and_no_secrets():
    config = load_config({})
    assert config.project_id == "seguimiento-glucosa"
    assert config.api_key is None
    assert config.oauth_client_file is None


def test_reads_values_from_environment_mapping():
    config = load_config(
        {
            "GLUCOSA_FIREBASE_PROJECT_ID": "otro",
            "GLUCOSA_FIREBASE_API_KEY": "abc",
            "GLUCOSA_OAUTH_CLIENT_FILE": r"C:\privado\client.json",
        }
    )
    assert config == AppConfig("otro", "abc", Path(r"C:\privado\client.json"))


def test_environment_variables_inside_the_path_are_expanded(monkeypatch):
    monkeypatch.setenv("MI_CARPETA_PRIVADA", r"C:\privado")
    config = load_config({"GLUCOSA_OAUTH_CLIENT_FILE": r"%MI_CARPETA_PRIVADA%\client.json"})
    assert config.oauth_client_file == Path(r"C:\privado\client.json")


def test_blank_values_are_treated_as_missing():
    config = load_config({"GLUCOSA_FIREBASE_API_KEY": "  ", "GLUCOSA_OAUTH_CLIENT_FILE": " "})
    assert config.api_key is None
    assert config.oauth_client_file is None


def test_require_api_key_raises_clear_error_when_missing():
    with pytest.raises(ConfigError, match="GLUCOSA_FIREBASE_API_KEY"):
        load_config({}).require_api_key()


def test_require_oauth_client_explains_the_missing_setting():
    with pytest.raises(ConfigError, match="GLUCOSA_OAUTH_CLIENT_FILE"):
        load_config({}).require_oauth_client()


def test_repr_never_exposes_the_api_key():
    config = load_config({"GLUCOSA_FIREBASE_API_KEY": "SECRETO-API"})
    assert "SECRETO-API" not in repr(config)
