"""Cliente de **solo lectura** de Firestore por REST, con el token del propio usuario.

Se usa la API REST con ``Authorization: Bearer <ID token de Firebase>`` para que
apliquen las reglas de seguridad existentes (cada usuario solo lee
``users/{su-uid}/...``). No se usa Admin SDK ni credenciales de servicio.

La clase solo expone dos operaciones públicas, ambas lecturas
(``runQuery`` y ``runAggregationQuery``); el contrato HTTP inyectado solo tiene
``post``. Las fechas se filtran como texto ISO 8601: el filtro del servidor es
una aproximación y el llamador debe volver a filtrar con las fechas ya
interpretadas (ver ``timeutil``).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import requests

from glucosa.data.firestore_decode import FirestoreDocument, decode_document
from glucosa.errors import (
    ConnectionProblem,
    GlucosaError,
    PermissionDeniedError,
    SessionExpiredError,
)
from glucosa.http import DEFAULT_TIMEOUT_SECONDS, HttpClient, HttpResponse
from glucosa.identifiers import is_valid_uid

BASE_URL = "https://firestore.googleapis.com/v1"
COLLECTIONS = frozenset(
    {"glucose_measurements", "meals", "medication_intakes", "biometric_measurements"}
)
DEFAULT_PAGE_SIZE = 300
_PROJECT_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_READ_ACTIONS = (":runQuery", ":runAggregationQuery")
# Los textos con "Z" (UTC) son 3-4 h mayores que la hora de pared de Chile: el límite
# superior del servidor se ensancha para no perder registros del borde. El llamador
# vuelve a filtrar con las fechas ya interpretadas.
_END_WIDENING = timedelta(days=1)


def _check_uid(uid: str) -> None:
    if not is_valid_uid(uid):
        raise ValueError("uid inválido: solo se permiten letras y números.")


def _check_collection(collection: str) -> None:
    if collection not in COLLECTIONS:
        raise ValueError(f"colección no permitida: {collection!r}")


def _raise_for_status(response: HttpResponse) -> None:
    status = response.status_code
    if status == 200:
        return
    if status == 401:
        raise SessionExpiredError("Tu sesión venció. Inicia sesión nuevamente.")
    if status == 403:
        raise PermissionDeniedError("Firestore rechazó la lectura (reglas de seguridad).")
    if status == 429 or status >= 500:
        raise ConnectionProblem("Firestore no está disponible o hay demasiadas solicitudes.")
    raise GlucosaError(f"Respuesta inesperada de Firestore (HTTP {status}).")


def _range_filter(field_path: str, op: str, value: str) -> dict[str, Any]:
    return {
        "fieldFilter": {
            "field": {"fieldPath": field_path},
            "op": op,
            "value": {"stringValue": value},
        }
    }


def _widen_end(end: str) -> str:
    try:
        return (datetime.fromisoformat(end) + _END_WIDENING).isoformat()
    except ValueError:
        raise ValueError(f"end inválido: {end!r}") from None


def _documents_from(payload: Any) -> list[FirestoreDocument]:
    if not isinstance(payload, list):
        raise GlucosaError("Firestore devolvió una respuesta con formato inesperado.")
    return [decode_document(item["document"]) for item in payload if "document" in item]


class FirestoreReader:
    def __init__(
        self, project_id: str, http: HttpClient, timeout: int = DEFAULT_TIMEOUT_SECONDS
    ) -> None:
        if not _PROJECT_PATTERN.fullmatch(project_id):
            raise ValueError("project_id inválido.")
        self._project_id = project_id
        self._http = http
        self._timeout = timeout

    # ------------------------------------------------------------- interno
    def _parent_url(self, uid: str, action: str) -> str:
        return (
            f"{BASE_URL}/projects/{self._project_id}/databases/(default)"
            f"/documents/users/{uid}:{action}"
        )

    def _post(self, url: str, id_token: str, body: dict[str, Any]) -> Any:
        if not url.endswith(_READ_ACTIONS):
            raise ValueError("Solo se permiten endpoints de lectura de Firestore.")
        try:
            response = self._http.post(
                url,
                headers={"Authorization": f"Bearer {id_token}"},
                json=body,
                timeout=self._timeout,
            )
        except requests.RequestException:
            # Sin encadenar: el mensaje de la excepción original puede incluir la URL.
            raise ConnectionProblem("Sin conexión con Firestore. Revisa tu red.") from None
        _raise_for_status(response)
        try:
            return response.json()
        except ValueError:
            raise ConnectionProblem("Firestore devolvió una respuesta no válida.") from None

    @staticmethod
    def _where(order_field: str, start: str | None, end: str | None) -> dict[str, Any] | None:
        filters = []
        if start is not None:
            filters.append(_range_filter(order_field, "GREATER_THAN_OR_EQUAL", start))
        if end is not None:
            filters.append(_range_filter(order_field, "LESS_THAN", _widen_end(end)))
        if not filters:
            return None
        return {"compositeFilter": {"op": "AND", "filters": filters}}

    # ------------------------------------------------------------- público
    def query_collection(
        self,
        uid: str,
        collection: str,
        id_token: str,
        *,
        order_field: str,
        start: str | None = None,
        end: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[FirestoreDocument]:
        """Lee los documentos de una subcolección del usuario, paginando."""
        _check_uid(uid)
        _check_collection(collection)
        if page_size < 1:
            raise ValueError("page_size debe ser al menos 1.")
        url = self._parent_url(uid, "runQuery")
        where = self._where(order_field, start, end)
        documents: list[FirestoreDocument] = []
        cursor: dict[str, Any] | None = None
        while True:
            query: dict[str, Any] = {
                "from": [{"collectionId": collection}],
                "orderBy": [
                    {"field": {"fieldPath": order_field}, "direction": "ASCENDING"},
                    {"field": {"fieldPath": "__name__"}, "direction": "ASCENDING"},
                ],
                "limit": page_size,
            }
            if where is not None:
                query["where"] = where
            if cursor is not None:
                query["startAt"] = cursor
            payload = self._post(url, id_token, {"structuredQuery": query})
            page = _documents_from(payload)
            documents.extend(page)
            if len(page) < page_size:
                return documents
            cursor = self._next_cursor(page[-1], order_field, cursor)

    @staticmethod
    def _next_cursor(
        last: FirestoreDocument, order_field: str, previous: dict[str, Any] | None
    ) -> dict[str, Any]:
        value = last.fields.get(order_field)
        if not isinstance(value, str):
            raise GlucosaError(
                f"El campo de orden '{order_field}' no es texto en el documento {last.doc_id}."
            )
        cursor = {
            "values": [{"stringValue": value}, {"referenceValue": last.path}],
            "before": False,
        }
        if cursor == previous:
            raise GlucosaError("La paginación no avanzó; se detuvo para evitar un bucle.")
        return cursor

    def count_collection(self, uid: str, collection: str, id_token: str) -> int:
        """Cuenta los documentos de una subcolección (consulta de agregación)."""
        _check_uid(uid)
        _check_collection(collection)
        body = {
            "structuredAggregationQuery": {
                "structuredQuery": {"from": [{"collectionId": collection}]},
                "aggregations": [{"count": {}, "alias": "count"}],
            }
        }
        payload = self._post(self._parent_url(uid, "runAggregationQuery"), id_token, body)
        if isinstance(payload, list):
            for item in payload:
                result = item.get("result")
                if result:
                    try:
                        return int(result["aggregateFields"]["count"]["integerValue"])
                    except (KeyError, TypeError, ValueError):
                        break
        raise GlucosaError("Firestore no devolvió el conteo solicitado.")
