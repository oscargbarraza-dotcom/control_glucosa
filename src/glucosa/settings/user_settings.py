"""Ajustes por usuario, guardados cifrados y aislados por usuario.

* Rango objetivo de glucosa: 70–180 mg/dL por defecto, configurable.
* Altura (opcional): solo existe aquí; Android no la sincroniza. Se usa
  únicamente para calcular el IMC, y la UI debe indicarlo.

La carpeta de cada usuario usa un hash del uid (no el uid) y vive en el
directorio de datos local de la aplicación, fuera de OneDrive.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

from glucosa.errors import SecureStoreError
from glucosa.storage.secure_store import EncryptedJsonStore, KeyProvider

GLUCOSE_BOUNDS = (20, 600)  # mismo rango que valida la app al registrar
HEIGHT_BOUNDS_CM = (50.0, 250.0)  # mismo rango que valida el perfil de la app


def _exact_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Se esperaba un entero.")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Se esperaba un número.")
    return float(value)


@dataclass(frozen=True)
class UserSettings:
    target_low: int = 70
    target_high: int = 180
    height_cm: float | None = None

    def __post_init__(self) -> None:
        low_bound, high_bound = GLUCOSE_BOUNDS
        if not (low_bound <= self.target_low < self.target_high <= high_bound):
            raise ValueError(
                f"El rango objetivo debe cumplir {low_bound} ≤ mínimo < máximo ≤ {high_bound}."
            )
        if self.height_cm is not None:
            low, high = HEIGHT_BOUNDS_CM
            if not low <= self.height_cm <= high:
                raise ValueError(f"La altura debe estar entre {low:g} y {high:g} cm.")


class SettingsRepository:
    def __init__(self, base_dir: Path, key_provider: KeyProvider) -> None:
        self._base_dir = Path(base_dir)
        self._key_provider = key_provider

    def _store(self, uid: str) -> EncryptedJsonStore:
        folder = hashlib.sha256(uid.encode("utf-8")).hexdigest()[:32]
        path = self._base_dir / "users" / folder / "settings.enc"
        return EncryptedJsonStore(path, self._key_provider)

    def load(self, uid: str) -> UserSettings:
        data = self._store(uid).read()
        if data is None:
            return UserSettings()
        try:
            return UserSettings(
                target_low=_exact_int(data["target_low"]),
                target_high=_exact_int(data["target_high"]),
                height_cm=_optional_float(data.get("height_cm")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SecureStoreError("Los ajustes guardados son inválidos.") from exc

    def save(self, uid: str, settings: UserSettings) -> None:
        self._store(uid).write(asdict(settings))
