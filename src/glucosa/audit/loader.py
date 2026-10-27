"""Carga de solo lectura de las cuatro colecciones del usuario autenticado."""

from collections.abc import Mapping

from glucosa.audit.structure import DATE_FIELDS
from glucosa.auth.session import AuthSession
from glucosa.data.firestore_client import FirestoreReader
from glucosa.data.firestore_decode import FirestoreDocument


def fetch_all(
    reader: FirestoreReader, session: AuthSession
) -> Mapping[str, list[FirestoreDocument]]:
    """Descarga todos los documentos de cada colección (lecturas; no escribe nada).

    Los datos quedan solo en memoria: no se escriben a disco ni a OneDrive.
    """
    return {
        collection: reader.query_collection(
            session.uid, collection, session.id_token, order_field=date_field
        )
        for collection, date_field in DATE_FIELDS.items()
    }
