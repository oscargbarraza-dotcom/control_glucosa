"""Configuración local leída de variables de entorno / archivo ``.env``.

Nada de esto es una credencial administrativa: la API key de Firebase y el
ID de cliente OAuth son identificadores de cliente. Aun así se mantienen fuera
del repositorio (``.env`` está en ``.gitignore``) y no aparecen en ``repr``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from glucosa.auth.oauth_client import OAuthClient, load_oauth_client
from glucosa.errors import ConfigError
from glucosa.paths import default_data_dir

DEFAULT_PROJECT_ID = "seguimiento-glucosa"
_PROJECT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"  # solo desarrollo


@dataclass(frozen=True)
class AppConfig:
    project_id: str
    api_key: str | None = field(default=None, repr=False)
    oauth_client_file: Path | None = None  # ruta del JSON descargado (privada, fuera de OneDrive)

    def require_api_key(self) -> str:
        if not self.api_key:
            raise ConfigError(
                "Falta GLUCOSA_FIREBASE_API_KEY. Cópiala desde la consola de Firebase "
                "(app web de Windows) a tu archivo .env."
            )
        return self.api_key

    def require_oauth_client(self) -> OAuthClient:
        if self.oauth_client_file is None:
            raise ConfigError(
                "Falta GLUCOSA_OAUTH_CLIENT_FILE: ruta del JSON del cliente OAuth de escritorio "
                "(guárdalo fuera de OneDrive y no lo versiones)."
            )
        return load_oauth_client(self.oauth_client_file, expected_project_id=self.project_id)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _path(value: str | None) -> Path | None:
    cleaned = _clean(value)
    return Path(os.path.expandvars(cleaned)) if cleaned else None


def load_config(env: Mapping[str, str]) -> AppConfig:
    """Construye la configuración a partir de un mapeo (puro, fácil de probar)."""
    return AppConfig(
        project_id=_clean(env.get("GLUCOSA_FIREBASE_PROJECT_ID")) or DEFAULT_PROJECT_ID,
        api_key=_clean(env.get("GLUCOSA_FIREBASE_API_KEY")),
        oauth_client_file=_path(env.get("GLUCOSA_OAUTH_CLIENT_FILE")),
    )


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return {k: v for k, v in dotenv_values(path).items() if v is not None}


def config_from_environment(project_env_file: Path | None = None) -> AppConfig:
    """Lee la configuración sin depender del directorio de trabajo.

    Orden de prioridad (de mayor a menor): variables de entorno no vacías,
    ``.env`` en la carpeta de datos local (``%LOCALAPPDATA%\\glucosa``, fuera de
    OneDrive) y, solo para desarrollo, ``.env`` en la raíz del proyecto.
    """
    try:
        data_dir = default_data_dir(os.environ.get("GLUCOSA_DATA_DIR"))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    merged = _read_env_file(project_env_file or _PROJECT_ENV_FILE)
    merged.update(_read_env_file(data_dir / ".env"))
    merged.update({k: v for k, v in os.environ.items() if v.strip()})
    return load_config(merged)
