"""Decodificación de valores y documentos de la API REST de Firestore."""

import pytest

from glucosa.data.firestore_decode import decode_document, decode_value


def test_decodes_scalar_types():
    assert decode_value({"stringValue": "hola"}) == "hola"
    assert decode_value({"integerValue": "176"}) == 176
    assert decode_value({"doubleValue": 72.5}) == 72.5
    assert decode_value({"booleanValue": True}) is True
    assert decode_value({"nullValue": None}) is None


def test_integer_value_arrives_as_string_and_becomes_int():
    value = decode_value({"integerValue": "120"})
    assert isinstance(value, int)


def test_decodes_nested_map_and_array():
    value = decode_value(
        {
            "mapValue": {
                "fields": {
                    "items": {
                        "arrayValue": {
                            "values": [
                                {"mapValue": {"fields": {"foodName": {"stringValue": "Pan"}}}}
                            ]
                        }
                    }
                }
            }
        }
    )
    assert value == {"items": [{"foodName": "Pan"}]}


def test_empty_array_and_empty_map_decode_to_empty_containers():
    assert decode_value({"arrayValue": {}}) == []
    assert decode_value({"mapValue": {}}) == {}


def test_unknown_value_type_raises_instead_of_guessing():
    with pytest.raises(ValueError, match="geoPointValue"):
        decode_value({"geoPointValue": {"latitude": 0, "longitude": 0}})


def test_document_exposes_id_fields_and_server_timestamps():
    doc = decode_document(
        {
            "name": (
                "projects/p/databases/(default)/documents/users/u1/glucose_measurements/abc-123"
            ),
            "fields": {"value": {"integerValue": "176"}},
            "createTime": "2026-10-23T14:00:00.123456Z",
            "updateTime": "2026-10-23T14:00:01.000000Z",
        }
    )
    assert doc.doc_id == "abc-123"
    assert doc.fields == {"value": 176}
    assert doc.create_time == "2026-10-23T14:00:00.123456Z"
    assert doc.update_time == "2026-10-23T14:00:01.000000Z"


def test_document_without_fields_decodes_to_empty_dict():
    doc = decode_document({"name": "projects/p/databases/(default)/documents/users/u/meals/x"})
    assert doc.fields == {}
