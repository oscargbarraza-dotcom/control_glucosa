"""OAuth 2.0 de escritorio con PKCE: parámetros, servidor de callback, intercambio y claims."""

import base64
import hashlib
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
import requests

from glucosa.auth.google_oauth import (
    CallbackServer,
    build_authorization_url,
    exchange_code,
    generate_pkce,
    new_token,
    validate_google_claims,
)
from glucosa.auth.oauth_client import OAuthClient
from glucosa.errors import AuthError, ConnectionProblem, OAuthDenied, OAuthTimeout
from tests.fakes import FakeHttp, FakeResponse, make_jwt

CLIENT = OAuthClient(client_id="123-abc.apps.googleusercontent.com", client_secret="SECRETO-OAUTH")
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------- PKCE
def test_pkce_challenge_is_s256_of_a_long_random_verifier():
    pkce = generate_pkce()
    digest = hashlib.sha256(pkce.verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    assert pkce.challenge == expected
    assert 43 <= len(pkce.verifier) <= 128
    assert generate_pkce().verifier != pkce.verifier


def test_random_tokens_are_unique_and_url_safe():
    first, second = new_token(), new_token()
    assert first != second
    assert len(first) >= 43
    assert all(c.isalnum() or c in "-_" for c in first)


def test_authorization_url_has_pkce_state_nonce_and_minimal_scope():
    url = build_authorization_url(
        CLIENT, "http://127.0.0.1:5555/callback", state="S", nonce="N", challenge="C"
    )
    parts = urllib.parse.urlsplit(url)
    query = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}

    assert (
        f"{parts.scheme}://{parts.netloc}{parts.path}"
        == "https://accounts.google.com/o/oauth2/auth"
    )
    assert query == {
        "client_id": CLIENT.client_id,
        "redirect_uri": "http://127.0.0.1:5555/callback",
        "response_type": "code",
        "scope": "openid email",
        "state": "S",
        "nonce": "N",
        "code_challenge": "C",
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    assert "access_type" not in query  # sin refresh token de Google
    assert "SECRETO-OAUTH" not in url


# --------------------------------------------------- servidor de callback local
def fetch(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.read().decode("utf-8")


def test_server_listens_only_on_loopback_on_a_system_assigned_port():
    with CallbackServer(expected_state="S") as server:
        assert server.redirect_uri.startswith("http://127.0.0.1:")
        assert server.port > 0
        host = server._server.server_address[0]  # noqa: SLF001
        assert host == "127.0.0.1"


def test_server_ignores_bad_requests_and_still_accepts_the_valid_callback():
    with CallbackServer(expected_state="STATE-OK") as server, ThreadPoolExecutor(1) as pool:
        waiting = pool.submit(server.wait_for_code, 10)
        base = server.redirect_uri

        assert fetch(base.replace("/callback", "/otra-ruta"))[0] == 400
        assert fetch(f"{base}?code=ROBADO&state=ESTADO-MALO")[0] == 400
        assert fetch(f"{base}?code=SIN-STATE")[0] == 400
        assert not waiting.done()  # una petición ajena no consume el intento

        status, _ = fetch(f"{base}?code=CODIGO-REAL&state=STATE-OK")
        assert status == 200
        assert waiting.result(timeout=5) == "CODIGO-REAL"


def test_server_response_never_reflects_query_parameters_and_sets_secure_headers():
    with CallbackServer(expected_state="S") as server:
        payload = urllib.parse.quote("<script>alert(1)</script>")
        threading.Thread(target=server.wait_for_code, args=(2,), daemon=True).start()
        request = urllib.request.Request(f"{server.redirect_uri}?code={payload}&state=S")
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
            headers = response.headers
        assert "<script>" not in body and "alert" not in body
        assert headers["Cache-Control"] == "no-store"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["X-Content-Type-Options"] == "nosniff"


def test_user_cancelling_in_the_browser_raises_oauth_denied():
    with CallbackServer(expected_state="S") as server, ThreadPoolExecutor(1) as pool:
        waiting = pool.submit(server.wait_for_code, 10)
        fetch(f"{server.redirect_uri}?error=access_denied&state=S")
        with pytest.raises(OAuthDenied):
            waiting.result(timeout=5)


def test_wait_times_out_when_nothing_arrives():
    with CallbackServer(expected_state="S") as server, pytest.raises(OAuthTimeout):
        server.wait_for_code(timeout=0.4)


def test_a_second_valid_callback_cannot_replace_the_first_code():
    with CallbackServer(expected_state="S") as server, ThreadPoolExecutor(1) as pool:
        waiting = pool.submit(server.wait_for_code, 10)
        assert fetch(f"{server.redirect_uri}?code=PRIMERO&state=S")[0] == 200
        assert waiting.result(timeout=5) == "PRIMERO"


# ------------------------------------------------- intercambio del código por token
def test_code_exchange_sends_pkce_verifier_and_returns_only_the_id_token():
    http = FakeHttp([FakeResponse(200, {"id_token": "ID-GOOGLE", "access_token": "NO-USAR"})])

    token = exchange_code(http, CLIENT, "CODE", "VERIFIER", "http://127.0.0.1:1/callback")

    assert token == "ID-GOOGLE"
    call = http.calls[0]
    assert call["url"] == "https://oauth2.googleapis.com/token"
    assert call["data"] == {
        "code": "CODE",
        "client_id": CLIENT.client_id,
        "client_secret": "SECRETO-OAUTH",
        "code_verifier": "VERIFIER",
        "redirect_uri": "http://127.0.0.1:1/callback",
        "grant_type": "authorization_code",
    }


def test_rejected_exchange_reports_only_the_error_code_not_secrets():
    http = FakeHttp([FakeResponse(400, {"error": "invalid_grant", "error_description": "Bad"})])
    with pytest.raises(AuthError) as info:
        exchange_code(http, CLIENT, "CODE", "V", "http://127.0.0.1:1/callback")
    assert "invalid_grant" in str(info.value)
    assert "SECRETO-OAUTH" not in str(info.value)


def test_exchange_without_id_token_or_with_network_failure_are_domain_errors():
    with pytest.raises(AuthError):
        exchange_code(FakeHttp([FakeResponse(200, {})]), CLIENT, "C", "V", "http://127.0.0.1:1/c")
    with pytest.raises(ConnectionProblem) as info:
        exchange_code(
            FakeHttp([requests.ConnectionError("fallo con SECRETO-OAUTH")]),
            CLIENT,
            "C",
            "V",
            "http://127.0.0.1:1/c",
        )
    assert info.value.__cause__ is None


# --------------------------------------------------------- claims del id_token
def good_claims(**overrides):
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT.client_id,
        "exp": int((NOW + timedelta(minutes=30)).timestamp()),
        "nonce": "NONCE",
        "email": "persona@gmail.com",
        "email_verified": True,
    }
    claims.update(overrides)
    return claims


def test_valid_claims_return_the_email():
    identity = validate_google_claims(make_jwt(good_claims()), CLIENT.client_id, "NONCE", NOW)
    assert identity.email == "persona@gmail.com"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "otro-cliente.apps.googleusercontent.com"},
        {"iss": "https://evil.example.com"},
        {"exp": 1},
        {"nonce": "OTRO"},
        {"nonce": None},
        {"email_verified": False},
        {"email_verified": "true"},
    ],
)
def test_tampered_or_stale_claims_are_rejected(overrides):
    with pytest.raises(AuthError):
        validate_google_claims(make_jwt(good_claims(**overrides)), CLIENT.client_id, "NONCE", NOW)


@pytest.mark.parametrize("bad", ["", "una.sola", "a.b.c.d", "no-es-jwt", "###.###.###"])
def test_malformed_tokens_are_rejected(bad):
    with pytest.raises(AuthError):
        validate_google_claims(bad, CLIENT.client_id, "NONCE", NOW)


def test_idle_connection_does_not_block_the_valid_callback():
    # Un navegador puede abrir una conexión especulativa y no enviar nada.
    with CallbackServer(expected_state="S") as server, ThreadPoolExecutor(1) as pool:
        idle = socket.create_connection(("127.0.0.1", server.port))
        try:
            waiting = pool.submit(server.wait_for_code, 10)
            started = time.monotonic()
            assert fetch(f"{server.redirect_uri}?code=OK&state=S")[0] == 200
            assert waiting.result(timeout=5) == "OK"
            assert time.monotonic() - started < 3
        finally:
            idle.close()


def test_only_the_first_valid_callback_wins_when_two_arrive_together():
    with CallbackServer(expected_state="S") as server, ThreadPoolExecutor(2) as pool:
        waiting = pool.submit(server.wait_for_code, 10)
        urls = [f"{server.redirect_uri}?code=C{i}&state=S" for i in range(2)]
        statuses = sorted(s for s, _ in pool.map(fetch, urls))
        assert statuses == [200, 400]
        assert waiting.result(timeout=5) in {"C0", "C1"}
