"""Sesión, almacenamiento del refresh token y renovación (sin OAuth todavía)."""

from datetime import UTC, datetime, timedelta

import pytest
import requests

from glucosa.auth.refresh import FirebaseTokenRefresher
from glucosa.auth.session import AuthSession
from glucosa.auth.token_store import KeyringTokenStore, StoredLogin
from glucosa.errors import ConnectionProblem, SessionExpiredError
from tests.fakes import FakeHttp, FakeKeyring, FakeResponse

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def test_session_expiry_uses_safety_margin():
    session = AuthSession(uid="u", email=None, id_token="t", expires_at=NOW + timedelta(seconds=30))
    assert session.is_expired(NOW) is True  # a menos de 60 s se considera vencida
    assert session.is_expired(NOW - timedelta(minutes=5)) is False


def test_session_repr_hides_token():
    session = AuthSession(uid="u", email=None, id_token="TOKEN-SECRETO", expires_at=NOW)
    assert "TOKEN-SECRETO" not in repr(session)


def test_token_store_round_trip_and_delete():
    store = KeyringTokenStore(backend=FakeKeyring())
    assert store.load() is None
    store.save(StoredLogin(uid="uid123", refresh_token="r-1"))
    assert store.load() == StoredLogin(uid="uid123", refresh_token="r-1")
    store.clear()
    assert store.load() is None


def test_token_store_ignores_corrupt_entry():
    backend = FakeKeyring()
    backend.set_password("glucosa", "session", "{no es json")
    assert KeyringTokenStore(backend=backend).load() is None


def refresher(http):
    return FirebaseTokenRefresher(api_key="KEY", http=http, clock=lambda: NOW)


def test_refresh_returns_new_session_and_rotated_refresh_token():
    http = FakeHttp(
        [
            FakeResponse(
                200,
                {
                    "id_token": "new-id",
                    "refresh_token": "new-r",
                    "expires_in": "3600",
                    "user_id": "uid123",
                },
            )
        ]
    )
    session, rotated = refresher(http).refresh("old-r")

    assert session.uid == "uid123"
    assert session.id_token == "new-id"
    assert session.expires_at == NOW + timedelta(seconds=3600)
    assert rotated == "new-r"
    call = http.calls[0]
    assert call["url"].startswith("https://securetoken.googleapis.com/v1/token")
    assert call["params"] == {"key": "KEY"}
    assert call["data"] == {"grant_type": "refresh_token", "refresh_token": "old-r"}


@pytest.mark.parametrize(
    "code", ["TOKEN_EXPIRED", "USER_DISABLED", "USER_NOT_FOUND", "INVALID_REFRESH_TOKEN"]
)
def test_rejected_refresh_token_requires_new_login(code):
    http = FakeHttp([FakeResponse(400, {"error": {"message": code}})])
    with pytest.raises(SessionExpiredError):
        refresher(http).refresh("r")


def test_network_failure_is_a_connection_problem_not_a_logout():
    http = FakeHttp([requests.ConnectionError("sin red")])
    with pytest.raises(ConnectionProblem):
        refresher(http).refresh("r")


def test_server_error_is_a_connection_problem():
    http = FakeHttp([FakeResponse(503, {})])
    with pytest.raises(ConnectionProblem):
        refresher(http).refresh("r")
