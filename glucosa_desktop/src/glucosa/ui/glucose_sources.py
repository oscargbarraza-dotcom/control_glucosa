"""Acceso a datos de la página Glucosa (sin Streamlit).

* **Firebase (manual):** restaura la sesión guardada (sin navegador) y lee la colección de
  glucosa del propio usuario con su token. Solo lectura.
* **LibreView (sensor):** lee la base local cifrada y permite importar un CSV.
* **Rango objetivo:** se guarda por usuario en los ajustes locales cifrados.

Los dos orígenes son independientes: un fallo en uno no impide mostrar el otro.
"""

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from keyring.errors import KeyringError

from glucosa.auth.refresh import FirebaseTokenRefresher
from glucosa.auth.service import restore_stored_session
from glucosa.auth.session import AuthSession
from glucosa.auth.token_store import KeyringTokenStore
from glucosa.config import AppConfig, config_from_environment
from glucosa.data.firestore_client import FirestoreReader
from glucosa.data.firestore_decode import FirestoreDocument
from glucosa.data.parsing import parse_glucose, parse_meals
from glucosa.errors import (
    ConfigError,
    ConnectionProblem,
    GlucosaError,
    PermissionDeniedError,
    SecureStoreError,
    SessionExpiredError,
)
from glucosa.http import HttpClient, default_http
from glucosa.models.records import GlucoseRecord, MealRecord
from glucosa.paths import default_data_dir, libre_db_path
from glucosa.settings.user_settings import SettingsRepository, UserSettings
from glucosa.sources.libre.importer import import_libre_csv
from glucosa.sources.libre.models import ImportSummary, StoredReading, StoreStats
from glucosa.sources.libre.store import LibreStore
from glucosa.storage.secure_store import KeyProvider, KeyringKeyProvider

DEFAULT_RANGE = (70, 180)
_LOGIN_HINT = "Ejecuta: python -m glucosa.login login"
_CREDENTIALS_ERROR = (
    "No se pudo acceder al Administrador de credenciales de Windows. Reintenta; si persiste, "
    "revisa que tu sesión de Windows pueda usarlo."
)
_LOCAL_FILE_ERROR = "No se pudo leer o escribir un archivo local de _glucosa. Reintenta."
_NO_KEY_FOR_EXISTING_DATA = (
    "No se guardó el rango: hay datos cifrados de LibreView pero falta su clave en el "
    "Administrador de credenciales, y crear una nueva los dejaría ilegibles."
)


class SourceStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"  # aún no hay datos (p. ej., no se ha importado ningún CSV)
    CONFIG = "config"
    NO_SESSION = "no_session"
    SESSION_EXPIRED = "session_expired"
    ERROR = "error"


@dataclass(frozen=True)
class ManualLoad:
    status: SourceStatus
    records: tuple[GlucoseRecord, ...] = ()
    message: str | None = None
    rejected: int = (
        0  # documentos de Firebase que no pasaron la validación (se cuentan, no se ocultan)
    )
    # Instante de la última consulta EXITOSA a Firebase. No es una sincronización confirmada
    # desde Android: solo dice cuándo se leyó Firestore.
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class MealLoad:
    """Comidas de Firebase (solo lectura). Mismos estados y mensajes que ``ManualLoad``."""

    status: SourceStatus
    records: tuple[MealRecord, ...] = ()
    message: str | None = None
    rejected: int = 0  # documentos que no pasaron la validación (se cuentan, no se ocultan)
    warnings: int = 0  # avisos de validación (comida sin alimentos, posible duplicado…)
    fetched_at: datetime | None = None  # última consulta EXITOSA (no es una sincronización)


@dataclass(frozen=True)
class _Fetch:
    """Resultado interno de leer una colección: documentos o el estado que explica por qué no."""

    documents: tuple[FirestoreDocument, ...] = ()
    status: SourceStatus = SourceStatus.OK
    message: str | None = None


@dataclass(frozen=True)
class LibreLoad:
    status: SourceStatus
    readings: tuple[StoredReading, ...] = field(default=(), repr=False)
    stats: StoreStats | None = None
    message: str | None = None


@dataclass(frozen=True)
class TargetRange:
    low: int
    high: int
    notice: str | None = None  # por qué se usa el rango por defecto, si no es el guardado


class MealSources(Protocol):
    def load_meals(self) -> MealLoad: ...
    def session_marker(self) -> str | None: ...


class GlucoseSources(Protocol):
    def load_manual(self) -> ManualLoad: ...
    def load_libre(self) -> LibreLoad: ...
    def libre_signature(self) -> tuple[int, int] | None: ...
    def session_marker(self) -> str | None: ...
    def import_csv(self, file_name: str, content: bytes) -> ImportSummary: ...
    def target_range(self) -> tuple[int, int]: ...
    def target_range_info(self) -> TargetRange: ...
    def save_target_range(self, low: int, high: int) -> None: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DefaultGlucoseSources:
    def __init__(
        self,
        config: AppConfig | None = None,
        http: HttpClient | None = None,
        token_store: KeyringTokenStore | None = None,
        key_provider: KeyProvider | None = None,
        data_dir: Path | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._config = config
        self._http = http
        self._token_store = token_store
        self._key_provider = key_provider
        self._data_dir = data_dir
        self._clock = clock
        self._session: AuthSession | None = None

    # ------------------------------------------------------------ dependencias
    def _cfg(self) -> AppConfig:
        if self._config is None:
            self._config = config_from_environment()
        return self._config

    def _keys(self) -> KeyProvider:
        if self._key_provider is None:
            self._key_provider = KeyringKeyProvider()
        return self._key_provider

    def _base_dir(self) -> Path:
        return self._data_dir or default_data_dir(os.environ.get("GLUCOSA_DATA_DIR"))

    def _libre_path(self) -> Path:
        return libre_db_path(self._base_dir())

    def _client(self) -> HttpClient:
        if self._http is None:
            self._http = default_http()
        return self._http

    # ---------------------------------------------------------------- Firebase
    def _store(self) -> KeyringTokenStore:
        if self._token_store is None:
            self._token_store = KeyringTokenStore()
        return self._token_store

    def session_marker(self) -> str | None:
        """Huella del inicio de sesión guardado (``None`` = sin sesión), sin exponer el uid.

        Cambia al cerrar sesión o al entrar con otra cuenta por la línea de comandos, para que la
        interfaz descarte lo que tenía en caché.
        """
        try:
            login = self._store().load()
        except (KeyringError, OSError):
            return "no-disponible"
        if login is None:
            return None
        return hashlib.sha256(login.uid.encode("utf-8")).hexdigest()[:16]

    def _active_session(self, api_key: str) -> AuthSession | None:
        store = self._store()
        login = store.load()
        if login is None:  # cerraron sesión por la línea de comandos: no seguir con la anterior
            self._session = None
            return None
        if self._session is not None and self._session.uid != login.uid:
            self._session = None  # otra cuenta: no se reutiliza nada de la anterior
        if self._session is not None and not self._session.is_expired(self._clock()):
            return self._session
        refresher = FirebaseTokenRefresher(api_key, self._client(), self._clock)
        self._session = restore_stored_session(store, refresher)
        return self._session

    def _fetch(self, collection: str, order_field: str) -> _Fetch:
        """Lee una colección del usuario con su propio token (solo lectura) o explica por qué no."""
        try:
            config = self._cfg()
            api_key = config.require_api_key()
        except ConfigError as exc:
            return _Fetch(status=SourceStatus.CONFIG, message=str(exc))
        try:
            session = self._active_session(api_key)
            if session is None:
                return _Fetch(
                    status=SourceStatus.NO_SESSION,
                    message=f"No hay una sesión de Firebase guardada. {_LOGIN_HINT}",
                )
            reader = FirestoreReader(config.project_id, self._client())
            documents = reader.query_collection(
                session.uid, collection, session.id_token, order_field=order_field
            )
        except SessionExpiredError:
            self._session = None
            return _Fetch(
                status=SourceStatus.SESSION_EXPIRED,
                message=f"Tu sesión de Firebase venció. {_LOGIN_HINT}",
            )
        except (PermissionDeniedError, ConnectionProblem, GlucosaError) as exc:
            return _Fetch(status=SourceStatus.ERROR, message=str(exc))
        except KeyringError:
            return _Fetch(status=SourceStatus.ERROR, message=_CREDENTIALS_ERROR)
        except ValueError:
            return _Fetch(
                status=SourceStatus.ERROR,
                message="La configuración de Firebase no es válida (proyecto o usuario).",
            )
        return _Fetch(tuple(documents))

    def load_manual(self) -> ManualLoad:
        fetched = self._fetch("glucose_measurements", "measuredAt")
        if fetched.status is not SourceStatus.OK:
            return ManualLoad(fetched.status, message=fetched.message)
        parsed = parse_glucose(fetched.documents)
        rejected = sum(issue.severity == "error" for issue in parsed.issues)
        return ManualLoad(
            SourceStatus.OK, records=parsed.records, rejected=rejected, fetched_at=self._clock()
        )

    def load_meals(self) -> MealLoad:
        """Comidas del usuario: una sola consulta de lectura a ``meals`` (no escribe nada)."""
        fetched = self._fetch("meals", "eatenAt")
        if fetched.status is not SourceStatus.OK:
            return MealLoad(fetched.status, message=fetched.message)
        parsed = parse_meals(fetched.documents)
        rejected = sum(issue.severity == "error" for issue in parsed.issues)
        return MealLoad(
            SourceStatus.OK,
            records=parsed.records,
            rejected=rejected,
            warnings=len(parsed.issues) - rejected,
            fetched_at=self._clock(),
        )

    # --------------------------------------------------------------- LibreView
    def libre_signature(self) -> tuple[int, int] | None:
        try:
            info = self._libre_path().stat()
        except (FileNotFoundError, ValueError, OSError):
            return None
        return (info.st_mtime_ns, info.st_size)

    def load_libre(self) -> LibreLoad:
        try:
            path = self._libre_path()
            if not path.exists():
                return LibreLoad(SourceStatus.EMPTY)
            with LibreStore.open(path, self._keys()) as store:
                stats = store.stats()
                readings = tuple(store.readings())
        except GlucosaError as exc:
            return LibreLoad(SourceStatus.ERROR, message=str(exc))
        except ValueError as exc:  # p. ej. carpeta de datos dentro de OneDrive
            return LibreLoad(SourceStatus.ERROR, message=str(exc))
        except KeyringError:
            return LibreLoad(SourceStatus.ERROR, message=_CREDENTIALS_ERROR)
        except OSError:
            return LibreLoad(SourceStatus.ERROR, message=_LOCAL_FILE_ERROR)
        if stats.total == 0:
            return LibreLoad(SourceStatus.EMPTY, stats=stats)
        return LibreLoad(SourceStatus.OK, readings=readings, stats=stats)

    def import_csv(self, file_name: str, content: bytes) -> ImportSummary:
        """Importa un CSV (propaga ``GlucosaError``). No se crea la base si el CSV es inválido."""
        with LibreStore.open(self._libre_path(), self._keys()) as store:
            return import_libre_csv(content, file_name, store, now=self._clock())

    # ---------------------------------------------------------- rango objetivo
    def _settings(self) -> tuple[SettingsRepository, str] | None:
        if self._session is None:
            return None
        repository = SettingsRepository(self._base_dir(), self._keys())
        return repository, self._session.uid

    def target_range_info(self) -> TargetRange:
        """Rango objetivo guardado; si se usa el de por defecto, ``notice`` explica por qué."""
        default_low, default_high = DEFAULT_RANGE
        fallback = f"{default_low}–{default_high} mg/dL"
        try:
            found = self._settings()
            if found is None:
                return TargetRange(
                    *DEFAULT_RANGE,
                    notice=(
                        "Sin sesión de Firebase no se puede leer el rango objetivo que guardaste: "
                        f"se usa el predeterminado ({fallback})."
                    ),
                )
            repository, uid = found
            settings = repository.load(uid)
        except (GlucosaError, ValueError, KeyringError, OSError):
            return TargetRange(
                *DEFAULT_RANGE,
                notice=(
                    "Tus ajustes locales están ilegibles: se usa el rango predeterminado "
                    f"({fallback}) y no se pueden guardar cambios."
                ),
            )
        return TargetRange(settings.target_low, settings.target_high)

    def target_range(self) -> tuple[int, int]:
        info = self.target_range_info()
        return info.low, info.high

    def _refuse_new_key_when_data_exists(self) -> None:
        """Crear una clave nueva dejaría ilegible la base LibreView que ya existe."""
        try:
            if self._libre_path().exists():
                self._keys().key(create=False)
        except SecureStoreError:
            raise SecureStoreError(_NO_KEY_FOR_EXISTING_DATA) from None

    def save_target_range(self, low: int, high: int) -> None:
        found = self._settings()
        if found is None:
            raise ValueError("Inicia sesión para guardar el rango objetivo.")
        repository, uid = found
        self._refuse_new_key_when_data_exists()
        try:
            current = repository.load(uid)
            repository.save(
                uid, UserSettings(target_low=low, target_high=high, height_cm=current.height_cm)
            )
        except SecureStoreError as exc:
            raise SecureStoreError(
                "No se guardó: no se pudo leer tu configuración local protegida. "
                "El archivo no se modificó."
            ) from exc
        except KeyringError:
            raise SecureStoreError(f"No se guardó. {_CREDENTIALS_ERROR}") from None
        except OSError:
            raise SecureStoreError(f"No se guardó. {_LOCAL_FILE_ERROR}") from None
