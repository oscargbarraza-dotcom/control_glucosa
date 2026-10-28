"""Auditoría de estructura: campos presentes, nulos, tipos y campos inesperados."""

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from glucosa.data.firestore_decode import FirestoreDocument

EXPECTED_FIELDS: Mapping[str, tuple[str, ...]] = {
    "glucose_measurements": ("uuid", "value", "moment", "measuredAt", "comment"),
    "meals": ("uuid", "type", "eatenAt", "comment", "items"),
    "medication_intakes": ("uuid", "takenAt", "comment", "items"),
    "biometric_measurements": (
        "uuid",
        "weightKg",
        "systolicPressure",
        "diastolicPressure",
        "heartRateBpm",
        "measuredAt",
        "comment",
    ),
}
EXPECTED_ITEM_FIELDS: Mapping[str, tuple[str, ...]] = {
    "meals": ("foodName", "quantity"),
    "medication_intakes": (
        "medicationName",
        "defaultUnit",
        "quantity",
        "unit",
        "customUnitLabel",
    ),
}
DATE_FIELDS: Mapping[str, str] = {
    "glucose_measurements": "measuredAt",
    "meals": "eatenAt",
    "medication_intakes": "takenAt",
    "biometric_measurements": "measuredAt",
}

_UUID_V4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", re.IGNORECASE
)


@dataclass(frozen=True)
class FieldStat:
    name: str
    present: int  # el campo existe (aunque sea nulo)
    null: int
    types: Mapping[str, int]


@dataclass(frozen=True)
class StructureReport:
    collection: str
    total: int
    fields: tuple[FieldStat, ...]
    unexpected_fields: tuple[str, ...]
    missing_expected: Mapping[str, int]  # documentos donde el campo esperado NO existe
    uuid_mismatch: int
    invalid_uuid_format: int
    item_fields: tuple[FieldStat, ...] = ()
    unexpected_item_fields: tuple[str, ...] = ()


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _profile(rows: Iterable[Mapping[str, Any]]) -> tuple[FieldStat, ...]:
    present: Counter[str] = Counter()
    nulls: Counter[str] = Counter()
    types: dict[str, Counter[str]] = {}
    for row in rows:
        for name, value in row.items():
            present[name] += 1
            nulls[name] += value is None
            types.setdefault(name, Counter())[type_name(value)] += 1
    return tuple(
        FieldStat(name, present[name], nulls[name], dict(types[name])) for name in sorted(present)
    )


def _item_rows(docs: Iterable[FirestoreDocument]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for doc in docs:
        items = doc.fields.get("items")
        if isinstance(items, list):
            rows.extend(item for item in items if isinstance(item, dict))
    return rows


def audit_structure(collection: str, docs: Iterable[FirestoreDocument]) -> StructureReport:
    documents = list(docs)
    expected = EXPECTED_FIELDS[collection]
    fields = _profile(doc.fields for doc in documents)
    seen = {f.name for f in fields}
    missing = {name: sum(1 for doc in documents if name not in doc.fields) for name in expected}
    item_fields = _profile(_item_rows(documents)) if collection in EXPECTED_ITEM_FIELDS else ()
    expected_items = EXPECTED_ITEM_FIELDS.get(collection, ())
    return StructureReport(
        collection=collection,
        total=len(documents),
        fields=fields,
        unexpected_fields=tuple(sorted(seen - set(expected))),
        missing_expected={name: count for name, count in missing.items() if count},
        uuid_mismatch=sum(
            1
            for doc in documents
            if doc.fields.get("uuid") is not None and doc.fields["uuid"] != doc.doc_id
        ),
        invalid_uuid_format=sum(1 for doc in documents if not _UUID_V4.fullmatch(doc.doc_id)),
        item_fields=item_fields,
        unexpected_item_fields=tuple(sorted({f.name for f in item_fields} - set(expected_items))),
    )
