"""Carga de comidas desde Firebase: solo lectura, una consulta, mismo manejo de sesión que Glucosa."""

import requests

from glucosa.auth.token_store import StoredLogin
from glucosa.models.records import MealType
from glucosa.ui.glucose_sources import SourceStatus
from tests.fakes import FakeHttp, FakeResponse
from tests.test_glucose_sources import UID, firestore_response, make_sources, refresh_response


def meal_document(index, kind="lunch", foods=(("Arroz", "1 tz"),), comment=None):
    uuid = f"3f2b8c1e-9d4a-4b7e-8a6c-1d2e3f4a5c{index:02d}"
    items = [
        {"mapValue": {"fields": {"foodName": {"stringValue": n}, "quantity": {"stringValue": q}}}}
        for n, q in foods
    ]
    prefix = f"projects/p/databases/(default)/documents/users/{UID}/meals/"
    return {
        "document": {
            "name": prefix + uuid,
            "fields": {
                "uuid": {"stringValue": uuid},
                "type": {"stringValue": kind},
                "eatenAt": {"stringValue": f"2026-10-2{index}T13:30:00.000000"},
                "comment": {"stringValue": comment} if comment else {"nullValue": None},
                "items": {"arrayValue": {"values": items}},
            },
            "createTime": f"2026-10-2{index}T16:30:01Z",
        }
    }


def meals_response(*documents):
    return FakeResponse(200, list(documents) or [{"readTime": "x"}])


def test_meals_are_read_with_the_users_own_token_in_one_read_only_query(tmp_path):
    http = FakeHttp(
        [refresh_response(), meals_response(meal_document(0), meal_document(1, "dinner"))]
    )
    sources, _ = make_sources(tmp_path, http)

    result = sources.load_meals()

    assert result.status is SourceStatus.OK
    assert [r.type for r in result.records] == [MealType.LUNCH, MealType.DINNER]
    assert [len(r.items) for r in result.records] == [1, 1]
    urls = [c["url"] for c in http.calls]
    assert urls[0].startswith("https://securetoken.googleapis.com")
    assert urls[1].endswith(f"users/{UID}:runQuery") and len(urls) == 2  # una sola consulta
    assert http.calls[1]["headers"]["Authorization"] == "Bearer NEW-ID"
    assert "meals" in str(http.calls[1]["json"])  # consulta la colección de comidas


def test_the_loader_never_writes_to_firebase(tmp_path):
    http = FakeHttp([refresh_response(), meals_response(meal_document(0))])
    sources, _ = make_sources(tmp_path, http)

    sources.load_meals()

    for call in http.calls:
        url = call["url"]
        assert (
            url.endswith(":runQuery") or "securetoken" in url
        )  # solo lectura y renovación del token
        assert not any(w in url for w in (":commit", ":batchWrite", ":write", ":beginTransaction"))


def test_the_session_is_shared_with_the_glucose_loader(tmp_path):
    http = FakeHttp([refresh_response(), firestore_response(100), meals_response(meal_document(0))])
    sources, _ = make_sources(tmp_path, http)

    sources.load_manual()
    sources.load_meals()

    assert (
        sum("securetoken" in c["url"] for c in http.calls) == 1
    )  # el token se renovó una sola vez
    assert len(http.calls) == 3


def test_load_time_is_recorded_only_for_a_successful_query(tmp_path):
    from datetime import UTC, datetime

    now = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)
    sources, _ = make_sources(
        tmp_path, FakeHttp([refresh_response(), meals_response(meal_document(0))])
    )
    sources._clock = lambda: now

    assert sources.load_meals().fetched_at == now

    no_session, _ = make_sources(tmp_path, stored=False)
    assert no_session.load_meals().fetched_at is None


def test_no_stored_login_means_no_session_and_no_network(tmp_path):
    http = FakeHttp()
    sources, _ = make_sources(tmp_path, http, stored=False)

    result = sources.load_meals()

    assert result.status is SourceStatus.NO_SESSION and "glucosa.login" in result.message
    assert http.calls == [] and result.records == ()


def test_missing_api_key_is_a_configuration_status_without_network(tmp_path):
    http = FakeHttp()
    sources, _ = make_sources(tmp_path, http, api_key=None)

    result = sources.load_meals()

    assert result.status is SourceStatus.CONFIG and http.calls == []


def test_expired_session_is_reported_and_clears_the_stored_login(tmp_path):
    http = FakeHttp([FakeResponse(400, {"error": {"message": "TOKEN_EXPIRED"}})])
    sources, token_store = make_sources(tmp_path, http)

    result = sources.load_meals()

    assert result.status is SourceStatus.SESSION_EXPIRED and token_store.load() is None


def test_network_failure_is_an_error_status_and_keeps_the_login(tmp_path):
    sources, token_store = make_sources(tmp_path, FakeHttp([requests.ConnectionError("sin red")]))

    result = sources.load_meals()

    assert result.status is SourceStatus.ERROR and token_store.load() is not None


def test_permission_denied_is_an_error_status(tmp_path):
    http = FakeHttp([refresh_response(), FakeResponse(403, {"error": {"message": "denegado"}})])
    sources, _ = make_sources(tmp_path, http)

    assert sources.load_meals().status is SourceStatus.ERROR


def test_logging_out_from_the_cli_stops_meal_reads_without_the_network(tmp_path):
    http = FakeHttp([refresh_response(), meals_response(meal_document(0))])
    sources, token_store = make_sources(tmp_path, http)
    assert sources.load_meals().status is SourceStatus.OK
    calls = len(http.calls)

    token_store.clear()

    assert sources.load_meals().status is SourceStatus.NO_SESSION and len(http.calls) == calls


def test_switching_account_uses_the_new_users_session(tmp_path):
    other = "OtraCuenta9999999999"
    http = FakeHttp([refresh_response(), meals_response(meal_document(0))])
    sources, token_store = make_sources(tmp_path, http)
    sources.load_meals()

    token_store.save(StoredLogin(uid=other, refresh_token="NUEVO"))
    http.responses = [refresh_response(uid=other, token="ID-2"), meals_response()]
    result = sources.load_meals()

    assert result.status is SourceStatus.OK and result.records == ()
    assert http.calls[-1]["headers"]["Authorization"] == "Bearer ID-2"


def test_documents_that_fail_validation_are_counted_not_hidden_and_warnings_are_counted(tmp_path):
    broken = meal_document(0)
    broken["document"]["fields"]["eatenAt"] = {"stringValue": "no-es-fecha"}
    empty = meal_document(1, foods=())
    http = FakeHttp([refresh_response(), meals_response(broken, empty)])
    sources, _ = make_sources(tmp_path, http)

    result = sources.load_meals()

    assert result.status is SourceStatus.OK
    assert result.rejected == 1 and len(result.records) == 1
    assert result.warnings >= 1  # la comida sin alimentos se avisa pero se conserva


def test_an_empty_collection_is_ok_with_no_records(tmp_path):
    sources, _ = make_sources(tmp_path, FakeHttp([refresh_response(), meals_response()]))

    result = sources.load_meals()

    assert result.status is SourceStatus.OK and result.records == () and result.rejected == 0


def test_glucose_loading_still_behaves_exactly_as_before(tmp_path):
    http = FakeHttp([refresh_response(), firestore_response(120, 150)])
    sources, _ = make_sources(tmp_path, http)

    result = sources.load_manual()

    assert result.status is SourceStatus.OK and [r.value_mg_dl for r in result.records] == [
        120,
        150,
    ]
