"""Interpretación de fechas de SeguimientoGlucosa.

La app Android guarda las fechas con ``DateTime.toIso8601String()``. Para una
fecha local el texto no lleva zona horaria (hora de pared del teléfono); para
una fecha UTC termina en ``Z``. Todo registro se origina en Chile, por lo que
el texto sin zona se interpreta como ``America/Santiago`` y el resto se
convierte a esa zona. La hora de pared original nunca se altera.

Los valores devueltos usan un **desfase fijo** (``timezone(offset)``) y no
``ZoneInfo``: Python compara y resta por hora de pared cuando dos fechas
comparten el mismo ``tzinfo``, lo que da resultados erróneos en la hora que se
repite al terminar el horario de verano. Con desfase fijo, orden, resta y
hash siguen el instante real. Para mostrar, usar ``to_santiago``.
"""

import re
from datetime import UTC, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

SANTIAGO = ZoneInfo("America/Santiago")

# Formato que escribe Android/Firestore: fecha, hora con segundos, fracción y
# zona opcionales. No se aceptan fechas sin hora ni formatos básicos.
_ISO_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|[+-]\d{2}:\d{2})?")

WallClockIssue = Literal["ambiguous", "nonexistent"]


def _parse_iso(value: object) -> datetime:
    if not isinstance(value, str) or not _ISO_FORMAT.fullmatch(value.strip()):
        raise ValueError(f"Fecha inválida: {value!r}")
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"Fecha inválida: {value!r}") from exc


def parse_timestamp(value: object) -> datetime:
    """Devuelve un ``datetime`` con la hora de pared de Santiago y desfase fijo.

    Lanza ``ValueError`` si ``value`` no es un texto ISO 8601 válido o está
    fuera del rango representable. Nunca inventa una fecha de reemplazo.
    """
    parsed = _parse_iso(value)
    try:
        local = (
            parsed.replace(tzinfo=SANTIAGO)
            if parsed.tzinfo is None
            else parsed.astimezone(SANTIAGO)
        )
        offset = local.utcoffset()
        return local.replace(tzinfo=timezone(offset))
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"Fecha fuera de rango: {value!r}") from exc


def to_santiago(moment: datetime) -> datetime:
    """Convierte a ``America/Santiago`` (solo para mostrar, no para comparar)."""
    return moment.astimezone(SANTIAGO)


def repeated_hour_pass(instant: datetime) -> int | None:
    """1 o 2 si la hora de pared de ``instant`` ocurrió dos veces (fin del horario de verano).

    ``None`` si esa hora de pared es única. Sirve para no confundir las dos pasadas de la misma
    hora en gráficos y tablas, que muestran la hora local de Chile.
    """
    local = instant.astimezone(SANTIAGO)
    naive = local.replace(tzinfo=None)
    first = naive.replace(tzinfo=SANTIAGO, fold=0)
    second = naive.replace(tzinfo=SANTIAGO, fold=1)
    if first.utcoffset() == second.utcoffset():
        return None
    return local.fold + 1


def wall_clock_issue(value: str) -> WallClockIssue | None:
    """Detecta horas locales sin zona que no identifican un único instante.

    * ``"ambiguous"``: la hora ocurrió dos veces (fin del horario de verano).
    * ``"nonexistent"``: la hora no existió (inicio del horario de verano).
    """
    parsed = _parse_iso(value)
    if parsed.tzinfo is not None:
        return None
    first = parsed.replace(tzinfo=SANTIAGO, fold=0)
    second = parsed.replace(tzinfo=SANTIAGO, fold=1)
    if first.utcoffset() == second.utcoffset():
        return None
    roundtrip = first.astimezone(UTC).astimezone(SANTIAGO).replace(tzinfo=None)
    return "nonexistent" if roundtrip != parsed else "ambiguous"
