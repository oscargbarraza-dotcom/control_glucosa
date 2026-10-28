"""Carga segura del JSON del cliente OAuth de escritorio descargado desde Google Cloud."""

import json

import pytest

from glucosa.auth.oauth_client import MAX_FILE_BYTES, load_oauth_client
from glucosa.errors import ConfigError

CLIENT_ID = "123456789-abcdef.apps.googleusercontent.com"
SECRET = "GOCSPX-SECRETO-DE-PRUEBA"


def installed(**overrides):
    body = {
        "client_id": CLIENT_ID,
        "project_id": "seguimiento-glucosa",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": SECRET,
        "redirect_uris": ["http://localhost"],
    }
    body.update(overrides)
    return {"installed": body}


def write(tmp_path, content, name="client.json"):
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def test_valid_desktop_client_is_loaded(tmp_path):
    client = load_oauth_client(
        write(tmp_path, installed()), expected_project_id="seguimiento-glucosa"
    )
    assert client.client_id == CLIENT_ID
    assert client.client_secret == SECRET
    assert client.auth_uri == "https://accounts.google.com/o/oauth2/auth"
    assert client.token_uri == "https://oauth2.googleapis.com/token"


def test_repr_never_exposes_the_secret(tmp_path):
    client = load_oauth_client(write(tmp_path, installed()), expected_project_id=None)
    assert SECRET not in repr(client)
    assert SECRET not in str(client)


def test_web_type_client_is_rejected_with_actionable_message(tmp_path):
    body = {"web": installed()["installed"]}
    with pytest.raises(ConfigError, match="Aplicación de escritorio"):
        load_oauth_client(write(tmp_path, body), expected_project_id=None)


@pytest.mark.parametrize(
    "overrides",
    [
        {"client_id": ""},
        {"client_id": "no-es-un-id-de-google"},
        {"client_secret": ""},
        {"client_secret": None},
    ],
)
def test_missing_or_malformed_credentials_are_rejected(tmp_path, overrides):
    with pytest.raises(ConfigError):
        load_oauth_client(write(tmp_path, installed(**overrides)), expected_project_id=None)


@pytest.mark.parametrize(
    "overrides",
    [
        {"token_uri": "https://evil.example.com/token"},
        {"auth_uri": "https://evil.example.com/auth"},
        {"token_uri": "http://oauth2.googleapis.com/token"},
    ],
)
def test_endpoints_are_pinned_to_google_so_a_tampered_file_cannot_redirect_credentials(
    tmp_path, overrides
):
    with pytest.raises(ConfigError, match="endpoint"):
        load_oauth_client(write(tmp_path, installed(**overrides)), expected_project_id=None)


def test_client_from_another_project_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="proyecto"):
        load_oauth_client(
            write(tmp_path, installed(project_id="otro-proyecto")),
            expected_project_id="seguimiento-glucosa",
        )


def test_missing_file_explains_which_setting_to_use(tmp_path):
    with pytest.raises(ConfigError, match="GLUCOSA_OAUTH_CLIENT_FILE"):
        load_oauth_client(tmp_path / "no-existe.json", expected_project_id=None)


def test_invalid_json_and_oversized_files_are_rejected_without_echoing_content(tmp_path):
    bad = write(tmp_path, f'{{"client_secret": "{SECRET}" esto no es json')
    with pytest.raises(ConfigError) as info:
        load_oauth_client(bad, expected_project_id=None)
    assert SECRET not in str(info.value)

    huge = write(tmp_path, "x" * (MAX_FILE_BYTES + 1), name="huge.json")
    with pytest.raises(ConfigError, match="tamaño"):
        load_oauth_client(huge, expected_project_id=None)


def test_file_inside_onedrive_is_rejected(tmp_path, monkeypatch):
    onedrive = tmp_path / "OneDrive - X"
    onedrive.mkdir()
    monkeypatch.setenv("OneDrive", str(onedrive))
    path = write(onedrive, installed())
    with pytest.raises(ConfigError, match="OneDrive"):
        load_oauth_client(path, expected_project_id=None)
