"""Auditoría: estructura de campos y análisis de fechas (datos sintéticos)."""

from datetime import UTC, datetime

from glucosa.audit.dates import audit_dates, classify_format
from glucosa.audit.structure import audit_structure, type_name
from tests.conftest import make_doc

UUID_A = "3f2b8c1e-9d4a-4b7e-8a6c-1d2e3f4a5b6c"
UUID_B = "7a1c9e22-0b3d-4c5f-9e8a-2b3c4d5e6f70"


def glucose(doc_id=UUID_A, **overrides):
    fields = {
        "uuid": doc_id,
        "value": 120,
        "moment": "now",
        "measuredAt": "2026-08-07T10:00:00.000",
        "comment": None,
    }
    fields.update(overrides)
    return make_doc(doc_id, create_time="2026-08-07T14:00:05.123456Z", **fields)


# ------------------------------------------------------------------ estructura
def test_type_names_distinguish_bool_int_float_and_null():
    assert [type_name(v) for v in (True, 3, 3.5, "x", None, [], {})] == [
        "bool",
        "int",
        "float",
        "str",
        "null",
        "list",
        "dict",
    ]


def test_structure_reports_presence_nulls_types_and_unexpected_fields():
    docs = [
        glucose(UUID_A),
        glucose(UUID_B, value=130.5, extra="x"),
        make_doc("sin-uuid-valido", value=1, moment="now", measuredAt="2026-08-07T10:00:00.000"),
    ]

    report = audit_structure("glucose_measurements", docs)

    assert report.total == 3
    by_name = {f.name: f for f in report.fields}
    assert by_name["value"].types == {"int": 2, "float": 1}
    assert by_name["comment"].present == 2 and by_name["comment"].null == 2
    assert report.unexpected_fields == ("extra",)
    assert report.missing_expected["comment"] == 1
    assert report.missing_expected["uuid"] == 1
    assert report.invalid_uuid_format == 1  # el ID del documento no es un UUID
    assert report.uuid_mismatch == 0


def test_structure_detects_uuid_field_different_from_document_id():
    doc = make_doc(UUID_A, create_time=None, uuid=UUID_B, value=1, measuredAt="x")
    assert audit_structure("glucose_measurements", [doc]).uuid_mismatch == 1


def test_nested_item_fields_are_profiled_for_meals():
    meal = make_doc(
        UUID_A,
        uuid=UUID_A,
        type="lunch",
        eatenAt="2026-08-07T13:00:00.000",
        comment=None,
        items=[{"foodName": "A", "quantity": "1"}, {"foodName": "B"}],
    )
    report = audit_structure("meals", [meal])
    nested = {f.name: f for f in report.item_fields}
    assert nested["foodName"].present == 2
    assert nested["quantity"].present == 1
    assert report.unexpected_item_fields == ()


# ---------------------------------------------------------------------- fechas
def test_format_classes():
    assert classify_format("2026-08-07T10:00:00.000") == "local_sin_zona"
    assert classify_format("2026-08-07T10:00:00.123456") == "local_sin_zona"
    assert classify_format("2026-08-07T10:00:00.000Z") == "utc_Z"
    assert classify_format("2026-08-07T10:00:00-04:00") == "con_offset"
    assert classify_format("07/08/2026") == "otro"
    assert classify_format(None) == "ausente"


def test_date_audit_counts_formats_issues_range_and_future_dates():
    now = datetime(2026, 10, 23, tzinfo=UTC)
    docs = [
        glucose(UUID_A, measuredAt="2026-08-07T10:00:00.000"),
        glucose(UUID_B, measuredAt="2026-08-09T10:00:00.000Z"),
        glucose("c", measuredAt="2026-04-04T23:30:00.000"),  # ambigua
        glucose("d", measuredAt="2026-09-06T00:30:00.000"),  # inexistente
        glucose("e", measuredAt="2027-01-01T00:00:00.000"),  # futura
        glucose("f", measuredAt="basura"),
    ]

    report = audit_dates("glucose_measurements", "measuredAt", docs, now)

    assert report.formats == {"local_sin_zona": 4, "utc_Z": 1, "otro": 1}
    assert report.unparseable == 1
    assert (report.ambiguous, report.nonexistent, report.future) == (1, 1, 1)
    assert report.earliest.date().isoformat() == "2026-04-04"
    assert report.latest.date().isoformat() == "2027-01-01"


def test_lag_between_event_and_cloud_creation_is_summarised_in_minutes():
    now = datetime(2026, 10, 23, tzinfo=UTC)
    # Evento 10:00 hora de Santiago (UTC-4 en agosto) = 14:00Z; creado en la nube 14:00:05Z.
    docs = [glucose(UUID_A), glucose(UUID_B, measuredAt="2026-08-07T09:30:00.000")]

    lag = audit_dates("glucose_measurements", "measuredAt", docs, now).lag

    assert lag.count == 2
    assert lag.negative == 0
    assert round(lag.min_minutes, 1) == 0.1  # 5 s
    assert round(lag.max_minutes, 1) == 30.1  # evento 13:30Z, subido 14:00:05Z


def test_negative_lag_flags_events_dated_after_their_upload():
    now = datetime(2026, 10, 23, tzinfo=UTC)
    future_event = glucose(UUID_A, measuredAt="2026-08-07T12:00:00.000")  # 16:00Z > 14:00Z
    lag = audit_dates("glucose_measurements", "measuredAt", [future_event], now).lag
    assert lag.negative == 1
