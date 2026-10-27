"""Intercambio con Firebase (signInWithIdp) y servicio de sesión de punta a punta (sin red)."""

import json
import threading
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest
import requests
from keyring.errors import KeyringError

from glucosa.auth.firebase_signin import sign_in_with_google
from glucosa.auth.oauth_client import OAuthClient
from glucosa.auth.service import AuthService
from glucosa.auth.token_store import KeyringTokenStore, StoredLogin
from glucosa.errors import AuthError, ConnectionProblem, SessionExpiredError
from tests.fakes import FakeHttp, FakeKeyring, FakeResponse, make_jwt

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
CLIENT = OAuthClient(client_id="123-abc.apps.googleusercontent.com", client_secret="SECRETO-OAUTH")
UID = "AbCdEf1234567890UidFirebase"


def firebase_ok(**overrides):
    body = {
        "idToken": "ID-FIREBASE",
        "refreshToken": "REFRESH-FIREBASE",
        "localId": UID,
        "email": "persona@gmail.com",
        "expiresIn": "3600",
    }
    body.update(overrides)
    return FakeResponse(200, body)


# ------------------------------------------------------------- signInWithIdp
def test_sign_in_with_google_builds_the_documented_request_and_maps_the_response():
    http = FakeHttp([firebase_ok()])

    login = sign_in_with_google(http, "API-KEY", "GOOGLE-ID-TOKEN", clock=lambda: NOW)

    call = http.calls[0]
    assert call["url"] == "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp"
    assert call["params"] == {"key": "API-KEY"}
    body = call["json"]
    assert body["requestUri"] == "http://localhost"
    assert body["returnSecureToken"] is True
    assert urllib.parse.parse_qs(body["postBody"]) == {
        "id_token": ["GOOGLE-ID-TOKEN"],
        "providerId": ["google.com"],
    }
    assert (login.uid, login.email) == (UID, "persona@gmail.com")
    assert login.expires_at == NOW + timedelta(seconds=3600)
    assert "ID-FIREBASE" not in repr(login) and "REFRESH-FIREBASE" not in repr(login)


def test_firebase_rejection_surfaces_the_error_code_to_diagnose_audience_problems():
    http = FakeHttp([FakeResponse(400, {"error": {"message": "INVALID_IDP_RESPONSE : audience"}})])
    with pytest.raises(AuthError, match="INVALID_IDP_RESPONSE"):
        sign_in_with_google(http, "K", "T", clock=lambda: NOW)


@pytest.mark.parametrize("body", [{"needConfirmation": True}, {"emailExists": True}, {}])
def test_responses_without_a_firebase_session_are_domain_errors(body):
    with pytest.raises(AuthError):
        sign_in_with_google(FakeHttp([FakeResponse(200, body)]), "K", "T", clock=lambda: NOW)


def test_network_and_server_failures_are_connection_problems_without_leaking_the_key():
    with pytest.raises(ConnectionProblem) as info:
        sign_in_with_google(
            FakeHttp([requests.ConnectionError("https://x?key=API-KEY")]),
            "API-KEY",
            "T",
            clock=lambda: NOW,
        )
    assert info.value.__cause__ is None
    with pytest.raises(ConnectionProblem):
        sign_in_with_google(FakeHttp([FakeResponse(503, {})]), "K", "T", clock=lambda: NOW)


def test_an_unsafe_uid_from_the_server_is_rejected():
    with pytest.raises(AuthError):
        sign_in_with_google(FakeHttp([firebase_ok(localId="../otro")]), "K", "T", clock=lambda: NOW)


# ---------------------------------------------------------------- AuthService
class GoogleAndFirebaseFake:
    """Simula token endpoint de Google + signInWithIdp, usando el nonce real de la URL."""

    def __init__(self):
        self.nonce = None
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(url)
        if url == "https://oauth2.googleapis.com/token":
            claims = {
                "iss": "https://accounts.google.com",
                "aud": CLIENT.client_id,
                "exp": int((NOW + timedelta(minutes=30)).timestamp()),
                "nonce": self.nonce,
                "email": "persona@gmail.com",
                "email_verified": True,
            }
            return FakeResponse(200, {"id_token": make_jwt(claims), "access_token": "NO-GUARDAR"})
        if url.endswith("accounts:signInWithIdp"):
            return firebase_ok()
        raise AssertionError(f"URL inesperada: {url}")


def make_service(http, backend=None, opener=None):
    backend = backend or FakeKeyring()
    service = AuthService(
        api_key="API-KEY",
        client=CLIENT,
        http=http,
        token_store=KeyringTokenStore(backend=backend),
        open_browser=opener or (lambda url: True),
        clock=lambda: NOW,
        callback_timeout=10,
    )
    return service, backend


def browser_that_approves(http_fake):
    """Simula al navegador: lee state/nonce de la URL y llama al callback local."""

    def opener(url):
        query = {
            k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()
        }
        http_fake.nonce = query["nonce"]
        callback = f"{query['redirect_uri']}?code=CODIGO&state={query['state']}"
        threading.Thread(target=lambda: urllib.request.urlopen(callback, timeout=5).read()).start()
        return True

    return opener


def test_full_sign_in_stores_only_the_firebase_refresh_token():
    fake = GoogleAndFirebaseFake()
    service, backend = make_service(fake, opener=browser_that_approves(fake))

    result = service.sign_in()

    assert result.session.uid == UID
    assert result.session.id_token == "ID-FIREBASE"
    assert result.uid_changed is False
    stored = json.loads(backend.store[("glucosa", "session")])
    assert stored == {"uid": UID, "refresh_token": "REFRESH-FIREBASE"}
    saved_text = " ".join(backend.store.values())
    assert "NO-GUARDAR" not in saved_text and "SECRETO-OAUTH" not in saved_text


def test_sign_in_flags_a_different_uid_than_the_previously_stored_one():
    fake = GoogleAndFirebaseFake()
    service, backend = make_service(fake, opener=browser_that_approves(fake))
    KeyringTokenStore(backend=backend).save(
        StoredLogin(uid="OtroUidAnterior123", refresh_token="x")
    )

    assert service.sign_in().uid_changed is True


def test_sign_in_fails_clearly_when_the_browser_cannot_be_opened():
    service, _ = make_service(GoogleAndFirebaseFake(), opener=lambda url: False)
    with pytest.raises(AuthError, match="navegador"):
        service.sign_in()


# -------------------------------------------------------- restaurar / cerrar sesión
def refresh_ok(refresh="ROTADO", uid=UID):
    return FakeResponse(
        200,
        {"id_token": "NUEVO-ID", "refresh_token": refresh, "expires_in": "3600", "user_id": uid},
    )


def test_restore_returns_none_without_a_stored_login():
    service, _ = make_service(FakeHttp())
    assert service.restore_session() is None


def test_restore_renews_the_session_and_saves_the_rotated_refresh_token():
    service, backend = make_service(FakeHttp([refresh_ok()]))
    KeyringTokenStore(backend=backend).save(StoredLogin(uid=UID, refresh_token="VIEJO"))

    session = service.restore_session()

    assert session.id_token == "NUEVO-ID"
    assert KeyringTokenStore(backend=backend).load().refresh_token == "ROTADO"


def test_restore_clears_the_stored_login_when_firebase_rejects_it():
    http = FakeHttp([FakeResponse(400, {"error": {"message": "TOKEN_EXPIRED"}})])
    service, backend = make_service(http)
    KeyringTokenStore(backend=backend).save(StoredLogin(uid=UID, refresh_token="R"))

    with pytest.raises(SessionExpiredError):
        service.restore_session()
    assert KeyringTokenStore(backend=backend).load() is None


def test_restore_keeps_the_stored_login_on_network_failure():
    service, backend = make_service(FakeHttp([requests.ConnectionError("sin red")]))
    KeyringTokenStore(backend=backend).save(StoredLogin(uid=UID, refresh_token="R"))

    with pytest.raises(ConnectionProblem):
        service.restore_session()
    assert KeyringTokenStore(backend=backend).load() is not None


def test_restore_refuses_a_session_that_belongs_to_another_user_and_clears_it():
    service, backend = make_service(FakeHttp([refresh_ok(uid="UidDeOtraPersona99")]))
    KeyringTokenStore(backend=backend).save(StoredLogin(uid=UID, refresh_token="R"))

    with pytest.raises(AuthError):
        service.restore_session()
    assert KeyringTokenStore(backend=backend).load() is None


def test_sign_out_removes_the_stored_login():
    service, backend = make_service(FakeHttp())
    KeyringTokenStore(backend=backend).save(StoredLogin(uid=UID, refresh_token="R"))
    service.sign_out()
    assert KeyringTokenStore(backend=backend).load() is None


# ----------------------------------------- fallos del Administrador de credenciales
class BrokenKeyring(FakeKeyring):
    def set_password(self, service, username, password):
        raise KeyringError("almacén bloqueado")

    def get_password(self, service, username):
        raise KeyringError("almacén bloqueado")


def test_keyring_failure_when_saving_the_session_is_a_clear_domain_error():
    fake = GoogleAndFirebaseFake()
    service, _ = make_service(fake, backend=BrokenKeyring(), opener=browser_that_approves(fake))
    with pytest.raises(AuthError, match="Administrador de credenciales"):
        service.sign_in()


def test_keyring_failure_when_restoring_is_a_clear_domain_error():
    service, _ = make_service(FakeHttp(), backend=BrokenKeyring())
    with pytest.raises(AuthError, match="Administrador de credenciales"):
        service.restore_session()
