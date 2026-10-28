"""Endurecimiento: solo lectura en ejecución, errores sin filtrar URLs, claves, rutas."""

import threading

import pytest
import requests

from glucosa.auth.refresh import FirebaseTokenRefresher
from glucosa.auth.token_store import KeyringTokenStore, StoredLogin
from glucosa.config import config_from_environment
from glucosa.data.firestore_client import FirestoreReader
from glucosa.errors import AuthError, ConfigError, GlucosaError, SecureStoreError
from glucosa.http import ReadOnlyHttp, default_http
from glucosa.paths import default_data_dir
from glucosa.storage.secure_store import EncryptedJsonStore, KeyringKeyProvider
from tests.fakes import FakeHttp, FakeKeyring, FakeResponse


# ---------------- solo lectura en ejecución
class Underlying:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(200, {})

    def put(self, *a, **k):  # pragma: no cover - no debe ser alcanzable
        raise AssertionError("put no debe ser accesible")


def test_adapter_exposes_only_post_and_blocks_redirects():
    underlying = Underlying()
    adapter = ReadOnlyHttp(underlying)

    adapter.post("https://x/y", json={})

    assert {n for n in dir(adapter) if not n.startswith("_")} == {"post"}
    assert underlying.calls[0][1]["allow_redirects"] is False


def test_default_http_cannot_write():
    http = default_http()
    assert not hasattr(http, "put")
    assert not hasattr(http, "patch")
    assert not hasattr(http, "delete")


def test_reader_refuses_any_url_that_is_not_a_read_endpoint():
    reader = FirestoreReader(project_id="proyecto-p", http=FakeHttp())
    with pytest.raises(ValueError, match="lectura"):
        reader._post(
            "https://firestore.googleapis.com/v1/projects/p/databases/(default)/documents/users/u/meals/x",
            "T",
            {},
        )


def test_project_id_is_validated():
    with pytest.raises(ValueError, match="project"):
        FirestoreReader(project_id="p/../x", http=FakeHttp())


# ---------------- errores sin filtrar URL/clave y respuestas inesperadas
def test_connection_error_does_not_chain_the_original_exception_with_the_api_key():
    http = FakeHttp([requests.ConnectionError("GET https://x?key=SECRETA falló")])
    with pytest.raises(GlucosaError) as info:
        FirebaseTokenRefresher(api_key="SECRETA", http=http).refresh("r")
    assert info.value.__cause__ is None
    assert "SECRETA" not in str(info.value)


def test_unexpected_200_body_is_a_domain_error_not_a_raw_exception():
    http = FakeHttp([FakeResponse(200, {"sin": "campos"})])
    with pytest.raises(AuthError):
        FirebaseTokenRefresher(api_key="K", http=http).refresh("r")


def test_html_200_body_is_a_domain_error():
    class HtmlResponse:
        status_code = 200

        def json(self):
            raise ValueError("no es JSON")

    with pytest.raises(AuthError):
        FirebaseTokenRefresher(api_key="K", http=FakeHttp([HtmlResponse()])).refresh("r")


# ---------------- tokens: logout honesto
def test_clear_swallows_only_missing_entry_errors():
    from keyring.errors import PasswordDeleteError

    class Missing(FakeKeyring):
        def delete_password(self, service, username):
            raise PasswordDeleteError("no existe")

    class Broken(FakeKeyring):
        def delete_password(self, service, username):
            raise RuntimeError("almacén bloqueado")

    KeyringTokenStore(backend=Missing()).clear()  # no debe lanzar
    with pytest.raises(RuntimeError):
        KeyringTokenStore(backend=Broken()).clear()


# ---------------- clave Fernet: sin carreras
def test_key_creation_is_thread_safe_and_consistent():
    class SlowKeyring(FakeKeyring):
        def get_password(self, service, username):
            value = super().get_password(service, username)
            threading.Event().wait(0.02)
            return value

    provider = KeyringKeyProvider(backend=SlowKeyring())
    keys = []
    threads = [threading.Thread(target=lambda: keys.append(provider.key())) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(keys)) == 1


def test_unreadable_file_raises_secure_store_error(tmp_path):
    path = tmp_path / "carpeta.enc"
    path.mkdir()  # leerlo como archivo produce OSError
    with pytest.raises(SecureStoreError):
        EncryptedJsonStore(path, KeyringKeyProvider(backend=FakeKeyring())).read()


# ---------------- rutas: nada de datos de salud en OneDrive
def test_override_inside_onedrive_is_rejected(monkeypatch, tmp_path):
    onedrive = tmp_path / "OneDrive - X"
    onedrive.mkdir()
    monkeypatch.setenv("OneDrive", str(onedrive))
    with pytest.raises(ValueError, match="OneDrive"):
        default_data_dir(str(onedrive / "glucosa"))


def test_override_outside_onedrive_is_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv("OneDrive", str(tmp_path / "OneDrive"))
    assert default_data_dir(str(tmp_path / "otro")) == tmp_path / "otro"


# ---------------- .env fuera de OneDrive
def test_env_file_is_read_from_the_local_data_dir(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "GLUCOSA_FIREBASE_API_KEY=desde-datos-locales\n", encoding="utf-8"
    )
    monkeypatch.setenv("GLUCOSA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GLUCOSA_FIREBASE_API_KEY", raising=False)
    assert config_from_environment().require_api_key() == "desde-datos-locales"


def test_real_environment_variables_take_priority_over_env_file(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("GLUCOSA_FIREBASE_API_KEY=archivo\n", encoding="utf-8")
    monkeypatch.setenv("GLUCOSA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GLUCOSA_FIREBASE_API_KEY", "entorno")
    assert config_from_environment().require_api_key() == "entorno"


def test_missing_env_file_yields_missing_key_error(monkeypatch, tmp_path):
    monkeypatch.setenv("GLUCOSA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GLUCOSA_FIREBASE_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        config_from_environment(project_env_file=tmp_path / "no-existe.env").require_api_key()


def test_stored_login_repr_hides_refresh_token():
    assert "R-SECRETO" not in repr(StoredLogin(uid="u", refresh_token="R-SECRETO"))


def test_refresh_rejects_an_unsafe_user_id_from_the_server():
    http = FakeHttp(
        [
            FakeResponse(
                200,
                {"id_token": "t", "refresh_token": "r", "expires_in": "3600", "user_id": "../x"},
            )
        ]
    )
    with pytest.raises(AuthError):
        FirebaseTokenRefresher(api_key="K", http=http).refresh("r")
