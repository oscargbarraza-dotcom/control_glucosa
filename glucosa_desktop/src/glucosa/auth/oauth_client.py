"""Carga del cliente OAuth de escritorio desde el JSON descargado de Google Cloud.

El proyecto NUNCA copia el ``client_secret`` a ``.env``, al código ni al
repositorio: lee el archivo descargado directamente desde su ubicación privada
(``GLUCOSA_OAUTH_CLIENT_FILE``), que debe estar fuera de OneDrive.

Validaciones defensivas:

* debe ser un cliente tipo "Aplicación de escritorio" (clave ``installed``);
* los endpoints de Google quedan fijados (un archivo alterado no puede
  redirigir el ``code`` ni el secreto a otro servidor);
* si trae ``project_id``, debe coincidir con el del proyecto;
* los mensajes de error nunca incluyen el contenido del archivo.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from glucosa.errors import ConfigError
from glucosa.paths import is_inside_onedrive

MAX_FILE_BYTES = 10_000
ALLOWED_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
ALLOWED_TOKEN_URI = "https://oauth2.googleapis.com/token"
_CLIENT_ID_SUFFIX = ".apps.googleusercontent.com"
_SETTING = "GLUCOSA_OAUTH_CLIENT_FILE"


@dataclass(frozen=True)
class OAuthClient:
    client_id: str
    client_secret: str = field(repr=False)
    auth_uri: str = ALLOWED_AUTH_URI
    token_uri: str = ALLOWED_TOKEN_URI
    project_id: str | None = None


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise ConfigError(
            f"No se encontró el archivo del cliente OAuth. Revisa {_SETTING} en tu archivo .env."
        )
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ConfigError("El archivo del cliente OAuth tiene un tamaño inesperado.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ConfigError("El archivo del cliente OAuth no es un JSON válido.") from None
    if not isinstance(data, dict):
        raise ConfigError("El archivo del cliente OAuth no tiene el formato esperado.")
    return data


def _installed_section(data: dict) -> dict:
    section = data.get("installed")
    if isinstance(section, dict):
        return section
    if "web" in data:
        raise ConfigError(
            "El cliente es de tipo Web. Se necesita un cliente de tipo "
            "'Aplicación de escritorio' (el JSON debe tener la clave 'installed')."
        )
    raise ConfigError("El archivo del cliente OAuth no corresponde a una Aplicación de escritorio.")


def load_oauth_client(path: Path, expected_project_id: str | None) -> OAuthClient:
    path = Path(path)
    if is_inside_onedrive(path):
        raise ConfigError(
            "El archivo del cliente OAuth está dentro de OneDrive. Muévelo a una carpeta "
            "privada fuera de OneDrive (por ejemplo %LOCALAPPDATA%\\glucosa\\secrets)."
        )
    section = _installed_section(_read_json(path))

    client_id = section.get("client_id")
    client_secret = section.get("client_secret")
    if not (isinstance(client_id, str) and client_id.endswith(_CLIENT_ID_SUFFIX)):
        raise ConfigError("El client_id del archivo no tiene el formato de Google esperado.")
    if not (isinstance(client_secret, str) and client_secret.strip()):
        raise ConfigError("El archivo del cliente OAuth no incluye client_secret.")

    auth_uri = section.get("auth_uri", ALLOWED_AUTH_URI)
    token_uri = section.get("token_uri", ALLOWED_TOKEN_URI)
    if auth_uri != ALLOWED_AUTH_URI or token_uri != ALLOWED_TOKEN_URI:
        raise ConfigError("El archivo declara un endpoint de OAuth que no es el de Google.")

    project_id = section.get("project_id")
    if expected_project_id and project_id and project_id != expected_project_id:
        raise ConfigError(
            "El cliente pertenece a otro proyecto de Google Cloud "
            f"(se esperaba {expected_project_id})."
        )
    return OAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        auth_uri=auth_uri,
        token_uri=token_uri,
        project_id=project_id if isinstance(project_id, str) else None,
    )
