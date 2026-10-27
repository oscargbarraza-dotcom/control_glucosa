"""Tabla detallada del módulo Glucosa (pandas, sin Streamlit).

Muestra solo lo necesario: no expone UUID, identificadores de dispositivo ni números de serie.
"""

from collections.abc import Iterable

import pandas as pd

from glucosa.analytics.glucose_view import (
    BAND_LABELS,
    KIND_LABELS,
    SOURCE_LABELS,
    GlucosePoint,
    Source,
    classify,
)
from glucosa.data.timeutil import repeated_hour_pass, to_santiago

TABLE_COLUMNS = (
    "Fecha y hora",
    "Cambio de hora",
    "Glucosa (mg/dL)",
    "Fuente",
    "Tipo de registro",
    "Momento declarado",
    "Observaciones",
    "Clasificación",
)


def _repeated_hour_note(point: GlucosePoint) -> str:
    """La hora de pared de Chile se repite al terminar el horario de verano: se distingue."""
    turn = repeated_hour_pass(point.instant)
    return f"Hora repetida ({turn}.ª vez)" if turn else ""


def points_table(points: Iterable[GlucosePoint], low: int, high: int) -> pd.DataFrame:
    """Una fila por registro, de la más reciente a la más antigua, con la hora local de Chile."""
    ordered = sorted(points, key=lambda p: p.instant, reverse=True)
    rows = [
        {
            "Fecha y hora": to_santiago(p.instant).replace(tzinfo=None),
            "Cambio de hora": _repeated_hour_note(p),
            "Glucosa (mg/dL)": p.value,
            "Fuente": SOURCE_LABELS[p.source],
            "Tipo de registro": KIND_LABELS[p.kind],
            "Momento declarado": p.moment.label if p.source is Source.FIREBASE and p.moment else "",
            "Observaciones": p.comment or "",
            "Clasificación": BAND_LABELS[classify(p.value, low, high)],
        }
        for p in ordered
    ]
    return pd.DataFrame(rows, columns=list(TABLE_COLUMNS))
