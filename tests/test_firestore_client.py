"""Cliente REST de Firestore: solo lectura, con el token del propio usuario."""

import pytest
import requests

from glucosa.data.firestore_client import FirestoreReader
from glucosa.errors import (
    ConnectionProblem,
    GlucosaError,
    PermissionDeniedError,
    SessionExpiredError,
)
from tests.fakes import FakeHttp, FakeResponse

UID = "Abc123XyzUid4567890"
PREFIX = "projects/p/databases/(default)/documents/users/" + UID + "/glucose_measurements/"


def raw_doc(doc_id: str, measured_at: str, value: int = 100) -> dict:
    return {
        "document": {
            "name": PREFIX + doc_id,
            "fields": {
                "value": {"integerValue": str(value)},
                "measuredAt": {"stringValue": measured_at},
            },
            "createTime": "2026-10-23T14:00:00Z",
            "updateTime": "2026-10-23T14:00:00Z",
        },
        "readTime": "2026-10-23T14:05:00Z",
    }


def reader(http: FakeHttp) -> FirestoreReader:
    return FirestoreReader(project_id="p", http=http)


def test_query_sends_bearer_token_and_targets_user_scoped_runquery():
    http = FakeHttp([FakeResponse(200, [raw_doc("a", "2026-08-07T10:00:00.000")])])

    docs = reader(http).query_collection(
        UID, "glucose_measurements", "TOKEN", order_field="measuredAt"
    )

    call = http.calls[0]
    assert call["url"] == (
        "https://firestore.googleapis.com/v1/projects/p/databases/(default)/documents/users/"
        f"{UID}:runQuery"
    )
    assert call["headers"]["Authorization"] == "Bearer TOKEN"
    assert call["json"]["structuredQuery"]["from"] == [{"collectionId": "glucose_measurements"}]
    assert [d.doc_id for d in docs] == ["a"]
    assert docs[0].fields["value"] == 100


def test_empty_result_returns_no_documents():
    http = FakeHttp([FakeResponse(200, [{"readTime": "2026-10-23T14:05:00Z"}])])
    assert reader(http).query_collection(UID, "meals", "T", order_field="eatenAt") == []


def test_date_range_is_sent_as_string_filters():
    http = FakeHttp([FakeResponse(200, [{"readTime": "x"}])])
    reader(http).query_collection(
        UID,
        "glucose_measurements",
        "T",
        order_field="measuredAt",
        start="2026-08-01T00:00:00",
        end="2026-09-01T00:00:00",
    )
    where = http.calls[0]["json"]["structuredQuery"]["where"]["compositeFilter"]
    assert where["op"] == "AND"
    ops = {f["fieldFilter"]["op"]: f["fieldFilter"]["value"] for f in where["filters"]}
    assert ops == {
        "GREATER_THAN_OR_EQUAL": {"stringValue": "2026-08-01T00:00:00"},
        # `end` se ensancha un día: un registro guardado con "Z" tiene un texto 3-4 h
        # mayor que su hora de pared y sería excluido por error del servidor.
        "LESS_THAN": {"stringValue": "2026-09-02T00:00:00"},
    }


def test_pagination_continues_after_last_document_until_short_page():
    page1 = [raw_doc("a", "2026-08-01T10:00:00.000"), raw_doc("b", "2026-08-02T10:00:00.000")]
    page2 = [raw_doc("c", "2026-08-03T10:00:00.000")]
    http = FakeHttp([FakeResponse(200, page1), FakeResponse(200, page2)])

    docs = reader(http).query_collection(
        UID, "glucose_measurements", "T", order_field="measuredAt", page_size=2
    )

    assert [d.doc_id for d in docs] == ["a", "b", "c"]
    assert len(http.calls) == 2
    cursor = http.calls[1]["json"]["structuredQuery"]["startAt"]
    assert cursor["before"] is False
    assert cursor["values"][0] == {"stringValue": "2026-08-02T10:00:00.000"}
    assert cursor["values"][1] == {"referenceValue": PREFIX + "b"}


def test_count_uses_aggregation_query_and_returns_integer():
    http = FakeHttp(
        [FakeResponse(200, [{"result": {"aggregateFields": {"count": {"integerValue": "321"}}}}])]
    )
    assert reader(http).count_collection(UID, "meals", "T") == 321
    assert http.calls[0]["url"].endswith(f"users/{UID}:runAggregationQuery")


def test_only_read_endpoints_are_ever_called():
    http = FakeHttp(
        [
            FakeResponse(200, [{"readTime": "x"}]),
            FakeResponse(200, [{"result": {"aggregateFields": {"count": {"integerValue": "0"}}}}]),
        ]
    )
    r = reader(http)
    r.query_collection(UID, "meals", "T", order_field="eatenAt")
    r.count_collection(UID, "meals", "T")
    assert all(c["url"].endswith((":runQuery", ":runAggregationQuery")) for c in http.calls)
    public = {name for name in dir(r) if not name.startswith("_")}
    assert public == {"query_collection", "count_collection"}


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, SessionExpiredError),
        (403, PermissionDeniedError),
        (429, ConnectionProblem),
        (503, ConnectionProblem),
    ],
)
def test_http_errors_map_to_domain_errors(status, error):
    http = FakeHttp([FakeResponse(status, {"error": {"message": "x"}})])
    with pytest.raises(error):
        reader(http).query_collection(UID, "meals", "T", order_field="eatenAt")


def test_network_failure_maps_to_connection_problem():
    http = FakeHttp([requests.Timeout("lento")])
    with pytest.raises(ConnectionProblem):
        reader(http).count_collection(UID, "meals", "T")


@pytest.mark.parametrize("bad_uid", ["", "../otro", "a/b", "uid con espacio", "x" * 200])
def test_uid_is_validated_to_prevent_path_injection(bad_uid):
    with pytest.raises(ValueError, match="uid"):
        reader(FakeHttp()).count_collection(bad_uid, "meals", "T")


def test_collection_must_be_one_of_the_four_known_collections():
    with pytest.raises(ValueError, match="colección"):
        reader(FakeHttp()).count_collection(UID, "backups", "T")


def test_end_filter_is_widened_so_utc_text_at_the_border_is_not_dropped_by_the_server():
    # 2026-09-30T22:00 en Santiago se guarda como 2026-10-01T01:00:00Z (texto mayor).
    http = FakeHttp([FakeResponse(200, [{"readTime": "x"}])])
    reader(http).query_collection(
        UID, "meals", "T", order_field="eatenAt", end="2026-10-01T00:00:00"
    )
    filters = http.calls[0]["json"]["structuredQuery"]["where"]["compositeFilter"]["filters"]
    sent_end = filters[0]["fieldFilter"]["value"]["stringValue"]
    assert sent_end > "2026-10-01T01:00:00Z"


def test_invalid_end_filter_is_rejected():
    with pytest.raises(ValueError, match="end"):
        reader(FakeHttp()).query_collection(
            UID, "meals", "T", order_field="eatenAt", end="no-es-fecha"
        )


@pytest.mark.parametrize("page_size", [0, -1])
def test_page_size_must_be_positive(page_size):
    with pytest.raises(ValueError, match="page_size"):
        reader(FakeHttp()).query_collection(
            UID, "meals", "T", order_field="eatenAt", page_size=page_size
        )


def test_non_string_order_value_stops_with_explicit_error_instead_of_a_wrong_cursor():
    doc = raw_doc("a", "x")
    doc["document"]["fields"]["measuredAt"] = {"integerValue": "5"}
    http = FakeHttp([FakeResponse(200, [doc])])
    with pytest.raises(GlucosaError, match="orden"):
        reader(http).query_collection(
            UID, "glucose_measurements", "T", order_field="measuredAt", page_size=1
        )


def test_repeated_page_stops_instead_of_looping_forever():
    same_page = [raw_doc("a", "2026-08-01T10:00:00.000")]
    http = FakeHttp([FakeResponse(200, same_page), FakeResponse(200, same_page)])
    with pytest.raises(GlucosaError, match="avanz"):
        reader(http).query_collection(
            UID, "glucose_measurements", "T", order_field="measuredAt", page_size=1
        )


class HtmlResponse:
    status_code = 200

    def json(self):
        raise ValueError("no es JSON")


def test_200_with_non_json_body_is_a_connection_problem():
    with pytest.raises(ConnectionProblem):
        reader(FakeHttp([HtmlResponse()])).count_collection(UID, "meals", "T")


def test_unexpected_payload_shape_is_a_domain_error():
    with pytest.raises(GlucosaError):
        reader(FakeHttp([FakeResponse(200, {"no": "es lista"})])).query_collection(
            UID, "meals", "T", order_field="eatenAt"
        )
