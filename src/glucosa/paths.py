"""Ubicación de los datos locales (ajustes y, más adelante, caché cifrada).

Por defecto es la carpeta de datos locales del usuario de Windows
(``%LOCALAPPDATA%\\glucosa``), que NO se sincroniza con OneDrive. El proyecto
vive dentro de OneDrive, por eso ningún dato de salud se guarda junto al código
ni se acepta una carpeta de datos dentro de OneDrive.
"""

import os
from pathlib import Path

from platformdirs import user_data_dir

_ONEDRIVE_VARIABLES = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")


def _onedrive_roots() -> list[Path]:
    roots = (os.environ.get(name) for name in _ONEDRIVE_VARIABLES)
    return [Path(root).resolve() for root in roots if root]


def _is_inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def is_inside_onedrive(path: Path) -> bool:
    """True si ``path`` está dentro de alguna carpeta raíz de OneDrive."""
    resolved = Path(path).resolve()
    return any(_is_inside(resolved, root) for root in _onedrive_roots())


def default_data_dir(override: str | None = None) -> Path:
    if not (override and override.strip()):
        return Path(user_data_dir("glucosa", appauthor=False))
    chosen = Path(override.strip())
    if is_inside_onedrive(chosen):
        raise ValueError(
            "La carpeta de datos no puede estar dentro de OneDrive: "
            "los datos de salud se sincronizarían a la nube."
        )
    return chosen


LIBRE_DB_NAME = "libre.db.enc"


def libre_db_path(data_dir: Path | None = None) -> Path:
    """Archivo cifrado de la base LibreView: ``<datos>/data/libre.db.enc`` (fuera de OneDrive)."""
    base = (
        data_dir if data_dir is not None else default_data_dir(os.environ.get("GLUCOSA_DATA_DIR"))
    )
    return base / "data" / LIBRE_DB_NAME
