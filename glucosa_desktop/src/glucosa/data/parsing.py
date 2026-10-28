"""Validación y transformación de documentos de Firestore a modelos tipados.

Reglas (decisiones del proyecto, ver ``PROJECT_CONTEXT.md``):

* Un documento con un dato obligatorio ausente o inválido se **rechaza** y se
  reporta como ``error``. Nunca se reemplaza por 0 ni por un valor inventado.
* Un dato sospechoso (fuera del rango que valida la app, enum desconocido,
  posible duplicado) se **conserva** y se reporta como ``warning``.
* La identidad de un registro es el ID del documento, que Android fija igual
  al UUID del registro. Un mismo UUID se cuenta una sola vez.
* Las fechas originales se conservan (ver ``timeutil``).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from glucosa.data.firestore_decode import FirestoreDocument
from glucosa.data.timeutil import parse_timestamp, wall_clock_issue
from glucosa.limits import GLUCOSE_RANGE
from glucosa.models.foods import normalize_food_name
from glucosa.models.records import (
    BiometricRecord,
    DoseUnit,
    GlucoseMoment,
    GlucoseRecord,
    IntakeItem,
    IntakeRecord,
    MealItem,
    MealRecord,
    MealType,
    Origin,
)

Severity = Literal["error", "warning"]

# Rangos que valida la propia app Android al registrar (fuera de ellos solo
# pueden venir datos importados o corruptos): se reportan, no se descartan.
WEIGHT_RANGE = (20.0, 400.0)
SYSTOLIC_RANGE = (60, 250)
DIASTOLIC_RANGE = (30, 150)
HEART_RATE_RANGE = (30, 220)

_IMPORT_MARKER = re.compile(r"(?:Importado|Tomado) desde (.+?)\.?")


@dataclass(frozen=True)
class ParseIssue:
    collection: str
    doc_id: str
    severity: Severity
    message: str


@dataclass(frozen=True)
class ParseResult[T]:
    records: tuple[T, ...]
    issues: tuple[ParseIssue, ...]
    total_documents: int
    duplicate_uuids: int


class _Log:
    """Acumulador interno de avisos; el resultado público es inmutable."""

    def __init__(self, collection: str) -> None:
        self.collection = collection
        self.items: list[ParseIssue] = []

    def error(self, doc_id: str, message: str) -> None:
        self.items.append(ParseIssue(self.collection, doc_id, "error", message))

    def warn(self, doc_id: str, message: str) -> None:
        self.items.append(ParseIssue(self.collection, doc_id, "warning", message))


# ---------------------------------------------------------------- utilidades
def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    """Número real finito (excluye bool, NaN e infinitos)."""
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


_WALL_CLOCK_MESSAGES = {
    "ambiguous": "La hora local de '{field}' es ambigua (ocurrió dos veces por cambio de horario).",
    "nonexistent": "La hora local de '{field}' no existió en Chile (salto de horario de verano).",
}


def _timestamp(doc: FirestoreDocument, field: str, log: _Log) -> datetime | None:
    raw = doc.fields.get(field)
    try:
        parsed = parse_timestamp(raw)
        issue = wall_clock_issue(raw)
    except ValueError:
        log.error(doc.doc_id, f"Fecha inválida o ausente en '{field}'.")
        return None
    if issue is not None:
        log.warn(doc.doc_id, _WALL_CLOCK_MESSAGES[issue].format(field=field))
    return parsed


def _raw_items(doc: FirestoreDocument, log: _Log) -> list[Any]:
    """Lista de ``items`` del documento; un tipo inesperado da un único aviso."""
    items = doc.fields.get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        log.warn(doc.doc_id, "El campo 'items' no es una lista: se ignoró.")
        return []
    return items


def _cloud_created(doc: FirestoreDocument) -> datetime | None:
    if not doc.create_time:
        return None
    try:
        return parse_timestamp(doc.create_time)
    except ValueError:
        return None


def _enum_or_none[E: StrEnum](
    enum_cls: type[E], raw: Any, doc: FirestoreDocument, field: str, log: _Log
) -> E | None:
    try:
        return enum_cls(raw)
    except ValueError:
        log.warn(doc.doc_id, f"Valor desconocido en '{field}': {raw!r}.")
        return None


def _check_uuid(doc: FirestoreDocument, log: _Log) -> None:
    declared = doc.fields.get("uuid")
    if declared is not None and declared != doc.doc_id:
        log.warn(doc.doc_id, f"El campo 'uuid' ({declared!r}) difiere del ID del documento.")


def _check_range(
    value: float, bounds: tuple[float, float], label: str, doc_id: str, log: _Log
) -> None:
    low, high = bounds
    if not low <= value <= high:
        log.warn(doc_id, f"{label} fuera del rango que valida la app ({low}–{high}): {value}.")


@dataclass
class _Collected[T]:
    records: list[T]
    log: _Log
    total: int
    duplicates: int


def _collect[T](
    collection: str,
    docs: Iterable[FirestoreDocument],
    build: Callable[[FirestoreDocument, _Log], T | None],
    sort_key: Callable[[T], tuple[Any, ...]],
) -> _Collected[T]:
    log = _Log(collection)
    seen: set[str] = set()
    records: list[T] = []
    total = duplicates = 0
    for doc in docs:
        total += 1
        if doc.doc_id in seen:
            duplicates += 1
            continue
        seen.add(doc.doc_id)
        _check_uuid(doc, log)
        record = build(doc, log)
        if record is not None:
            records.append(record)
    records.sort(key=sort_key)
    return _Collected(records, log, total, duplicates)


def _result[T](collected: _Collected[T]) -> ParseResult[T]:
    return ParseResult(
        tuple(collected.records),
        tuple(collected.log.items),
        collected.total,
        collected.duplicates,
    )


# ------------------------------------------------------------------ glucosa
def _build_glucose(doc: FirestoreDocument, log: _Log) -> GlucoseRecord | None:
    fields = doc.fields
    value = fields.get("value")
    if not _is_int(value):
        log.error(doc.doc_id, "Valor de glucosa ausente o no entero.")
        return None
    measured_at = _timestamp(doc, "measuredAt", log)
    if measured_at is None:
        return None
    _check_range(value, GLUCOSE_RANGE, "Glucosa", doc.doc_id, log)
    comment = _text(fields.get("comment"))
    match = _IMPORT_MARKER.fullmatch(comment.strip()) if comment else None
    return GlucoseRecord(
        uuid=doc.doc_id,
        value_mg_dl=value,
        moment=_enum_or_none(GlucoseMoment, fields.get("moment"), doc, "moment", log),
        measured_at=measured_at,
        comment=comment,
        origin=Origin.IMPORTED if match else Origin.MANUAL,
        import_source=match.group(1) if match else None,
        cloud_created_at=_cloud_created(doc),
    )


def _flag_possible_duplicates(records: Sequence[GlucoseRecord], log: _Log) -> None:
    first_by_key: dict[tuple[datetime, int], str] = {}
    for record in records:
        key = (record.measured_at, record.value_mg_dl)
        original = first_by_key.setdefault(key, record.uuid)
        if original != record.uuid:
            log.warn(
                record.uuid,
                f"Posible duplicado: misma fecha/hora y valor que el registro {original}.",
            )


def parse_glucose(docs: Iterable[FirestoreDocument]) -> ParseResult[GlucoseRecord]:
    collected = _collect(
        "glucose_measurements",
        docs,
        _build_glucose,
        lambda r: (r.measured_at, r.uuid),
    )
    _flag_possible_duplicates(collected.records, collected.log)
    return _result(collected)


# ----------------------------------------------------------------- comidas
def _build_meal_items(doc: FirestoreDocument, log: _Log) -> tuple[MealItem, ...]:
    items: list[MealItem] = []
    for raw in _raw_items(doc, log):
        name = _text(raw.get("foodName")) if isinstance(raw, dict) else None
        if name is None:
            log.warn(doc.doc_id, "Alimento sin nombre: se omitió de la comida.")
            continue
        quantity = raw.get("quantity")
        if not isinstance(quantity, str):
            log.warn(doc.doc_id, f"Alimento '{name}' sin cantidad.")
            quantity = ""
        items.append(MealItem(food_name=name, quantity=quantity))
    return tuple(items)


def _build_meal(doc: FirestoreDocument, log: _Log) -> MealRecord | None:
    eaten_at = _timestamp(doc, "eatenAt", log)
    if eaten_at is None:
        return None
    items = _build_meal_items(doc, log)
    if not items and not doc.fields.get("items"):
        # Solo si el documento no trae alimentos; si traía alimentos inválidos ya se avisó.
        log.warn(doc.doc_id, "Comida sin alimentos.")
    return MealRecord(
        uuid=doc.doc_id,
        type=_enum_or_none(MealType, doc.fields.get("type"), doc, "type", log),
        eaten_at=eaten_at,
        comment=_text(doc.fields.get("comment")),
        items=items,
        cloud_created_at=_cloud_created(doc),
    )


def _validate_meals(records: Sequence[MealRecord], log: _Log) -> None:
    """Avisos sobre comidas (nunca descartan ni modifican registros; sin nombres en los textos)."""
    first_by_key: dict[tuple[datetime, MealType | None, tuple[str, ...]], str] = {}
    for record in records:
        names = [normalize_food_name(item.food_name) for item in record.items]
        if len(set(names)) < len(names):
            log.warn(record.uuid, "Alimento repetido dentro de la comida (se conservan ambos).")
        if not names:
            continue
        key = (record.eaten_at, record.type, tuple(sorted(set(names))))
        original = first_by_key.setdefault(key, record.uuid)
        if original != record.uuid:
            log.warn(
                record.uuid,
                f"Posible duplicado: misma fecha/hora, tipo y alimentos que la comida {original}.",
            )


def parse_meals(docs: Iterable[FirestoreDocument]) -> ParseResult[MealRecord]:
    collected = _collect("meals", docs, _build_meal, lambda r: (r.eaten_at, r.uuid))
    _validate_meals(collected.records, collected.log)
    return _result(collected)


# ------------------------------------------------------------ medicamentos
def _build_intake_item(raw: Any, doc: FirestoreDocument, log: _Log) -> IntakeItem | None:
    name = _text(raw.get("medicationName")) if isinstance(raw, dict) else None
    if name is None:
        log.warn(doc.doc_id, "Medicamento sin nombre: se omitió de la toma.")
        return None
    quantity = raw.get("quantity")
    if not _is_number(quantity) or quantity <= 0:
        log.warn(doc.doc_id, f"Medicamento '{name}' sin dosis válida: se omitió.")
        return None
    try:
        unit = DoseUnit(raw.get("unit"))
    except ValueError:
        log.warn(doc.doc_id, f"Medicamento '{name}' con unidad desconocida: se omitió.")
        return None
    return IntakeItem(
        medication_name=name,
        quantity=float(quantity),
        unit=unit,
        custom_unit_label=_text(raw.get("customUnitLabel")),
    )


def _build_intake(doc: FirestoreDocument, log: _Log) -> IntakeRecord | None:
    taken_at = _timestamp(doc, "takenAt", log)
    if taken_at is None:
        return None
    built = (_build_intake_item(raw, doc, log) for raw in _raw_items(doc, log))
    return IntakeRecord(
        uuid=doc.doc_id,
        taken_at=taken_at,
        comment=_text(doc.fields.get("comment")),
        items=tuple(item for item in built if item is not None),
        cloud_created_at=_cloud_created(doc),
    )


def parse_intakes(docs: Iterable[FirestoreDocument]) -> ParseResult[IntakeRecord]:
    return _result(
        _collect("medication_intakes", docs, _build_intake, lambda r: (r.taken_at, r.uuid))
    )


# ---------------------------------------------------------------- biometría
def _optional_int(
    doc: FirestoreDocument, field: str, bounds: tuple[int, int], label: str, log: _Log
) -> int | None:
    value = doc.fields.get(field)
    if value is None:
        return None
    if not _is_int(value):
        log.warn(doc.doc_id, f"{label} no es un entero: se ignoró.")
        return None
    _check_range(value, bounds, label, doc.doc_id, log)
    return value


def _build_biometric(doc: FirestoreDocument, log: _Log) -> BiometricRecord | None:
    weight = doc.fields.get("weightKg")
    if not _is_number(weight):
        log.error(doc.doc_id, "Peso ausente o no numérico.")
        return None
    measured_at = _timestamp(doc, "measuredAt", log)
    if measured_at is None:
        return None
    _check_range(float(weight), WEIGHT_RANGE, "Peso", doc.doc_id, log)
    systolic = _optional_int(doc, "systolicPressure", SYSTOLIC_RANGE, "Presión sistólica", log)
    diastolic = _optional_int(doc, "diastolicPressure", DIASTOLIC_RANGE, "Presión diastólica", log)
    if (systolic is None) != (diastolic is None):
        log.warn(doc.doc_id, "Presión arterial incompleta: falta sistólica o diastólica.")
    return BiometricRecord(
        uuid=doc.doc_id,
        weight_kg=float(weight),
        systolic=systolic,
        diastolic=diastolic,
        heart_rate_bpm=_optional_int(doc, "heartRateBpm", HEART_RATE_RANGE, "Frecuencia", log),
        measured_at=measured_at,
        comment=_text(doc.fields.get("comment")),
        cloud_created_at=_cloud_created(doc),
    )


def parse_biometrics(docs: Iterable[FirestoreDocument]) -> ParseResult[BiometricRecord]:
    return _result(
        _collect(
            "biometric_measurements", docs, _build_biometric, lambda r: (r.measured_at, r.uuid)
        )
    )
