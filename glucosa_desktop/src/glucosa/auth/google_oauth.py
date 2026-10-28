"""OAuth 2.0 para apps de escritorio (loopback + PKCE) con Google.

Diseño y justificación en ``PROJECT_CONTEXT.md`` (sección 7). Puntos clave:

* PKCE (S256), ``state`` y ``nonce`` generados con ``secrets``.
* Callback local solo en ``127.0.0.1``, puerto asignado por el sistema, sin
  reutilización de puerto (``SO_EXCLUSIVEADDRUSE`` en Windows). Sigue
  escuchando hasta recibir un ``state`` válido: una petición local ajena no
  puede consumir el intento. No registra la URL (el ``code`` viaja en ella) ni
  refleja parámetros en la respuesta.
* Solo se pide ``openid email`` y no se solicita acceso offline: no hay
  refresh token de Google. Los tokens de Google viven únicamente en variables
  locales.
"""

import base64
import binascii
import hashlib
import json
import re
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import requests

from glucosa.auth.oauth_client import OAuthClient
from glucosa.errors import AuthError, ConnectionProblem, OAuthDenied, OAuthTimeout
from glucosa.http import DEFAULT_TIMEOUT_SECONDS, HttpClient

SCOPE = "openid email"
CALLBACK_PATH = "/callback"
GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
_POLL_SECONDS = 0.2

_SUCCESS_PAGE = (
    "<!doctype html><meta charset='utf-8'><title>_glucosa</title>"
    "<p>Inicio de sesión completado. Ya puedes cerrar esta pestaña y volver a la aplicación.</p>"
)
_CANCEL_PAGE = (
    "<!doctype html><meta charset='utf-8'><title>_glucosa</title>"
    "<p>Autorización cancelada. Puedes cerrar esta pestaña.</p>"
)
_INVALID_PAGE = (
    "<!doctype html><meta charset='utf-8'><title>_glucosa</title><p>Solicitud no válida.</p>"
)


# ------------------------------------------------------------------ PKCE
@dataclass(frozen=True)
class Pkce:
    verifier: str
    challenge: str


def new_token() -> str:
    """Valor aleatorio (86 caracteres URL-safe) para verifier, state o nonce."""
    return secrets.token_urlsafe(64)


def generate_pkce() -> Pkce:
    verifier = new_token()
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return Pkce(verifier=verifier, challenge=challenge)


def build_authorization_url(
    client: OAuthClient, redirect_uri: str, state: str, nonce: str, challenge: str
) -> str:
    query = urlencode(
        {
            "client_id": client.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    return f"{client.auth_uri}?{query}"


# ------------------------------------------------- servidor de callback local
class _LoopbackServer(ThreadingHTTPServer):
    """Un hilo por conexión: un socket inactivo no puede bloquear la petición real."""

    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, expected_state: str) -> None:
        self.expected_state = expected_state
        self.outcome: tuple[str, str] | None = None
        self._claim_lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), _CallbackHandler)

    def claim(self, kind: str, value: str) -> bool:
        """Registra el primer resultado válido; los siguientes se rechazan."""
        with self._claim_lock:
            if self.outcome is not None:
                return False
            self.outcome = (kind, value)
            return True

    def server_bind(self) -> None:
        # En Windows, SO_REUSEADDR permite que otro proceso comparta el puerto.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class _CallbackHandler(BaseHTTPRequestHandler):
    server: _LoopbackServer
    timeout = 5  # segundos por conexión: libera sockets inactivos

    def log_message(self, format: str, *args: Any) -> None:
        """Sin registro: la línea de petición contiene el código de autorización."""

    def _reply(self, status: int, page: str) -> None:
        body = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        params = parse_qs(parsed.query)
        state = params.get("state", [""])[0]
        valid_state = secrets.compare_digest(
            state.encode("utf-8"), self.server.expected_state.encode("utf-8")
        )
        if parsed.path != CALLBACK_PATH or not valid_state:
            self._reply(400, _INVALID_PAGE)
            return
        if "error" in params:
            accepted = self.server.claim("error", params["error"][0][:100])
            page = _CANCEL_PAGE
        else:
            code = params.get("code", [""])[0]
            accepted = bool(code) and self.server.claim("code", code)
            page = _SUCCESS_PAGE
        if accepted:
            self._reply(200, page)
        else:
            self._reply(400, _INVALID_PAGE)


class CallbackServer:
    """Recibe la redirección de Google en ``http://127.0.0.1:<puerto>/callback``."""

    def __init__(self, expected_state: str) -> None:
        self._server = _LoopbackServer(expected_state)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.port}{CALLBACK_PATH}"

    def wait_for_code(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        self._server.timeout = _POLL_SECONDS
        while self._server.outcome is None:
            if time.monotonic() >= deadline:
                raise OAuthTimeout("Se agotó el tiempo esperando la autorización en el navegador.")
            self._server.handle_request()
        kind, value = self._server.outcome
        if kind == "error":
            raise OAuthDenied(f"La autorización fue cancelada o rechazada ({value}).")
        return value

    def close(self) -> None:
        self._server.server_close()

    def __enter__(self) -> "CallbackServer":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# ------------------------------------------- intercambio del código por token
def exchange_code(
    http: HttpClient, client: OAuthClient, code: str, verifier: str, redirect_uri: str
) -> str:
    """Canjea el código por el ``id_token`` de Google (el ``access_token`` se descarta)."""
    try:
        response = http.post(
            client.token_uri,
            data={
                "code": code,
                "client_id": client.client_id,
                "client_secret": client.client_secret,
                "code_verifier": verifier,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise ConnectionProblem("Sin conexión con Google. Revisa tu red.") from None
    if response.status_code != 200:
        raise AuthError(f"Google rechazó el intercambio del código{_error_code(response)}.")
    try:
        id_token = response.json().get("id_token")
    except (ValueError, AttributeError):
        id_token = None
    if not isinstance(id_token, str) or not id_token:
        raise AuthError("Google no devolvió un id_token.")
    return id_token


def _error_code(response: Any) -> str:
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return ""
    if isinstance(error, str) and re.fullmatch(r"[a-z_]{1,40}", error):
        return f" ({error})"
    return ""


# ----------------------------------------------------- claims del id_token
@dataclass(frozen=True)
class GoogleIdentity:
    email: str | None


def _decode_claims(id_token: str) -> dict[str, Any]:
    parts = id_token.split(".") if isinstance(id_token, str) else []
    if len(parts) != 3:
        raise AuthError("El id_token de Google tiene un formato inválido.")
    try:
        payload = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        claims = json.loads(payload)
    except (binascii.Error, ValueError):
        raise AuthError("El id_token de Google tiene un formato inválido.") from None
    if not isinstance(claims, dict):
        raise AuthError("El id_token de Google tiene un formato inválido.")
    return claims


def validate_google_claims(
    id_token: str, client_id: str, nonce: str, now: datetime
) -> GoogleIdentity:
    """Comprueba aud, iss, exp, nonce y email verificado.

    La firma NO se verifica aquí: la verifica Firebase al canjear el token.
    Estas comprobaciones son una defensa adicional barata.
    """
    claims = _decode_claims(id_token)
    expires = claims.get("exp")
    token_nonce = claims.get("nonce")
    checks = {
        "audiencia": claims.get("aud") == client_id,
        "emisor": claims.get("iss") in GOOGLE_ISSUERS,
        "vigencia": isinstance(expires, int | float)
        and not isinstance(expires, bool)
        and expires > now.timestamp(),
        "nonce": isinstance(token_nonce, str)
        and secrets.compare_digest(token_nonce.encode("utf-8"), nonce.encode("utf-8")),
        "correo verificado": claims.get("email_verified") is True,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise AuthError(f"El id_token de Google no es válido ({', '.join(failed)}).")
    email = claims.get("email")
    return GoogleIdentity(email=email if isinstance(email, str) else None)
