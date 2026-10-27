"""Modelos de la fuente LibreView (inmutables).

Los ``repr`` no incluyen números de serie ni listas de lecturas para que no
terminen por accidente en un log.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum


class RecordType(IntEnum):
    HISTORIC = 0  # historial del sensor (una lectura cada ~15 min)
    SCAN = 1  # escaneo manual del sensor


class TimeFlag(StrEnum):
    NORMAL = "normal"
    AMBIGUOUS = "ambiguous"  # hora local repetida por cambio de horario
    NONEXISTENT = "nonexistent"  # hora local que no existió por cambio de horario


@dataclass(frozen=True)
class ParsedReading:
    line_number: int
    model: str
    serial: str = field(repr=False)
    local_minute: str  # 'AAAA-MM-DDTHH:MM', valor original del archivo (hora local de Chile)
    instant_utc: datetime
    utc_offset_minutes: int
    time_flag: TimeFlag
    record_type: RecordType
    glucose_mg_dl: int = field(repr=False)
    fold: int = 0  # 1 = segunda pasada de la hora repetida (fin del horario de verano)


@dataclass(frozen=True)
class InvalidRow:
    line_number: int
    reason: str


@dataclass(frozen=True)
class ParsedExport:
    metadata_present: bool
    rows_total: int  # filas de datos no vacías
    readings: tuple[ParsedReading, ...] = field(repr=False)
    invalid: tuple[InvalidRow, ...]  # solo las primeras (límite); el total exacto está abajo
    invalid_total: int
    invalid_by_reason: Mapping[str, int]
    other_events: Mapping[str, int]  # alimento / nota / otros: solo conteos, no se conservan
    period_start: str | None
    period_end: str | None


@dataclass(frozen=True)
class StoredReading:
    device_id: str
    local_minute: str
    instant_utc: datetime
    utc_offset_minutes: int
    time_flag: TimeFlag
    record_type: RecordType
    glucose_mg_dl: int = field(repr=False)
    import_id: int
    fold: int = 0


@dataclass(frozen=True)
class ImportRecord:
    id: int
    imported_at_utc: datetime
    file_name: str
    file_sha256: str
    file_bytes: int
    rows_total: int
    inserted: int
    repeated: int
    invalid: int
    conflicts: int
    period_start: str | None
    period_end: str | None


@dataclass(frozen=True)
class StoreStats:
    total: int
    historic: int
    scans: int
    period_start: str | None
    period_end: str | None
    last_import_utc: datetime | None
    imports: int


@dataclass(frozen=True)
class ImportSummary:
    file_name: str
    file_sha256: str
    file_bytes: int
    same_file_seen_before: bool
    period_start: str | None
    period_end: str | None
    rows_total: int
    historic_rows: int  # lecturas de historial válidas en el archivo
    scan_rows: int
    other_events: Mapping[str, int]
    new: int
    new_historic: int
    new_scans: int
    repeated: int
    invalid: int
    invalid_by_reason: Mapping[str, int]
    conflicts: int  # claves en conflicto
    rows_in_conflict: int
    total_consolidated: int
    total_historic: int
    total_scans: int
    imported_at_utc: datetime
    last_import_utc: datetime

    @property
    def hi_lo(self) -> int:
        return self.invalid_by_reason.get("hi", 0) + self.invalid_by_reason.get("lo", 0)
