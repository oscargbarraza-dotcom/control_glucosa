"""Acceso a datos de la página Glucosa: Firebase (solo lectura), base LibreView, rango objetivo."""

import pytest
import requests

from glucosa.auth.token_store import KeyringTokenStore, StoredLogin
from glucosa.config import AppConfig
from glucosa.errors import LibreFormatError, SecureStoreError
from glucosa.storage.secure_store import KeyringKeyProvider
from glucosa.ui.glucose_sources import DefaultGlucoseSources, SourceStatus
from tests.fakes import FakeHttp, FakeKeyring, FakeResponse
from tests.libre_fixtures import build_csv, minute_series

UID = "AbCdEf1234567890UidFirebase"


def refresh_response(uid=UID, token="NEW-ID", refresh="ROTATED"):
    return FakeResponse(
        200, {"id_token": token, "refresh_token": refresh, "expires_in": "3600", "user_id": uid}
    )


def firestore_response(*values):
    prefix = f"projects/p/databases/(default)/documents/users/{UID}/glucose_measurements/"
    docs = []
    for index, value in enumerate(values):
        uuid = f"3f2b8c1e-9d4a-4b7e-8a6c-1d2e3f4a5b{index:02d}"
        docs.append(
            {
                "document": {
                    "name": prefix + uuid,
                    "fields": {
                        "uuid": {"stringValue": uuid},
                        "value": {"integerValue": str(value)},
                        "moment": {"stringValue": "now"},
                        "measuredAt": {"stringValue": f"2026-10-2{index}T08:00:00.000000"},
                        "comment": {"nullValue": None},
                    },
                    "createTime": f"2026-10-2{index}T11:00:01Z",
                }
            }
        )
    return FakeResponse(200, docs or [{"readTime": "x"}])


def make_sources(tmp_path, http=None, api_key="API-KEY", stored=True, backend=None):
    backend = backend or FakeKeyring()
    token_store = KeyringTokenStore(backend=backend)
    if stored:
        token_store.save(StoredLogin(uid=UID, refresh_token="OLD"))
    sources = DefaultGlucoseSources(
        config=AppConfig("p", api_key),
        http=http or FakeHttp(),
        token_store=token_store,
        key_provider=KeyringKeyProvider(backend=FakeKeyring()),
        data_dir=tmp_path,
    )
    return sources, token_store


# ---------------------------------------------------------------- Firebase
def test_missing_api_key_is_a_configuration_status_without_network(tmp_path):
    http = FakeHttp()
    sources, _ = make_sources(tmp_path, http, api_key=None)
    result = sources.load_manual()
    assert result.status is SourceStatus.CONFIG and ".env" in result.message
    assert http.calls == []


def test_no_stored_login_means_no_session(tmp_path):
    sources, _ = make_sources(tmp_path, stored=False)
    result = sources.load_manual()
    assert result.status is SourceStatus.NO_SESSION
    assert "glucosa.login" in result.message


def test_manual_records_are_read_with_the_users_own_token_and_session_is_reused(tmp_path):
    http = FakeHttp(
        [refresh_response(), firestore_response(120, 150), firestore_response(120, 150)]
    )
    sources, _ = make_sources(tmp_path, http)

    first = sources.load_manual()
    second = sources.load_manual()

    assert first.status is SourceStatus.OK
    assert [r.value_mg_dl for r in first.records] == [120, 150]
    assert second.status is SourceStatus.OK
    urls = [c["url"] for c in http.calls]
    assert urls[0].startswith("https://securetoken.googleapis.com")
    assert urls[1].endswith(f"users/{UID}:runQuery") and urls[2].endswith(f"users/{UID}:runQuery")
    assert http.calls[1]["headers"]["Authorization"] == "Bearer NEW-ID"
    assert sum("securetoken" in u for u in urls) == 1  # la sesión se reutiliza hasta vencer


def test_rejected_firebase_documents_are_counted_not_hidden(tmp_path):
    bad = firestore_response(120)
    bad.payload[0]["document"]["fields"]["value"] = {"stringValue": "no-es-entero"}
    sources, _ = make_sources(tmp_path, FakeHttp([refresh_response(), bad]))
    result = sources.load_manual()
    assert result.records == () and result.rejected == 1


def test_expired_session_is_reported_and_the_stored_login_is_cleared(tmp_path):
    http = FakeHttp([FakeResponse(400, {"error": {"message": "TOKEN_EXPIRED"}})])
    sources, token_store = make_sources(tmp_path, http)
    result = sources.load_manual()
    assert result.status is SourceStatus.SESSION_EXPIRED and "glucosa.login" in result.message
    assert token_store.load() is None


def test_network_failure_is_an_error_status_and_keeps_the_stored_login(tmp_path):
    sources, token_store = make_sources(tmp_path, FakeHttp([requests.ConnectionError("sin red")]))
    result = sources.load_manual()
    assert result.status is SourceStatus.ERROR and "conexión" in result.message.lower()
    assert token_store.load() is not None


# ----------------------------------------------------------------- LibreView
def test_libreview_is_empty_until_a_csv_is_imported_then_exposes_readings(tmp_path):
    sources, _ = make_sources(tmp_path)
    assert sources.load_libre().status is SourceStatus.EMPTY
    assert sources.libre_signature() is None

    summary = sources.import_csv(
        "Paciente_glucose_23-10-2026.csv", build_csv(minute_series("20-10-2026", 8, 5))
    )
    loaded = sources.load_libre()

    assert summary.new == 5
    assert loaded.status is SourceStatus.OK and len(loaded.readings) == 5
    assert loaded.stats.total == 5 and loaded.stats.last_import_utc is not None
    assert sources.libre_signature() is not None
    assert "Paciente" not in str(loaded.stats) + summary.file_name


def test_importing_the_same_csv_twice_does_not_duplicate_and_changes_the_signature_only_on_writes(
    tmp_path,
):
    sources, _ = make_sources(tmp_path)
    content = build_csv(minute_series("20-10-2026", 8, 5))
    sources.import_csv("a.csv", content)
    first_signature = sources.libre_signature()

    again = sources.import_csv("a.csv", content)

    assert again.new == 0 and len(sources.load_libre().readings) == 5
    assert sources.libre_signature() != first_signature  # se registró la importación


def test_invalid_csv_raises_a_format_error_and_leaves_no_database(tmp_path):
    sources, _ = make_sources(tmp_path)
    with pytest.raises(LibreFormatError):
        sources.import_csv("x.csv", b"a,b\r\n1,2\r\n")
    assert sources.load_libre().status is SourceStatus.EMPTY


# ----------------------------------------------------------- rango objetivo
def test_target_range_defaults_to_70_180_without_a_session(tmp_path):
    sources, _ = make_sources(tmp_path, stored=False)
    assert sources.target_range() == (70, 180)


def test_target_range_is_saved_per_user_and_validated(tmp_path):
    http = FakeHttp([refresh_response(), firestore_response(100)])
    sources, _ = make_sources(tmp_path, http)
    sources.load_manual()  # establece el usuario de la sesión

    sources.save_target_range(80, 160)

    assert sources.target_range() == (80, 160)
    with pytest.raises(ValueError):
        sources.save_target_range(200, 100)
    assert sources.target_range() == (80, 160)


# ------------------------------------------------- D-2: última consulta exitosa
def test_a_successful_manual_load_records_when_firebase_was_queried(tmp_path):
    from datetime import UTC, datetime

    now = datetime(2026, 10, 26, 18, 0, tzinfo=UTC)
    sources, _ = make_sources(tmp_path, FakeHttp([refresh_response(), firestore_response(100)]))
    sources._clock = lambda: now

    result = sources.load_manual()

    assert result.status is SourceStatus.OK and result.fetched_at == now


def test_failed_loads_do_not_claim_a_query_time(tmp_path):
    sources, _ = make_sources(tmp_path, stored=False)
    assert sources.load_manual().fetched_at is None


# ------------------------------------------- cierre de sesión por línea de comandos
def test_session_marker_follows_the_stored_login(tmp_path):
    sources, token_store = make_sources(tmp_path)
    first = sources.session_marker()
    assert first is not None and UID not in first  # no expone el uid

    token_store.clear()
    assert sources.session_marker() is None

    token_store.save(StoredLogin(uid="OtraCuenta9999999999", refresh_token="X"))
    assert sources.session_marker() not in (None, first)


def test_logging_out_from_the_cli_ends_the_running_session_without_using_the_network(tmp_path):
    http = FakeHttp([refresh_response(), firestore_response(100)])
    sources, token_store = make_sources(tmp_path, http)
    assert sources.load_manual().status is SourceStatus.OK
    calls_before = len(http.calls)

    token_store.clear()
    result = sources.load_manual()

    assert result.status is SourceStatus.NO_SESSION and len(http.calls) == calls_before
    assert sources.target_range_info().notice  # ya no hay sesión: se avisa


def test_switching_account_from_the_cli_drops_the_previous_users_session(tmp_path):
    other = "OtraCuenta9999999999"
    http = FakeHttp([refresh_response(), firestore_response(100)])
    sources, token_store = make_sources(tmp_path, http)
    sources.load_manual()
    sources.save_target_range(80, 160)

    token_store.save(StoredLogin(uid=other, refresh_token="NUEVO"))
    http.responses = [
        refresh_response(uid=other, token="ID-2"),
        FakeResponse(200, [{"readTime": "x"}]),
    ]
    sources.load_manual()

    assert sources.target_range() == (70, 180)  # no hereda el rango del usuario anterior
    assert http.calls[-1]["headers"]["Authorization"] == "Bearer ID-2"


# --------------------------------------------------- M-7: rango por defecto avisado
def test_target_range_info_says_why_the_default_range_is_used(tmp_path):
    sources, _ = make_sources(tmp_path, stored=False)
    info = sources.target_range_info()
    assert (info.low, info.high) == (70, 180)
    assert "sesión" in info.notice.lower() and "70" in info.notice


def test_target_range_info_has_no_notice_when_the_saved_range_is_read(tmp_path):
    sources, _ = make_sources(tmp_path, FakeHttp([refresh_response(), firestore_response(100)]))
    sources.load_manual()
    sources.save_target_range(80, 160)

    info = sources.target_range_info()

    assert (info.low, info.high, info.notice) == (80, 160, None)


def test_unreadable_settings_fall_back_to_the_default_with_a_notice(tmp_path):
    sources, _ = make_sources(tmp_path, FakeHttp([refresh_response(), firestore_response(100)]))
    sources.load_manual()
    sources.save_target_range(80, 160)
    for path in tmp_path.rglob("settings.enc"):
        path.write_bytes(b"corrupto")

    info = sources.target_range_info()

    assert (info.low, info.high) == (70, 180) and "ilegible" in info.notice.lower()


# ------------------------------------------------- M-6: guardar con ajustes dañados
def test_saving_with_unreadable_settings_fails_cleanly_and_does_not_overwrite_them(tmp_path):
    sources, _ = make_sources(tmp_path, FakeHttp([refresh_response(), firestore_response(100)]))
    sources.load_manual()
    sources.save_target_range(80, 160)
    path = next(tmp_path.rglob("settings.enc"))
    path.write_bytes(b"corrupto")

    with pytest.raises(SecureStoreError, match="No se guardó"):
        sources.save_target_range(90, 150)

    assert path.read_bytes() == b"corrupto"


# --------------------------- INFO-9: no crear claves nuevas si ya hay datos cifrados
def test_saving_settings_never_creates_a_new_key_when_the_libreview_database_exists(tmp_path):
    sources, _ = make_sources(tmp_path)
    sources.import_csv("a.csv", build_csv(minute_series("20-10-2026", 8, 5)))  # crea base y clave

    lost_key_backend = FakeKeyring()  # el Administrador de credenciales perdió la clave
    token_store = KeyringTokenStore(backend=FakeKeyring())
    token_store.save(StoredLogin(uid=UID, refresh_token="OLD"))
    orphaned = DefaultGlucoseSources(
        config=AppConfig("p", "API-KEY"),
        http=FakeHttp([refresh_response(), firestore_response(100)]),
        token_store=token_store,
        key_provider=KeyringKeyProvider(backend=lost_key_backend),
        data_dir=tmp_path,
    )
    orphaned.load_manual()

    with pytest.raises(SecureStoreError):
        orphaned.save_target_range(80, 160)

    assert lost_key_backend.store == {}  # no se generó ninguna clave


# ------------------------------------ errores locales: estado ERROR, nunca excepción
def test_a_data_folder_inside_onedrive_is_an_error_status_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("OneDrive", str(tmp_path))
    monkeypatch.setenv("GLUCOSA_DATA_DIR", str(tmp_path / "datos"))
    sources = DefaultGlucoseSources(config=AppConfig("p", "K"), http=FakeHttp())

    assert sources.libre_signature() is None
    loaded = sources.load_libre()
    assert loaded.status is SourceStatus.ERROR and "OneDrive" in loaded.message


def test_a_keyring_failure_is_an_error_status_not_a_crash(tmp_path):
    from keyring.errors import KeyringError

    class BrokenKeys:
        def key(self, create=True):
            raise KeyringError("sin acceso")

    sources, _ = make_sources(tmp_path)
    sources.import_csv("a.csv", build_csv(minute_series("20-10-2026", 8, 5)))
    sources._key_provider = BrokenKeys()

    loaded = sources.load_libre()

    assert loaded.status is SourceStatus.ERROR and "credenciales" in loaded.message.lower()


def test_an_invalid_firebase_project_id_is_an_error_status(tmp_path):
    sources, _ = make_sources(tmp_path, FakeHttp([refresh_response()]))
    sources._config = AppConfig("PROYECTO INVÁLIDO!", "API-KEY")

    result = sources.load_manual()

    assert result.status is SourceStatus.ERROR and result.message
