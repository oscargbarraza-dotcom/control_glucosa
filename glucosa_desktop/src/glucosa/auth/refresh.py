"""Renovación del ID token de Firebase con el refresh token (API securetoken).

No necesita OAuth de Google ni configuración adicional: usa la API key pública
del proyecto. Distingue "hay que iniciar sesión de nuevo" de "no hay conexión"
para no cerrar la sesión por una caída de red.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import requests

from glucosa.auth.session import AuthSession
from glucosa.errors import AuthError, ConnectionProblem, SessionExpiredError
from glucosa.http import DEFAULT_TIMEOUT_SECONDS, HttpClient, HttpResponse
from glucosa.identifiers import is_valid_uid

TOKEN_URL = "https://securetoken.googleapis.com/v1/token"
_REJECTED_TOKEN_CODES = frozenset(
    {"TOKEN_EXPIRED", "USER_DISABLED", "USER_NOT_FOUND", "INVALID_REFRESH_TOKEN"}
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class FirebaseTokenRefresher:
    def __init__(
        self,
        api_key: str,
        http: HttpClient,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._api_key = api_key
        self._http = http
        self._clock = clock

    def refresh(self, refresh_token: str) -> tuple[AuthSession, str]:
        """Devuelve la nueva sesión y el refresh token vigente (puede rotar)."""
        try:
            response = self._http.post(
                TOKEN_URL,
                params={"key": self._api_key},
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            # Sin encadenar: el mensaje original puede incluir la URL con la API key.
            raise ConnectionProblem("Sin conexión con Firebase. Revisa tu red.") from None

        status = response.status_code
        if status == 429 or status >= 500:
            raise ConnectionProblem("Firebase no está disponible en este momento.")
        if status != 200:
            self._raise_for_rejection(response)

        try:
            body = response.json()
            if not is_valid_uid(body["user_id"]):
                raise AuthError("Firebase devolvió un identificador de usuario inesperado.")
            session = AuthSession(
                uid=body["user_id"],
                email=None,
                id_token=body["id_token"],
                expires_at=self._clock() + timedelta(seconds=int(body["expires_in"])),
            )
            return session, body["refresh_token"]
        except (ValueError, KeyError, TypeError):
            raise AuthError(
                "Firebase devolvió una respuesta inesperada al renovar la sesión."
            ) from None

    @staticmethod
    def _raise_for_rejection(response: HttpResponse) -> None:
        try:
            message = str(response.json().get("error", {}).get("message", ""))
        except (ValueError, AttributeError):
            message = ""
        if message in _REJECTED_TOKEN_CODES:
            raise SessionExpiredError("Tu sesión venció. Inicia sesión nuevamente.")
        raise AuthError(f"No se pudo renovar la sesión (HTTP {response.status_code}).")
