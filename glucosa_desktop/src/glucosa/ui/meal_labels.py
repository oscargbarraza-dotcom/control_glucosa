"""Textos de la interfaz de Alimentación (sin Streamlit ni Plotly, para poder probarlos).

Rotulan siempre la fuente y distinguen estados que no deben confundirse: «sin medición manual
registrada», «sin datos del sensor», «export fuera de cobertura», «hueco del sensor» y «hito
pendiente». Para las mediciones de Firebase se separan además tres situaciones: «Fuente no
disponible» (la lectura falló), «Sin mediciones en Firebase» (la colección está vacía) y «Sin
medición … registrada» (hay mediciones, pero ninguna cerca). Nunca hablan de cumplimiento de
recordatorios ni de causalidad.
"""

from enum import StrEnum

from glucosa.analytics.meal_glucose import Window
from glucosa.analytics.meal_milestones import MilestoneResult, MilestoneStatus
from glucosa.analytics.meal_readings import ReadingSource
from glucosa.ui.glucose_sources import SourceStatus

SOURCE_NAMES: dict[ReadingSource, str] = {
    ReadingSource.MANUAL: "Manual (Firebase)",
    ReadingSource.IMPORTED: "Importada (Firebase)",
    ReadingSource.SENSOR: "Sensor (LibreView)",
    ReadingSource.SCAN: "Escaneo (LibreView)",
}
# Nombres cortos de leyenda (iguales a los del gráfico de Glucosa).
LEGEND_NAMES: dict[ReadingSource, str] = {
    ReadingSource.MANUAL: "Manual Firebase",
    ReadingSource.IMPORTED: "Importado Firebase",
    ReadingSource.SENSOR: "Sensor LibreView",
    ReadingSource.SCAN: "Escaneo LibreView",
}
WINDOW_LABELS: dict[Window, str] = {
    Window.PRE: "Previa (−60 a −5 min)",
    Window.AT: "Al comer (±5 min)",
    Window.POST: "Posterior (+5 a +180 min)",
}
MINUS = "−"

UNAVAILABLE_TEXT = "Fuente no disponible"
EMPTY_TEXT = "Sin mediciones en Firebase"
# Las mediciones manuales e importadas salen de la misma lectura de Firebase.
FIREBASE_SOURCES = frozenset({ReadingSource.MANUAL, ReadingSource.IMPORTED})


class FirebaseState(StrEnum):
    AVAILABLE = "available"  # la lectura funcionó y hay mediciones
    EMPTY = "empty"  # la lectura funcionó y la colección está vacía
    UNAVAILABLE = "unavailable"  # la lectura falló o no hay sesión: no se sabe si hay mediciones


def firebase_state(status: SourceStatus, record_count: int) -> FirebaseState:
    """Estado de la fuente de mediciones; si la lectura falló, los registros no cuentan."""
    if status is not SourceStatus.OK:
        return FirebaseState.UNAVAILABLE
    return FirebaseState.AVAILABLE if record_count else FirebaseState.EMPTY


SECONDS_PER_MINUTE = 60


def signed_minutes(value: float, digits: int = 0) -> str:
    """Desfase con signo: «+3 min», «−12 min»; bajo un minuto, en segundos («+24 s»); cero, «0 s».

    Un desfase distinto de cero nunca se muestra como «0»; el valor exacto vive en el modelo.
    """
    if value == 0:
        return "0 s"
    sign = "+" if value > 0 else MINUS
    seconds = round(abs(value) * SECONDS_PER_MINUTE)
    if seconds < SECONDS_PER_MINUTE:
        return f"{sign}{max(seconds, 1)} s"
    number = f"{round(abs(value), digits):.{digits}f}"
    if digits:
        number = number.rstrip("0").rstrip(".")
    return f"{sign}{number} min"


_NOT_REGISTERED = {
    ReadingSource.MANUAL: "Sin medición manual registrada",
    ReadingSource.IMPORTED: "Sin medición importada registrada",
}
STATUS_LABELS: dict[MilestoneStatus, str] = {
    MilestoneStatus.MEASURED: "Medición cercana",
    MilestoneStatus.NOT_REGISTERED: "Sin medición registrada",
    MilestoneStatus.NOT_APPLICABLE: "No aplica",
    MilestoneStatus.PENDING: "Hito pendiente",
    MilestoneStatus.NO_SENSOR_DATA: "Sin datos del sensor",
    MilestoneStatus.OUTSIDE_EXPORT: "Sin datos del sensor: export fuera de cobertura",
    MilestoneStatus.SENSOR_GAP: "Sin datos del sensor: hueco dentro del export",
}


def milestone_text(
    result: MilestoneResult, firebase: FirebaseState = FirebaseState.AVAILABLE
) -> str:
    """Texto de un hito: la lectura más cercana (valor y desfase) o el motivo de su ausencia.

    ``firebase`` solo afecta a las series de Firebase. Un hito pendiente es un hecho de tiempo y
    no depende de la fuente; el sensor tampoco depende de Firebase.
    """
    if result.source in FIREBASE_SOURCES and result.status is not MilestoneStatus.PENDING:
        if firebase is FirebaseState.UNAVAILABLE:
            return UNAVAILABLE_TEXT
        if firebase is FirebaseState.EMPTY and result.status is MilestoneStatus.NOT_REGISTERED:
            return EMPTY_TEXT
    if result.status is MilestoneStatus.MEASURED and result.reading is not None:
        value = result.reading.reading.value
        return f"{value} mg/dL ({signed_minutes(result.offset_minutes or 0, 0)} del hito)"
    if result.status is MilestoneStatus.NOT_REGISTERED:
        return _NOT_REGISTERED.get(result.source, STATUS_LABELS[result.status])
    return STATUS_LABELS[result.status]
