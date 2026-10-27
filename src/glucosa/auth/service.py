"""Servicio de sesión: inicio con Google, restauración desde Credential Manager y cierre."""

import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from keyring.errors import KeyringError

from glucosa.auth.firebase_signin import sign_in_with_google
from glucosa.auth.google_oauth import (
    CallbackServer,
    build_authorization_url,
    exchange_code,
    generate_pkce,
    new_token,
    validate_google_claims,
)
from glucosa.auth.oauth_client import OAuthClient
from glucosa.auth.refresh import FirebaseTokenRefresher
from glucosa.auth.session import AuthSession
from glucosa.auth.token_store import KeyringTokenStore, StoredLogin
from glucosa.errors import AuthError, SessionExpiredError
from glucosa.http import HttpClient

DEFAULT_CALLBACK_TIMEOUT_SECONDS = 180.0
_KEYRING_MESSAGE = "No se pudo acceder al Administrador de credenciales de Windows."


@dataclass(frozen=True)
class SignInResult:
    session: AuthSession
    uid_changed: bool  # el uid difiere del guardado antes: avisar al usuario


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _load_stored(store: KeyringTokenStore) -> StoredLogin | None:
    try:
        return store.load()
    except KeyringError:
        raise AuthError(_KEYRING_MESSAGE) from None


def _save_stored(store: KeyringTokenStore, login: StoredLogin) -> None:
    try:
        store.save(login)
    except KeyringError:
        raise AuthError(_KEYRING_MESSAGE) from None


def restore_stored_session(
    store: KeyringTokenStore, refresher: FirebaseTokenRefresher
) -> AuthSession | None:
    """Renueva la sesión guardada en el Administrador de credenciales (sin navegador).

    ``None`` si no hay sesión guardada. Un fallo de red conserva la sesión guardada; un rechazo
    de Firebase o un uid inesperado la borran. No necesita el cliente OAuth.
    """
    stored = _load_stored(store)
    if stored is None:
        return None
    try:
        session, rotated = refresher.refresh(stored.refresh_token)
    except SessionExpiredError:
        store.clear()
        raise
    if session.uid != stored.uid:
        store.clear()
        raise AuthError("La sesión guardada pertenece a otro usuario; inicia sesión de nuevo.")
    if rotated != stored.refresh_token:
        _save_stored(store, StoredLogin(uid=stored.uid, refresh_token=rotated))
    return session


class AuthService:
    def __init__(
        self,
        api_key: str,
        client: OAuthClient,
        http: HttpClient,
        token_store: KeyringTokenStore,
        open_browser: Callable[[str], bool] = webbrowser.open,
        clock: Callable[[], datetime] = _utc_now,
        callback_timeout: float = DEFAULT_CALLBACK_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._http = http
        self._store = token_store
        self._open_browser = open_browser
        self._clock = clock
        self._callback_timeout = callback_timeout
        self._refresher = FirebaseTokenRefresher(api_key, http, clock)

    def sign_in(self) -> SignInResult:
        pkce, state, nonce = generate_pkce(), new_token(), new_token()
        with CallbackServer(state) as server:
            url = build_authorization_url(
                self._client, server.redirect_uri, state, nonce, pkce.challenge
            )
            if not self._open_browser(url):
                raise AuthError("No se pudo abrir el navegador del sistema.")
            code = server.wait_for_code(self._callback_timeout)
            redirect_uri = server.redirect_uri

        google_token = exchange_code(self._http, self._client, code, pkce.verifier, redirect_uri)
        identity = validate_google_claims(
            google_token, self._client.client_id, nonce, self._clock()
        )
        login = sign_in_with_google(self._http, self._api_key, google_token, self._clock)

        previous = _load_stored(self._store)
        _save_stored(self._store, StoredLogin(uid=login.uid, refresh_token=login.refresh_token))
        session = AuthSession(
            uid=login.uid,
            email=login.email or identity.email,
            id_token=login.id_token,
            expires_at=login.expires_at,
        )
        return SignInResult(session, uid_changed=previous is not None and previous.uid != login.uid)

    def restore_session(self) -> AuthSession | None:
        """Renueva la sesión guardada. ``None`` si no hay sesión guardada."""
        return restore_stored_session(self._store, self._refresher)

    def sign_out(self) -> None:
        self._store.clear()
