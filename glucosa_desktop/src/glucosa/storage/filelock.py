"""Bloqueo exclusivo de archivo entre procesos (Windows: ``msvcrt``; otros: ``fcntl``).

Protege la ventana «comprobar que nadie cambió el archivo → reemplazarlo»: sin él, dos
importaciones simultáneas (p. ej. línea de comandos e interfaz) podrían pasar ambas la
comprobación y la segunda sobrescribiría a la primera sin avisar.
"""

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import IO

from glucosa.errors import SecureStoreError

if sys.platform == "win32":
    import msvcrt

    def _try_lock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


_POLL_SECONDS = 0.05


@contextmanager
def exclusive_lock(lock_path: Path, timeout: float = 10.0) -> Iterator[None]:
    """Mantiene un bloqueo exclusivo sobre ``lock_path`` mientras dura el bloque ``with``.

    Si no se obtiene dentro de ``timeout`` segundos lanza ``SecureStoreError``.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                _try_lock(handle)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise SecureStoreError(
                        "Hay otra importación en curso sobre la misma base de LibreView. "
                        "Espera a que termine y vuelve a intentarlo."
                    ) from None
                time.sleep(_POLL_SECONDS)
        try:
            yield
        finally:
            with suppress(OSError):
                _unlock(handle)
