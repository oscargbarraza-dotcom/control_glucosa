"""Intercambio del id_token de Google por una sesión de Firebase (signInWithIdp, REST)."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import requests

from glucosa.errors import AuthError, ConnectionProblem
from glucosa.http import DEFAULT_TIMEOUT_SECONDS, HttpClient
from glucosa.identifiers import is_valid_uid

SIGN_IN_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp"
_MAX_DETAIL = 160


@dataclass(frozen=True)
class FirebaseLogin:
    uid: str
    email: str | None
    id_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _firebase_error(response: Any) -> str:
    """Código/mensaje de error de Firebase (no contiene tokens), acotado y sin control chars."""
    try:
        message = response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return f"HTTP {response.status_code}"
    cleaned = re.sub(r"[^\x20-\x7e]", "", str(message))[:_MAX_DETAIL]
    return cleaned or f"HTTP {response.status_code}"


def sign_in_with_google(
    http: HttpClient,
    api_key: str,
    google_id_token: str,
    clock: Callable[[], datetime] = _utc_now,
) -> FirebaseLogin:
    body = {
        "postBody": urlencode({"id_token": google_id_token, "providerId": "google.com"}),
        "requestUri": "http://localhost",
        "returnSecureToken": True,
    }
    try:
        response = http.post(
            SIGN_IN_URL, params={"key": api_key}, json=body, timeout=DEFAULT_TIMEOUT_SECONDS
        )
    except requests.RequestException:
        # Sin encadenar: el mensaje original puede incluir la URL con la API key.
        raise ConnectionProblem("Sin conexión con Firebase. Revisa tu red.") from None
    if response.status_code == 429 or response.status_code >= 500:
        raise ConnectionProblem("Firebase no está disponible en este momento.")
    if response.status_code != 200:
        raise AuthError(f"Firebase rechazó la credencial de Google ({_firebase_error(response)}).")
    try:
        data = response.json()
    except ValueError:
        raise AuthError("Firebase devolvió una respuesta no válida.") from None
    return _login_from(data, clock)


def _login_from(data: Any, clock: Callable[[], datetime]) -> FirebaseLogin:
    if not isinstance(data, dict) or not data.get("idToken"):
        raise AuthError(
            "Firebase no devolvió una sesión (la cuenta puede requerir confirmación o vinculación)."
        )
    try:
        uid = data["localId"]
        if not is_valid_uid(uid):
            raise AuthError("Firebase devolvió un identificador de usuario inesperado.")
        return FirebaseLogin(
            uid=uid,
            email=data["email"] if isinstance(data.get("email"), str) else None,
            id_token=data["idToken"],
            refresh_token=data["refreshToken"],
            expires_at=clock() + timedelta(seconds=int(data["expiresIn"])),
        )
    except (KeyError, TypeError, ValueError):
        raise AuthError("Firebase devolvió una respuesta incompleta.") from None
