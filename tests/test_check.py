"""Diagnóstico de la instalación: informa estados sin mostrar nunca un secreto."""

import json

from glucosa.check import run_checks
from glucosa.config import AppConfig

CLIENT_ID = "123456789-abcdef.apps.googleusercontent.com"
SECRET = "GOCSPX-SECRETO-DE-PRUEBA"


class WinVaultKeyring:  # el nombre de la clase es lo que se inspecciona
    pass


class PlaintextKeyring:
    pass


def write_client(tmp_path):
    path = tmp_path / "client.json"
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": CLIENT_ID,
                    "project_id": "seguimiento-glucosa",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_secret": SECRET,
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def results_by_name(config, backend=None):
    return {r.name: r for r in run_checks(config, keyring_backend=backend or WinVaultKeyring())}


def test_everything_ok_with_a_complete_setup(tmp_path):
    config = AppConfig("seguimiento-glucosa", "api-key", write_client(tmp_path))
    results = results_by_name(config)
    assert all(r.ok for r in results.values()), {k: v.detail for k, v in results.items()}


def test_missing_api_key_and_client_file_are_reported(tmp_path):
    results = results_by_name(AppConfig("seguimiento-glucosa", None, None))
    assert not results["API key de Firebase"].ok
    assert not results["Cliente OAuth de escritorio"].ok


def test_insecure_keyring_backend_is_flagged(tmp_path):
    config = AppConfig("seguimiento-glucosa", "k", write_client(tmp_path))
    result = results_by_name(config, PlaintextKeyring())["Almacén de credenciales"]
    assert not result.ok
    assert "PlaintextKeyring" in result.detail


def test_report_never_contains_the_secret_or_the_full_client_id(tmp_path):
    config = AppConfig("seguimiento-glucosa", "api-key-secreta", write_client(tmp_path))
    text = " ".join(
        f"{r.name} {r.detail}" for r in run_checks(config, keyring_backend=WinVaultKeyring())
    )
    assert SECRET not in text
    assert "api-key-secreta" not in text
    assert CLIENT_ID not in text
