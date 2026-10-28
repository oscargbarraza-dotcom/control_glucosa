"""Generador de CSV sintéticos con la estructura de una exportación de LibreView (español).

Nunca se usan datos reales: nombres, series y valores son inventados.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

HEADER: tuple[str, ...] = (
    "Dispositivo",
    "Número de serie",
    "Marca de hora del dispositivo",
    "Tipo de registro",
    "Historial de glucosa mg/dL",
    "Escanear glucosa mg/dL",
    "Insulina de acción rápida no numérica",
    "Insulina de acción rápida (unidades)",
    "Alimento no numérico",
    "Carbohidratos (gramos)",
    "Carbohidratos (porciones)",
    "Insulina de acción prolongada no numérica",
    "Insulina de acción prolongada (unidades)",
    "Notas",
    "Banda de glucosa mg/dL",
    "Cetona mmol/L",
    "Insulina para la hora de la comida (unidades)",
    "Insulina de corrección (unidades)",
    "Insulina de cambio de usuario (unidades)",
    "Cetona histórica mmol/L",
    "Escanear cetona mmol/L",
)
MODEL = "FreeStyle LibreLink"
SERIAL_A = "SERIE-SECRETA-A"
SERIAL_B = "SERIE-SECRETA-B"
PATIENT = "PACIENTE-PRIVADO"


def _blank() -> list[str]:
    return [""] * len(HEADER)


def row(
    kind: str,
    minute: str,
    value: object = "",
    serial: str = SERIAL_A,
    model: str = MODEL,
) -> list[str]:
    """Fila de datos. ``kind``: hist | scan | food | note | other; ``minute``: dd-mm-aaaa hh:mm."""
    cells = _blank()
    cells[0], cells[1], cells[2] = model, serial, minute
    text = str(value)
    if kind == "hist":
        cells[3], cells[4] = "0", text
    elif kind == "scan":
        cells[3], cells[5] = "1", text
    elif kind == "food":
        cells[3], cells[8] = "5", text or "ALIMENTO-PRIVADO"
    elif kind == "note":
        cells[3], cells[13] = "6", text or "NOTA-PRIVADA"
    elif kind == "other":
        cells[3], cells[7] = "2", text or "3"
    else:
        raise ValueError(kind)
    return cells


def build_csv(
    rows: Iterable[list[str]],
    *,
    metadata: bool = True,
    header: Iterable[str] = HEADER,
    newline: str = "\r\n",
    bom: bool = False,
) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator=newline)
    if metadata:
        writer.writerow(
            ["Datos de glucosa", "Generado el", "23-10-2026 10:00 UTC", "Generado por", PATIENT]
        )
    writer.writerow(list(header))
    for data_row in rows:
        writer.writerow(data_row)
    text = buffer.getvalue()
    return (("﻿" if bom else "") + text).encode("utf-8")


def minute_series(day: str, start_hour: int, count: int, step: int = 15, base: int = 120):
    """``count`` filas históricas cada ``step`` min desde ``start_hour`` del día ``day``."""
    rows = []
    for i in range(count):
        total = start_hour * 60 + i * step
        rows.append(row("hist", f"{day} {total // 60 % 24:02d}:{total % 60:02d}", base + i % 7))
    return rows
