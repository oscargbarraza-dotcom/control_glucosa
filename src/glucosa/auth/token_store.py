"""Almacenamiento del refresh token en el Administrador de credenciales de Windows.

Se guarda únicamente el refresh token de Firebase (no la contraseña ni el
token de Google) vía ``keyring``. Nunca se escribe en archivos de texto.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from keyring.errors import PasswordDeleteError

from glucosa.identifiers import is_valid_uid

SERVICE_NAME = "glucosa"
ENTRY_NAME = "session"


class KeyringBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


@dataclass(frozen=True)
class StoredLogin:
    uid: str
    refresh_token: str = field(repr=False)


class KeyringTokenStore:
    def __init__(self, backend: KeyringBackend | None = None) -> None:
        if backend is None:
            import keyring

            backend = keyring  # type: ignore[assignment]
        self._backend: Any = backend

    def save(self, login: StoredLogin) -> None:
        payload = json.dumps({"uid": login.uid, "refresh_token": login.refresh_token})
        self._backend.set_password(SERVICE_NAME, ENTRY_NAME, payload)

    def load(self) -> StoredLogin | None:
        raw = self._backend.get_password(SERVICE_NAME, ENTRY_NAME)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            uid, token = data["uid"], data["refresh_token"]
            if not is_valid_uid(uid):
                return None
            if not (isinstance(token, str) and token):
                return None
            return StoredLogin(uid=uid, refresh_token=token)
        except (ValueError, KeyError, TypeError):
            return None  # entrada corrupta: se trata como "sin sesión guardada"

    def clear(self) -> None:
        try:
            self._backend.delete_password(SERVICE_NAME, ENTRY_NAME)
        except PasswordDeleteError:
            return  # no había sesión guardada; cualquier otro fallo se propaga
