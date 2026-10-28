"""Validación y transformación de documentos de glucosa."""

from glucosa.data.parsing import parse_glucose
from glucosa.models.records import GlucoseMoment, Origin
from tests.conftest import make_doc


def valid_fields(**overrides):
    base = {
        "uuid": "u-1",
        "value": 176,
        "moment": "beforeDinner",
        "measuredAt": "2026-08-07T21:59:54.000",
        "comment": "prueba",
    }
    base.update(overrides)
    return base


def test_valid_document_maps_to_record():
    result = parse_glucose([make_doc("u-1", **valid_fields())])

    assert result.total_documents == 1
    assert result.issues == ()
    (record,) = result.records
    assert record.uuid == "u-1"
    assert record.value_mg_dl == 176
    assert record.moment is GlucoseMoment.BEFORE_DINNER
    assert record.comment == "prueba"
    assert record.measured_at.hour == 21  # hora de pared original conservada
    assert record.origin is Origin.MANUAL


def test_imported_record_is_detected_from_comment_marker():
    doc = make_doc("u-2", **valid_fields(uuid="u-2", comment="Importado desde FreeStyle Libre."))
    (record,) = parse_glucose([doc]).records
    assert record.origin is Origin.IMPORTED
    assert record.import_source == "FreeStyle Libre"


def test_taken_from_marker_is_also_imported():
    doc = make_doc("u-3", **valid_fields(uuid="u-3", comment="Tomado desde Health Connect."))
    (record,) = parse_glucose([doc]).records
    assert record.origin is Origin.IMPORTED


def test_missing_or_non_integer_value_is_rejected_not_zeroed():
    docs = [
        make_doc("a", **{k: v for k, v in valid_fields(uuid="a").items() if k != "value"}),
        make_doc("b", **valid_fields(uuid="b", value="176")),
    ]
    result = parse_glucose(docs)
    assert result.records == ()
    assert [i.severity for i in result.issues] == ["error", "error"]
    assert {i.doc_id for i in result.issues} == {"a", "b"}


def test_invalid_timestamp_is_rejected():
    result = parse_glucose([make_doc("x", **valid_fields(uuid="x", measuredAt="ayer"))])
    assert result.records == ()
    assert result.issues[0].severity == "error"


def test_value_outside_app_range_is_kept_with_warning():
    result = parse_glucose([make_doc("lo", **valid_fields(uuid="lo", value=15))])
    assert len(result.records) == 1
    assert result.issues[0].severity == "warning"


def test_unknown_moment_is_none_with_warning_not_a_default():
    result = parse_glucose([make_doc("m", **valid_fields(uuid="m", moment="otroMomento"))])
    (record,) = result.records
    assert record.moment is None
    assert result.issues[0].severity == "warning"


def test_uuid_falls_back_to_document_id_and_mismatch_warns():
    no_uuid = make_doc("doc-1", **{k: v for k, v in valid_fields().items() if k != "uuid"})
    mismatch = make_doc("doc-2", **valid_fields(uuid="otro"))
    result = parse_glucose([no_uuid, mismatch])
    assert {r.uuid for r in result.records} == {"doc-1", "doc-2"}
    assert any(i.doc_id == "doc-2" and i.severity == "warning" for i in result.issues)


def test_duplicate_uuid_is_counted_once():
    docs = [
        make_doc("dup", **valid_fields(uuid="dup")),
        make_doc("dup", **valid_fields(uuid="dup")),
    ]
    result = parse_glucose(docs)
    assert len(result.records) == 1
    assert result.duplicate_uuids == 1
    assert result.total_documents == 2


def test_same_time_and_value_with_different_uuid_is_flagged_but_kept():
    docs = [make_doc("p", **valid_fields(uuid="p")), make_doc("q", **valid_fields(uuid="q"))]
    result = parse_glucose(docs)
    assert len(result.records) == 2
    assert any("posible duplicado" in i.message.lower() for i in result.issues)


def test_records_are_sorted_ascending_by_measurement_time():
    docs = [
        make_doc("late", **valid_fields(uuid="late", measuredAt="2026-08-08T08:00:00.000")),
        make_doc("early", **valid_fields(uuid="early", measuredAt="2026-08-07T08:00:00.000")),
    ]
    result = parse_glucose(docs)
    assert [r.uuid for r in result.records] == ["early", "late"]


def test_same_wall_clock_but_different_instants_are_not_duplicates():
    # 23:30 aparece dos veces el 2026-04-04 en Chile (UTC-3 y luego UTC-4).
    docs = [
        make_doc("a", **valid_fields(uuid="a", measuredAt="2026-04-05T02:30:00.000Z")),
        make_doc("b", **valid_fields(uuid="b", measuredAt="2026-04-05T03:30:00.000Z")),
    ]
    result = parse_glucose(docs)
    assert [r.uuid for r in result.records] == ["a", "b"]
    assert not any("duplicado" in i.message.lower() for i in result.issues)


def test_repeated_hour_is_ordered_by_real_instant():
    docs = [
        make_doc("later", **valid_fields(uuid="later", measuredAt="2026-04-05T03:10:00.000Z")),
        make_doc("first", **valid_fields(uuid="first", measuredAt="2026-04-05T02:30:00.000Z")),
    ]
    assert [r.uuid for r in parse_glucose(docs).records] == ["first", "later"]


def test_ambiguous_or_nonexistent_local_time_is_kept_with_warning():
    docs = [
        make_doc("amb", **valid_fields(uuid="amb", measuredAt="2026-04-04T23:30:00.000")),
        make_doc("gap", **valid_fields(uuid="gap", measuredAt="2026-09-06T00:30:00.000")),
    ]
    result = parse_glucose(docs)
    assert len(result.records) == 2
    messages = {i.doc_id: i.message.lower() for i in result.issues}
    assert "ambigua" in messages["amb"]
    assert "no existió" in messages["gap"]


def test_overflowing_timestamp_is_rejected_not_a_crash():
    result = parse_glucose(
        [make_doc("o", **valid_fields(uuid="o", measuredAt="0001-01-01T00:00:00Z"))]
    )
    assert result.records == ()
    assert result.issues[0].severity == "error"


def test_cloud_creation_time_is_exposed_separately_from_measurement_time():
    doc = make_doc("c", create_time="2026-08-09T10:00:00.123456789Z", **valid_fields(uuid="c"))
    (record,) = parse_glucose([doc]).records
    assert record.cloud_created_at is not None
    assert record.cloud_created_at > record.measured_at
