"""Base local de LibreView: SQLite en memoria dentro de un contenedor cifrado.

* El archivo en disco es un blob Fernet con la base SQLite serializada; la clave la
  entrega el Administrador de credenciales de Windows y nunca se guarda junto a él.
* Cada importación es **una transacción** en memoria. Solo si termina bien se serializa,
  se cifra y se reemplaza el archivo de forma atómica; ante cualquier error el archivo
  anterior queda intacto y la memoria se resincroniza con el disco.
* Entre procesos, un bloqueo de archivo cubre «comprobar que nadie cambió el archivo →
  reemplazarlo»: una importación simultánea no puede pisar a otra sin avisar.
* La ruta no puede estar dentro de OneDrive.

Limitación conocida y aceptada: el cifrado autentica el contenido pero no su antigüedad;
si alguien restaura una copia anterior del archivo (con la misma clave) se aceptará. La
base se reconstruye siempre reimportando los CSV, que son la fuente de verdad.
"""

import hashlib
import hmac
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from glucosa.errors import LibreStoreError, SecureStoreBusyError, SecureStoreError
from glucosa.limits import GLUCOSE_RANGE
from glucosa.paths import is_inside_onedrive
from glucosa.sources.libre.models import (
    ImportRecord,
    InvalidRow,
    RecordType,
    StoredReading,
    StoreStats,
    TimeFlag,
)
from glucosa.storage.filelock import exclusive_lock
from glucosa.storage.secure_store import EncryptedBytesStore, KeyProvider, derive_subkey

SCHEMA_VERSION = 1
_DEVICE_LABEL = "libre-device-id"
_LOW, _HIGH = GLUCOSE_RANGE
_SCHEMA = f"""
CREATE TABLE libre_import (
    id INTEGER PRIMARY KEY,
    imported_at_utc TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    file_bytes INTEGER NOT NULL,
    rows_total INTEGER NOT NULL,
    inserted INTEGER NOT NULL,
    repeated INTEGER NOT NULL,
    invalid INTEGER NOT NULL,
    conflicts INTEGER NOT NULL,
    period_start TEXT,
    period_end TEXT
);
CREATE TABLE libre_reading (
    id INTEGER PRIMARY KEY,
    device_id TEXT NOT NULL,
    local_minute TEXT NOT NULL,
    fold INTEGER NOT NULL DEFAULT 0 CHECK (fold IN (0, 1)),
    instant_utc TEXT NOT NULL,
    utc_offset_min INTEGER NOT NULL,
    time_flag TEXT NOT NULL,
    record_type INTEGER NOT NULL CHECK (record_type IN (0, 1)),
    glucose_mg_dl INTEGER NOT NULL CHECK (glucose_mg_dl BETWEEN {_LOW} AND {_HIGH}),
    import_id INTEGER NOT NULL REFERENCES libre_import (id)
);
CREATE UNIQUE INDEX ux_libre_historic ON libre_reading (device_id, local_minute, fold)
    WHERE record_type = 0;
CREATE UNIQUE INDEX ux_libre_scan ON libre_reading (device_id, local_minute, fold, glucose_mg_dl)
    WHERE record_type = 1;
CREATE INDEX ix_libre_instant ON libre_reading (instant_utc);
CREATE TABLE libre_conflict (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES libre_import (id),
    device_id TEXT NOT NULL,
    local_minute TEXT NOT NULL,
    fold INTEGER NOT NULL DEFAULT 0,
    record_type INTEGER NOT NULL,
    existing_value INTEGER,
    incoming_value INTEGER NOT NULL,
    detected_at_utc TEXT NOT NULL,
    UNIQUE (device_id, local_minute, fold, record_type, incoming_value)
);
CREATE TABLE libre_invalid_row (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES libre_import (id),
    line_number INTEGER NOT NULL,
    reason_code TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class NewReading:
    device_id: str
    local_minute: str
    instant_utc: datetime
    utc_offset_minutes: int
    time_flag: TimeFlag
    record_type: RecordType
    glucose_mg_dl: int
    fold: int = 0


@dataclass(frozen=True)
class ConflictRecord:
    device_id: str
    local_minute: str
    record_type: RecordType
    existing_value: int | None
    incoming_value: int
    fold: int = 0


@dataclass(frozen=True)
class ImportPlan:
    imported_at_utc: datetime
    file_name: str
    file_sha256: str
    file_bytes: int
    rows_total: int
    repeated: int
    conflicts: int
    period_start: str | None
    period_end: str | None
    new_readings: tuple[NewReading, ...]
    conflict_records: tuple[ConflictRecord, ...]
    invalid_rows: tuple[InvalidRow, ...]  # solo las primeras; el total exacto va en invalid_total
    invalid_total: int | None = None

    @property
    def total_invalid(self) -> int:
        return len(self.invalid_rows) if self.invalid_total is None else self.invalid_total


@dataclass(frozen=True)
class StoreIndex:
    """Claves ya consolidadas. Cada clave incluye ``fold`` (hora repetida) como último elemento
    antes del valor/tipo: ``(dispositivo, minuto_local, fold[, valor | tipo])``."""

    historic: dict[tuple[str, str, int], int]
    scans: set[tuple[str, str, int, int]]
    blocked: set[tuple[str, str, int, int]]  # claves con un conflicto registrado (…, tipo)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


class LibreStore:
    def __init__(self, path: Path, key_provider: KeyProvider, lock_timeout: float = 10.0) -> None:
        if is_inside_onedrive(Path(path)):
            raise LibreStoreError(
                "La base de LibreView no puede guardarse dentro de OneDrive: los datos de salud "
                "(y sus copias anteriores) se sincronizarían a la nube."
            )
        self._key_provider = key_provider
        self._lock_timeout = lock_timeout
        self._lock_path = Path(path).with_name(Path(path).name + ".lock")
        self._blob = EncryptedBytesStore(path, key_provider)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._stamp: tuple[int, int, bytes] | None = None
        self._load()

    @classmethod
    def open(
        cls, path: Path, key_provider: KeyProvider, lock_timeout: float = 10.0
    ) -> "LibreStore":
        return cls(path, key_provider, lock_timeout)

    # ------------------------------------------------------------ ciclo de vida
    def _unreadable(self, reason: str) -> SecureStoreError:
        return SecureStoreError(
            f"No se pudo abrir la base local de LibreView ({reason}). Si perdiste la clave de "
            f"cifrado o el archivo está dañado: cierra la aplicación, elimina el archivo "
            f"«{self._blob.path.name}» de la carpeta de datos y vuelve a importar tus CSV de "
            "LibreView (los CSV originales no se modifican)."
        )

    def _load(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
            self._stamp = self._blob.stamp()
            try:
                data = self._blob.read()
            except SecureStoreBusyError:
                raise  # error transitorio: no se aconseja borrar nada
            except SecureStoreError:
                raise self._unreadable("clave incorrecta o archivo dañado") from None
            conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
            try:
                if data is None:
                    conn.executescript(_SCHEMA)
                    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                else:
                    conn.deserialize(data)
                    version = conn.execute("PRAGMA user_version").fetchone()[0]
                    if version != SCHEMA_VERSION:
                        raise self._unreadable(f"versión de esquema {version} no soportada")
                conn.execute("PRAGMA foreign_keys = ON")
            except sqlite3.DatabaseError:
                conn.close()
                raise self._unreadable("contenido inválido") from None
            except SecureStoreError:
                conn.close()
                raise
            self._conn = conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __del__(self) -> None:
        # Red de seguridad: libera la conexión en memoria si nadie llamó a close().
        with suppress(Exception):  # durante el cierre del intérprete puede fallar
            self.close()

    def __enter__(self) -> "LibreStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise LibreStoreError("La base de LibreView está cerrada.")
        return self._conn

    def refresh_if_changed(self) -> None:
        """Recarga desde disco si otro proceso modificó el archivo desde la última carga."""
        with self._lock:
            if self._blob.stamp() != self._stamp:
                self._load()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        """Sección crítica: estado al día y sin interferencia de otros hilos de este proceso."""
        with self._lock:
            self.refresh_if_changed()
            yield

    # ------------------------------------------------------------------ lectura
    def device_id_for(self, model: str, serial: str) -> str:
        """Seudónimo estable del dispositivo: el número de serie real no se almacena."""
        subkey = derive_subkey(self._key_provider.key(), _DEVICE_LABEL)
        digest = hmac.new(subkey, f"{model}\x1f{serial}".encode(), hashlib.sha256)
        return digest.hexdigest()[:32]

    def index(self) -> StoreIndex:
        with self._lock:
            db = self._db
            historic = {
                (d, m, f): v
                for d, m, f, v in db.execute(
                    "SELECT device_id, local_minute, fold, glucose_mg_dl FROM libre_reading "
                    "WHERE record_type = 0"
                )
            }
            scans = {
                (d, m, f, v)
                for d, m, f, v in db.execute(
                    "SELECT device_id, local_minute, fold, glucose_mg_dl FROM libre_reading "
                    "WHERE record_type = 1"
                )
            }
            blocked = {
                (d, m, f, t)
                for d, m, f, t in db.execute(
                    "SELECT device_id, local_minute, fold, record_type FROM libre_conflict"
                )
            }
            return StoreIndex(historic, scans, blocked)

    def readings(
        self,
        record_type: RecordType | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[StoredReading]:
        """Lecturas en orden determinista. ``start`` inclusivo, ``end`` exclusivo."""
        clauses, args = [], []
        if record_type is not None:
            clauses.append("record_type = ?")
            args.append(int(record_type))
        if start is not None:
            clauses.append("instant_utc >= ?")
            args.append(_iso(start))
        if end is not None:
            clauses.append("instant_utc < ?")
            args.append(_iso(end))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = (
            "SELECT device_id, local_minute, instant_utc, utc_offset_min, time_flag, "
            f"record_type, glucose_mg_dl, import_id, fold FROM libre_reading {where} "
            "ORDER BY instant_utc, record_type, device_id, glucose_mg_dl"
        )
        with self._lock:
            rows = self._db.execute(query, args).fetchall()
        return [
            StoredReading(
                device_id=d,
                local_minute=m,
                instant_utc=datetime.fromisoformat(i),
                utc_offset_minutes=o,
                time_flag=TimeFlag(f),
                record_type=RecordType(t),
                glucose_mg_dl=g,
                import_id=imp,
                fold=fold,
            )
            for d, m, i, o, f, t, g, imp, fold in rows
        ]

    def stats(self) -> StoreStats:
        with self._lock:
            db = self._db
            total, historic, first, last = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(record_type = 0), 0), MIN(local_minute), "
                "MAX(local_minute) FROM libre_reading"
            ).fetchone()
            imports, last_import = db.execute(
                "SELECT COUNT(*), MAX(imported_at_utc) FROM libre_import"
            ).fetchone()
        return StoreStats(
            total=total,
            historic=historic,
            scans=total - historic,
            period_start=first,
            period_end=last,
            last_import_utc=datetime.fromisoformat(last_import) if last_import else None,
            imports=imports,
        )

    def imports(self) -> list[ImportRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, imported_at_utc, file_name, file_sha256, file_bytes, rows_total, "
                "inserted, repeated, invalid, conflicts, period_start, period_end "
                "FROM libre_import ORDER BY id"
            ).fetchall()
        return [ImportRecord(r[0], datetime.fromisoformat(r[1]), *r[2:]) for r in rows]

    def has_file_hash(self, sha256: str) -> bool:
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM libre_import WHERE file_sha256 = ? LIMIT 1", (sha256,)
            ).fetchone()
        return row is not None

    # ---------------------------------------------------------------- escritura
    def _rollback(self) -> None:
        with suppress(sqlite3.Error):  # un ROLLBACK fallido no debe ocultar el error original
            self._db.execute("ROLLBACK")

    def apply_import(self, plan: ImportPlan) -> int:
        """Aplica una importación completa (todo o nada) y la persiste cifrada."""
        with self._lock:
            db = self._db
            db.execute("BEGIN IMMEDIATE")
            try:
                import_id = self._insert_import(plan)
                self._insert_readings(import_id, plan.new_readings)
                self._insert_conflicts(import_id, plan)
                self._insert_invalid_rows(import_id, plan.invalid_rows)
                db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                self._rollback()
                if "UNIQUE" in str(exc):
                    message = "Se intentó guardar un registro duplicado; la importación se canceló."
                else:
                    message = (
                        "Un registro no cumple las restricciones de la base "
                        "(p. ej. un valor fuera de rango); la importación se canceló."
                    )
                raise LibreStoreError(message) from None
            except BaseException:
                self._rollback()
                raise
            try:
                self._persist()
            except BaseException:
                self._resync_after_failure()
                raise
            return import_id

    def _insert_import(self, plan: ImportPlan) -> int:
        cursor = self._db.execute(
            "INSERT INTO libre_import (imported_at_utc, file_name, file_sha256, file_bytes, "
            "rows_total, inserted, repeated, invalid, conflicts, period_start, period_end) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _iso(plan.imported_at_utc),
                plan.file_name,
                plan.file_sha256,
                plan.file_bytes,
                plan.rows_total,
                len(plan.new_readings),
                plan.repeated,
                plan.total_invalid,
                plan.conflicts,
                plan.period_start,
                plan.period_end,
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def _insert_readings(self, import_id: int, readings: Sequence[NewReading]) -> None:
        self._db.executemany(
            "INSERT INTO libre_reading (device_id, local_minute, fold, instant_utc, "
            "utc_offset_min, time_flag, record_type, glucose_mg_dl, import_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r.device_id,
                    r.local_minute,
                    r.fold,
                    _iso(r.instant_utc),
                    r.utc_offset_minutes,
                    r.time_flag.value,
                    int(r.record_type),
                    r.glucose_mg_dl,
                    import_id,
                )
                for r in readings
            ],
        )

    def _insert_conflicts(self, import_id: int, plan: ImportPlan) -> None:
        self._db.executemany(
            "INSERT OR IGNORE INTO libre_conflict (import_id, device_id, local_minute, fold, "
            "record_type, existing_value, incoming_value, detected_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    import_id,
                    c.device_id,
                    c.local_minute,
                    c.fold,
                    int(c.record_type),
                    c.existing_value,
                    c.incoming_value,
                    _iso(plan.imported_at_utc),
                )
                for c in plan.conflict_records
            ],
        )

    def _insert_invalid_rows(self, import_id: int, rows: Sequence[InvalidRow]) -> None:
        self._db.executemany(
            "INSERT INTO libre_invalid_row (import_id, line_number, reason_code) VALUES (?, ?, ?)",
            [(import_id, row.line_number, row.reason) for row in rows],
        )

    # -------------------------------------------------------------- persistencia
    def _persist(self) -> None:
        # El bloqueo cubre «comprobar la huella → reemplazar el archivo» entre procesos.
        with exclusive_lock(self._lock_path, self._lock_timeout):
            if self._blob.stamp() != self._stamp:
                raise SecureStoreError(
                    "La base de LibreView fue modificada por otro proceso mientras se importaba. "
                    "No se sobrescribió nada; vuelve a intentar la importación."
                )
            self._blob.write(self._db.serialize())
            self._stamp = self._blob.stamp()

    def _resync_after_failure(self) -> None:
        """Memoria = disco tras un fallo: los registros existentes se conservan."""
        try:
            self._load()
        except SecureStoreError:
            self.close()
