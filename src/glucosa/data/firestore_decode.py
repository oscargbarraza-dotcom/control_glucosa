"""Decodificación de la representación tipada de la API REST de Firestore.

La API REST devuelve cada valor como ``{"stringValue": ...}``,
``{"integerValue": "176"}`` (los enteros llegan como texto), etc. Este módulo
lo convierte a tipos nativos de Python. Un tipo desconocido es un error
explícito: nunca se adivina ni se sustituye por un valor por defecto.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, eq=False)
class FirestoreDocument:
    """Documento ya decodificado, con los metadatos que entrega el servidor.

    ``fields`` es de solo lectura (copia envuelta en ``MappingProxyType``). La
    igualdad es por identidad: el documento no debe usarse como clave de datos.
    """

    doc_id: str
    fields: Mapping[str, Any] = field(default_factory=dict)
    create_time: str | None = None
    update_time: str | None = None
    path: str = ""  # nombre completo (projects/.../documents/...), usado como cursor

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


def decode_value(value: dict[str, Any]) -> Any:
    """Convierte un ``Value`` de Firestore REST a un valor de Python."""
    if "stringValue" in value:
        return value["stringValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "nullValue" in value:
        return None
    if "timestampValue" in value:
        return value["timestampValue"]
    if "mapValue" in value:
        raw_fields = value["mapValue"].get("fields", {})
        return {key: decode_value(inner) for key, inner in raw_fields.items()}
    if "arrayValue" in value:
        return [decode_value(inner) for inner in value["arrayValue"].get("values", [])]
    kinds = ", ".join(sorted(value)) or "(vacío)"
    raise ValueError(f"Tipo de valor de Firestore no soportado: {kinds}")


def decode_document(raw: dict[str, Any]) -> FirestoreDocument:
    """Convierte un ``Document`` de Firestore REST (``name``, ``fields``, ...)."""
    doc_id = str(raw["name"]).rsplit("/", 1)[-1]
    fields = {key: decode_value(inner) for key, inner in raw.get("fields", {}).items()}
    return FirestoreDocument(
        doc_id=doc_id,
        fields=fields,
        create_time=raw.get("createTime"),
        update_time=raw.get("updateTime"),
        path=str(raw["name"]),
    )
