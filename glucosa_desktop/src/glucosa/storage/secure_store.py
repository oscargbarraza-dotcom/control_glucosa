"""Archivos JSON cifrados (Fernet) con la clave guardada en el Administrador de credenciales.

Todo dato de salud o ajuste personal que se persista localmente pasa por aquí:
el contenido en disco es ilegible sin la clave, y la clave vive en Windows
Credential Manager (vía ``keyring``), no junto a los datos. Las escrituras son
atómicas (archivo temporal + ``os.replace``).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Protocol

from cryptography.fernet import Fernet, InvalidToken

from glucosa.errors import SecureStoreBusyError, SecureStoreError

SERVICE_NAME = "glucosa"
KEY_ENTRY = "data-key"
_KEY_LOCK = threading.Lock()  # Streamlit ejecuta cada sesión en su propio hilo


class KeyProvider(Protocol):
    def key(self, create: bool = True) -> bytes: ...


class KeyringKeyProvider:
    """Genera una clave Fernet la primera vez y la reutiliza desde ``keyring``."""

    def __init__(self, backend: Any | None = None) -> None:
        if backend is None:
            import keyring

            backend = keyring
        self._backend = backend
        self._cached: bytes | None = None

    def key(self, create: bool = True) -> bytes:
        """Clave de cifrado. Con ``create=False`` nunca genera una nueva (p. ej. al leer datos)."""
        with _KEY_LOCK:
            if self._cached is None:
                self._cached = self._load_or_create(create)
            return self._cached

    @staticmethod
    def _validated(stored: str) -> bytes:
        try:
            raw = stored.encode("ascii")
            Fernet(raw)
        except (UnicodeEncodeError, ValueError):
            raise SecureStoreError(
                "La clave de cifrado guardada en el Administrador de credenciales está dañada."
            ) from None
        return raw

    def _load_or_create(self, create: bool) -> bytes:
        stored = self._backend.get_password(SERVICE_NAME, KEY_ENTRY)
        if stored:
            return self._validated(stored)
        if not create:
            raise SecureStoreError(
                "No hay una clave de cifrado guardada en el Administrador de credenciales."
            )
        fresh = Fernet.generate_key()
        self._backend.set_password(SERVICE_NAME, KEY_ENTRY, fresh.decode("ascii"))
        # Se relee lo realmente guardado: si otro proceso creó la clave a la vez, gana la suya.
        confirmed = self._backend.get_password(SERVICE_NAME, KEY_ENTRY)
        return self._validated(confirmed) if confirmed else fresh


class EncryptedJsonStore:
    def __init__(self, path: Path, key_provider: KeyProvider) -> None:
        self._path = Path(path)
        self._key_provider = key_provider

    def read(self) -> dict[str, Any] | None:
        if not self._path.exists():
            return None
        try:
            decrypted = Fernet(self._key_provider.key(create=False)).decrypt(
                self._path.read_bytes()
            )
            data = json.loads(decrypted)
        except (InvalidToken, ValueError, OSError) as exc:
            raise SecureStoreError(
                f"No se pudo leer el archivo local protegido ({self._path.name}). "
                "Puede estar dañado o la clave de cifrado cambió."
            ) from exc
        if not isinstance(data, dict):
            raise SecureStoreError(f"Contenido inesperado en {self._path.name}.")
        return data

    def write(self, data: dict[str, Any]) -> None:
        token = Fernet(self._key_provider.key()).encrypt(json.dumps(data).encode("utf-8"))
        atomic_write(self._path, token)


def atomic_write(path: Path, payload: bytes) -> None:
    """Escribe ``payload`` en ``path`` de forma atómica (temporal + ``os.replace``).

    Ante cualquier fallo el archivo anterior queda intacto y no se deja el temporal.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


class EncryptedBytesStore:
    """Contenedor cifrado (Fernet) de bytes arbitrarios, p. ej. una base SQLite serializada.

    La clave nunca se guarda junto al archivo: la entrega ``key_provider``
    (Administrador de credenciales de Windows).
    """

    def __init__(self, path: Path, key_provider: KeyProvider) -> None:
        self._path = Path(path)
        self._key_provider = key_provider

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> bytes | None:
        if not self._path.exists():
            return None
        try:
            ciphertext = self._path.read_bytes()
        except OSError as exc:
            raise SecureStoreBusyError(
                "No se pudo leer el archivo protegido en este momento (puede estar en uso por "
                "otro programa). Reintenta en unos segundos; el archivo no se tocó."
            ) from exc
        try:
            return Fernet(self._key_provider.key(create=False)).decrypt(ciphertext)
        except (InvalidToken, ValueError) as exc:
            raise SecureStoreError(
                f"No se pudo leer el archivo local protegido ({self._path.name}). "
                "Puede estar dañado o la clave de cifrado cambió."
            ) from exc

    def write(self, data: bytes) -> None:
        atomic_write(self._path, Fernet(self._key_provider.key()).encrypt(data))

    def stamp(self) -> tuple[int, int, bytes] | None:
        """Huella del archivo (fecha, tamaño y hash del contenido) para detectar cambios ajenos.

        Solo la fecha y el tamaño no bastan: dos versiones escritas en el mismo instante con el
        mismo tamaño (el cifrado rellena a bloques de 16 bytes) serían indistinguibles.
        """
        try:
            info = self._path.stat()
            digest = hashlib.blake2b(self._path.read_bytes(), digest_size=16).digest()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise SecureStoreBusyError(
                "No se pudo comprobar el archivo protegido en este momento (en uso por otro "
                "programa). Reintenta en unos segundos."
            ) from exc
        return (info.st_mtime_ns, info.st_size, digest)


def derive_subkey(master_key: bytes, label: str) -> bytes:
    """Subclave de 32 bytes (HMAC-SHA256) para un propósito concreto.

    Evita reutilizar la clave de cifrado para otros fines (p. ej. seudonimizar
    números de serie) sin tener que guardar otro secreto.
    """
    return hmac.new(master_key, label.encode("utf-8"), hashlib.sha256).digest()
