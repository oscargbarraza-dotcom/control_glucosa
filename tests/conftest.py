"""Utilidades compartidas por los tests. No contienen datos reales de salud."""

from __future__ import annotations

from typing import Any

from glucosa.data.firestore_decode import FirestoreDocument


def make_doc(doc_id: str, create_time: str | None = None, **fields: Any) -> FirestoreDocument:
    """Construye un documento ya decodificado, como lo entrega la capa REST."""
    return FirestoreDocument(
        doc_id=doc_id,
        fields=dict(fields),
        create_time=create_time,
        update_time=create_time,
    )


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_from_real_user_configuration(monkeypatch, tmp_path_factory):
    """Los tests nunca deben leer el .env, el JSON OAuth ni los datos reales del usuario."""
    monkeypatch.setenv("GLUCOSA_DATA_DIR", str(tmp_path_factory.mktemp("datos-aislados")))
    for name in (
        "GLUCOSA_FIREBASE_PROJECT_ID",
        "GLUCOSA_FIREBASE_API_KEY",
        "GLUCOSA_OAUTH_CLIENT_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
