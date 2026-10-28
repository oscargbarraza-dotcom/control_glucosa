"""Importación incremental, idempotente y transaccional de un CSV de LibreView.

Reglas de deduplicación (decisiones de la Fase 4):

* **Historial (tipo 0):** clave = dispositivo + minuto local (+ pasada de la hora repetida) + tipo.
  - misma clave y mismo valor → *repetido* (no se inserta);
  - misma clave y valor distinto → *conflicto*: no se sobrescribe ni se inserta; queda
    registrado y la clave sigue bloqueada en importaciones posteriores;
  - clave nueva → se inserta.
* **Escaneos (tipo 1):** clave = dispositivo + minuto local (+ pasada) + tipo + **valor**. El CSV
  solo llega al minuto, así que dos escaneos del mismo minuto con valores distintos son eventos
  distintos (no hay conflicto posible); los idénticos son repetidos.
* Dispositivos distintos son siempre registros independientes.
* Los registros de Firebase no participan en ninguna de estas comparaciones.
* Alimentos, notas y otros eventos del CSV se cuentan pero no se conservan.
* No se guarda el nombre original del archivo (suele incluir el del paciente): solo una etiqueta
  neutra con la fecha que aparezca en él y el hash del contenido.

Los logs contienen solo conteos: nunca valores de glucosa, nombres de archivo ni hashes.
"""

import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from glucosa.sources.libre.csv_parser import parse_libre_csv
from glucosa.sources.libre.models import ImportSummary, ParsedReading, RecordType
from glucosa.sources.libre.store import (
    ConflictRecord,
    ImportPlan,
    LibreStore,
    NewReading,
    StoreIndex,
)

logger = logging.getLogger("glucosa.libre.importer")
_EVENT_KEYS = ("alimento", "nota", "otros")


@dataclass
class _Classification:
    new_readings: list[NewReading] = field(default_factory=list)
    conflict_records: list[ConflictRecord] = field(default_factory=list)
    repeated: int = 0
    conflicts: int = 0
    rows_in_conflict: int = 0


def display_name(file_name: str, file_sha256: str) -> str:
    """Etiqueta para mostrar una exportación SIN revelar el nombre del archivo.

    El nombre original suele incluir el del paciente. Se muestra la fecha que aparezca en él
    (dd-mm-aaaa) y los 8 primeros caracteres del hash del contenido.
    """
    match = re.search(r"\d{2}-\d{2}-\d{4}", file_name)
    label = f"exportación del {match.group()}" if match else "exportación"
    return f"{label} [{file_sha256[:8]}]"


def _distinct(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))


def _as_new(device_id: str, reading: ParsedReading) -> NewReading:
    return NewReading(
        device_id=device_id,
        local_minute=reading.local_minute,
        instant_utc=reading.instant_utc,
        utc_offset_minutes=reading.utc_offset_minutes,
        time_flag=reading.time_flag,
        record_type=reading.record_type,
        glucose_mg_dl=reading.glucose_mg_dl,
        fold=reading.fold,
    )


def _classify_historic(
    slot: tuple[str, str, int],
    rows: list[ParsedReading],
    index: StoreIndex,
    out: _Classification,
) -> None:
    device_id, minute, fold = slot
    values = [r.glucose_mg_dl for r in rows]
    if (device_id, minute, fold, int(RecordType.HISTORIC)) in index.blocked:
        out.conflicts += 1
        out.rows_in_conflict += len(rows)
        return
    existing = index.historic.get(slot)
    if existing is not None:
        differing = _distinct([v for v in values if v != existing])
        out.repeated += sum(v == existing for v in values)
        if differing:
            out.conflicts += 1
            out.rows_in_conflict += sum(v != existing for v in values)
            out.conflict_records += [
                ConflictRecord(device_id, minute, RecordType.HISTORIC, existing, v, fold)
                for v in differing
            ]
        return
    distinct = _distinct(values)
    if len(distinct) == 1:
        out.new_readings.append(_as_new(device_id, rows[0]))
        out.repeated += len(rows) - 1
        return
    out.conflicts += 1
    out.rows_in_conflict += len(rows)
    out.conflict_records += [
        ConflictRecord(device_id, minute, RecordType.HISTORIC, None, v, fold) for v in distinct
    ]


def _classify(parsed_readings: tuple[ParsedReading, ...], store: LibreStore) -> _Classification:
    index = store.index()
    devices: dict[tuple[str, str], str] = {}
    historic: dict[tuple[str, str, int], list[ParsedReading]] = {}
    scans: dict[tuple[str, str, int, int], list[ParsedReading]] = {}
    for reading in parsed_readings:
        device_id = devices.setdefault(
            (reading.model, reading.serial), store.device_id_for(reading.model, reading.serial)
        )
        slot = (device_id, reading.local_minute, reading.fold)
        if reading.record_type is RecordType.HISTORIC:
            historic.setdefault(slot, []).append(reading)
        else:
            scans.setdefault((*slot, reading.glucose_mg_dl), []).append(reading)

    out = _Classification()
    for slot, rows in historic.items():
        _classify_historic(slot, rows, index, out)
    for key, rows in scans.items():
        if key in index.scans:
            out.repeated += len(rows)
        else:
            out.new_readings.append(_as_new(key[0], rows[0]))
            out.repeated += len(rows) - 1
    out.new_readings.sort(key=lambda r: (r.instant_utc, r.device_id, int(r.record_type)))
    return out


def import_libre_csv(
    content: bytes, file_name: str, store: LibreStore, now: datetime | None = None
) -> ImportSummary:
    """Importa ``content`` (bytes del CSV) en ``store``. No lee ni modifica el archivo original."""
    imported_at = now or datetime.now(UTC)
    parsed = parse_libre_csv(content)
    sha256 = hashlib.sha256(content).hexdigest()
    label = display_name(file_name, sha256)

    with store.exclusive():  # estado al día + sin interferencia mientras se clasifica y aplica
        seen_before = store.has_file_hash(sha256)
        result = _classify(parsed.readings, store)
        store.apply_import(
            ImportPlan(
                imported_at_utc=imported_at,
                file_name=label,
                file_sha256=sha256,
                file_bytes=len(content),
                rows_total=parsed.rows_total,
                repeated=result.repeated,
                conflicts=result.conflicts,
                period_start=parsed.period_start,
                period_end=parsed.period_end,
                new_readings=tuple(result.new_readings),
                conflict_records=tuple(result.conflict_records),
                invalid_rows=parsed.invalid,
                invalid_total=parsed.invalid_total,
            )
        )
        stats = store.stats()

    kinds = Counter(r.record_type for r in parsed.readings)
    new_kinds = Counter(r.record_type for r in result.new_readings)
    summary = ImportSummary(
        file_name=label,
        file_sha256=sha256,
        file_bytes=len(content),
        same_file_seen_before=seen_before,
        period_start=parsed.period_start,
        period_end=parsed.period_end,
        rows_total=parsed.rows_total,
        historic_rows=kinds[RecordType.HISTORIC],
        scan_rows=kinds[RecordType.SCAN],
        other_events={key: parsed.other_events.get(key, 0) for key in _EVENT_KEYS},
        new=len(result.new_readings),
        new_historic=new_kinds[RecordType.HISTORIC],
        new_scans=new_kinds[RecordType.SCAN],
        repeated=result.repeated,
        invalid=parsed.invalid_total,
        invalid_by_reason=dict(parsed.invalid_by_reason),
        conflicts=result.conflicts,
        rows_in_conflict=result.rows_in_conflict,
        total_consolidated=stats.total,
        total_historic=stats.historic,
        total_scans=stats.scans,
        imported_at_utc=imported_at,
        last_import_utc=stats.last_import_utc or imported_at,
    )
    logger.info(
        "Importación LibreView: nuevos=%d repetidos=%d inválidos=%d conflictos=%d total=%d",
        summary.new,
        summary.repeated,
        summary.invalid,
        summary.conflicts,
        summary.total_consolidated,
    )
    return summary
