"""Lectura y validación de un CSV de LibreView.

No persiste nada: devuelve las lecturas de glucosa (historial y escaneos) ya
normalizadas y cuenta —sin conservarlos— los alimentos, notas y otros eventos.
Una fila inválida se registra con su causa y no detiene el resto. El archivo se procesa
fila a fila (sin acumular filas vacías) y con límites de tamaño, de filas y de filas
inválidas almacenadas, para que un archivo hostil no pueda agotar la memoria.

**Hora repetida.** Al terminar el horario de verano la hora local 23:00–23:59 ocurre dos
veces y el CSV no trae desfase. Las dos pasadas se distinguen por el orden de las filas
(se detecta automáticamente si el archivo es cronológico o inverso): la primera pasada
recibe ``fold=0`` (UTC-3) y la segunda ``fold=1`` (UTC-4). Si el archivo contiene solo una
de las dos pasadas no hay forma de saber cuál es: se asume la primera y la lectura queda
marcada como ``ambiguous``.
"""

import csv
import dataclasses
import io
import re
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import chain, islice

from glucosa.data.timeutil import SANTIAGO, parse_timestamp, wall_clock_issue
from glucosa.errors import LibreFormatError
from glucosa.sources.libre import csv_format as fmt
from glucosa.sources.libre.models import (
    InvalidRow,
    ParsedExport,
    ParsedReading,
    RecordType,
    TimeFlag,
)

_DIGITS = re.compile(r"\d+")
_DECIMAL = re.compile(r"\d+[.,]\d+")
_MAX_DIGITS = 6  # más dígitos no pueden ser una glucosa plausible (y evita enteros enormes)


def _decode(content: bytes) -> str:
    if len(content) > fmt.MAX_FILE_BYTES:
        raise LibreFormatError("El archivo supera el tamaño máximo permitido (25 MB).")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise LibreFormatError("El archivo no está codificado en UTF-8.") from None


def _numbered_rows(text: str) -> Iterator[tuple[int, list[str]]]:
    """Filas CSV (de una en una) con la línea física en que empieza cada una."""
    reader = csv.reader(io.StringIO(text, newline=""))
    previous_end = 0
    try:
        for cells in reader:
            yield previous_end + 1, cells
            previous_end = reader.line_num
    except csv.Error:
        raise LibreFormatError("El archivo CSV está mal formado.") from None


def _find_header(rows: list[tuple[int, list[str]]]) -> int:
    candidates = [[c.strip() for c in cells] for _, cells in rows[: fmt.HEADER_SEARCH_ROWS]]
    for index, cells in enumerate(candidates):
        if cells == list(fmt.HEADER):
            return index
    best = max(candidates, key=lambda c: len(set(c) & set(fmt.HEADER)), default=[])
    if len(set(best) & set(fmt.HEADER)) >= fmt.MIN_HEADER_OVERLAP:
        missing = [name for name in fmt.HEADER if name not in best][:5]
        raise LibreFormatError(
            "El encabezado del CSV de LibreView no coincide con el esperado. "
            f"Columnas faltantes: {', '.join(missing) or '(ninguna)'}."
        )
    raise LibreFormatError(
        "El archivo no parece una exportación de LibreView en español "
        "(no se encontró el encabezado esperado)."
    )


def _parse_glucose(text: str) -> tuple[int | None, str | None]:
    value = text.strip()
    if not value:
        return None, "valor_ausente"
    if value.upper() in ("HI", "LO"):
        return None, value.lower()
    if _DIGITS.fullmatch(value):
        low, high = fmt.PLAUSIBLE_GLUCOSE
        if len(value) > _MAX_DIGITS or not low <= int(value) <= high:
            return None, "fuera_de_rango_plausible"
        return int(value), None
    if _DECIMAL.fullmatch(value):
        return None, "valor_no_entero"
    return None, "valor_no_numerico"


def _parse_time(text: str) -> tuple[str, datetime, int, TimeFlag] | None:
    try:
        local = datetime.strptime(text.strip(), fmt.DATE_FORMAT)
        if not fmt.PLAUSIBLE_YEARS[0] <= local.year <= fmt.PLAUSIBLE_YEARS[1]:
            return None
        iso = local.strftime("%Y-%m-%dT%H:%M:00")
        moment = parse_timestamp(iso)
        issue = wall_clock_issue(iso)
        instant = moment.astimezone(UTC)
    except (ValueError, OverflowError):
        return None
    offset = moment.utcoffset()
    assert offset is not None  # parse_timestamp siempre devuelve desfase fijo
    return (
        local.strftime("%Y-%m-%dT%H:%M"),
        instant,
        int(offset.total_seconds() // 60),
        TimeFlag(issue) if issue else TimeFlag.NORMAL,
    )


def _parse_glucose_row(line: int, cells: list[str], kind: RecordType) -> ParsedReading | InvalidRow:
    model, serial = cells[fmt.COL_MODEL].strip(), cells[fmt.COL_SERIAL].strip()
    if not model or not serial:
        return InvalidRow(line, "dispositivo_ausente")
    when = _parse_time(cells[fmt.COL_TIMESTAMP])
    if when is None:
        return InvalidRow(line, "fecha_invalida")
    column = fmt.COL_HISTORIC if kind is RecordType.HISTORIC else fmt.COL_SCAN
    value, reason = _parse_glucose(cells[column])
    if value is None:
        return InvalidRow(line, reason or "valor_no_numerico")
    local_minute, instant, offset_minutes, flag = when
    return ParsedReading(
        line_number=line,
        model=model,
        serial=serial,
        local_minute=local_minute,
        instant_utc=instant,
        utc_offset_minutes=offset_minutes,
        time_flag=flag,
        record_type=kind,
        glucose_mg_dl=value,
    )


# ------------------------------------------------------------- hora repetida
def _is_ascending(sequence: list[ParsedReading]) -> bool:
    """¿Las filas del dispositivo van en orden cronológico? (mayoría de pasos)"""
    clear = [r.local_minute for r in sequence if r.time_flag is not TimeFlag.AMBIGUOUS]
    steps = list(zip(clear, clear[1:], strict=False))
    increasing = sum(b > a for a, b in steps)
    decreasing = sum(b < a for a, b in steps)
    return increasing >= decreasing


def _with_second_pass(reading: ParsedReading) -> ParsedReading:
    """Misma lectura interpretada en la segunda pasada de la hora repetida (``fold=1``)."""
    naive = datetime.fromisoformat(reading.local_minute + ":00").replace(tzinfo=SANTIAGO, fold=1)
    offset = naive.utcoffset()
    assert offset is not None
    return dataclasses.replace(
        reading,
        fold=1,
        instant_utc=naive.astimezone(UTC),
        utc_offset_minutes=int(offset.total_seconds() // 60),
    )


def _resolve_repeated_hour(readings: list[ParsedReading]) -> list[ParsedReading]:
    by_device: dict[tuple[str, str], list[int]] = {}
    for index, reading in enumerate(readings):
        by_device.setdefault((reading.model, reading.serial), []).append(index)

    resolved = list(readings)
    for indices in by_device.values():
        ascending = _is_ascending([readings[i] for i in indices])
        previous: ParsedReading | None = None
        second_pass = not ascending  # el primer bloque de un archivo inverso ya es la 2.ª pasada
        for i in indices:
            reading = readings[i]
            if reading.time_flag is not TimeFlag.AMBIGUOUS:
                previous = None
                continue
            if previous is None:
                second_pass = not ascending
            else:
                went_back = (
                    reading.local_minute < previous.local_minute
                    if ascending
                    else reading.local_minute > previous.local_minute
                )
                if went_back:
                    second_pass = ascending
            previous = reading
            if second_pass:
                resolved[i] = _with_second_pass(reading)
    return resolved


# ----------------------------------------------------------------- principal
def parse_libre_csv(content: bytes) -> ParsedExport:
    rows = _numbered_rows(_decode(content))
    first = list(islice(rows, fmt.HEADER_SEARCH_ROWS))
    if not first:
        raise LibreFormatError("El archivo está vacío.")
    header_index = _find_header(first)

    readings: list[ParsedReading] = []
    invalid_rows: list[InvalidRow] = []
    reasons: Counter[str] = Counter()
    others: Counter[str] = Counter()
    total = 0

    def reject(line: int, reason: str) -> None:
        reasons[reason] += 1
        if len(invalid_rows) < fmt.MAX_STORED_INVALID_ROWS:
            invalid_rows.append(InvalidRow(line, reason))

    for line, cells in chain(first[header_index + 1 :], rows):
        if not any(cell.strip() for cell in cells):
            continue
        total += 1
        if total > fmt.MAX_DATA_ROWS:
            raise LibreFormatError(f"El archivo supera el máximo de {fmt.MAX_DATA_ROWS} filas.")
        if len(cells) != len(fmt.HEADER):
            reject(line, "columnas_inesperadas")
            continue
        type_text = cells[fmt.COL_TYPE].strip()
        if not _DIGITS.fullmatch(type_text):
            reject(line, "tipo_invalido")
            continue
        record_type = int(type_text)
        if record_type in (fmt.TYPE_HISTORIC, fmt.TYPE_SCAN):
            parsed = _parse_glucose_row(line, cells, RecordType(record_type))
            if isinstance(parsed, InvalidRow):
                reject(parsed.line_number, parsed.reason)
            else:
                readings.append(parsed)
        else:
            others[fmt.OTHER_EVENT_LABELS.get(record_type, "otros")] += 1

    readings = _resolve_repeated_hour(readings)
    minutes = sorted(r.local_minute for r in readings)
    return ParsedExport(
        metadata_present=header_index > 0,
        rows_total=total,
        readings=tuple(readings),
        invalid=tuple(invalid_rows),
        invalid_total=sum(reasons.values()),
        invalid_by_reason=dict(reasons),
        other_events=dict(others),
        period_start=minutes[0] if minutes else None,
        period_end=minutes[-1] if minutes else None,
    )
