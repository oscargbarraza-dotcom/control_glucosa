"""Tablas de Alimentación (pandas, sin Streamlit): comidas con sus mediciones cercanas y el detalle
de las lecturas de una comida.

Todas las comidas se muestran, incluidas las que no tienen datos de glucosa (con el motivo). Las
columnas se rotulan por fuente y no se mezclan. Nada de lo que aquí se dice implica cumplimiento de
recordatorios ni causalidad.
"""

from collections.abc import Collection, Mapping, Sequence

import pandas as pd

from glucosa.analytics.meal_glucose import (
    WINDOW_ORDER,
    MealAssociation,
    MealGlucose,
    Window,
    availability_label,
)
from glucosa.analytics.meal_readings import ReadingSource, WindowReading
from glucosa.analytics.meal_view import MealView
from glucosa.data.timeutil import to_santiago
from glucosa.ui.meal_labels import (
    EMPTY_TEXT,
    FIREBASE_SOURCES,
    SOURCE_NAMES,
    UNAVAILABLE_TEXT,
    WINDOW_LABELS,
    FirebaseState,
    milestone_text,
    signed_minutes,
)

NONE_TEXT = "—"
# Tabla de detalle: fecha, tipo y alimentos quedan fijos y el resto conserva un ancho legible
# (si no caben, la tabla se desplaza en horizontal; no se quita ninguna columna). Streamlit
# desancla TODAS las columnas fijas si suman más del ~60 % del ancho de la tabla (≈ 715 px a
# 760 px de ventana); por eso el conjunto fijo se mantiene bajo el ~55 % de ese ancho.
PINNED_COLUMNS = ("Fecha y hora", "Tipo", "Alimentos")
PINNED_BUDGET_PX = 393  # 55 % de los ~715 px de la tabla a 760 px de ventana
_DEFAULT_WIDTH = 200
_FIXED_WIDTHS = {
    "Fecha y hora": 120,
    "Tipo": 108,
    "Alimentos": 160,
    "Datos de glucosa": 250,
    "Sensor posterior (cobertura)": 330,
    "Ventanas": 420,
}
_PREFIX_WIDTHS = (("Previa", 170), ("Referencia", 320))
_MILESTONE_WIDTH = 250
_SENSOR_MILESTONE_WIDTH = 350
SERIES = (ReadingSource.MANUAL, ReadingSource.IMPORTED, ReadingSource.SENSOR)
_SHORT = {
    ReadingSource.MANUAL: "manual",
    ReadingSource.IMPORTED: "importada",
    ReadingSource.SENSOR: "sensor",
}


def _state_text(source: ReadingSource, firebase: FirebaseState) -> str | None:
    """Texto que reemplaza a cualquier valor de Firebase cuando la fuente no permite afirmarlo."""
    if source in FIREBASE_SOURCES:
        if firebase is FirebaseState.UNAVAILABLE:
            return UNAVAILABLE_TEXT
        if firebase is FirebaseState.EMPTY:
            return EMPTY_TEXT
    return None


def _reading_text(item: WindowReading | None) -> str:
    if item is None:
        return NONE_TEXT
    return f"{item.reading.value} mg/dL ({signed_minutes(item.delta_minutes, 0)})"


def _reference_text(outcome: MealGlucose, source: ReadingSource) -> str:
    reference = outcome.reference.get(source)
    if reference is None:
        return NONE_TEXT
    text = _reading_text(reference.reading)
    # Una referencia posterior al registro nunca se presenta como previa.
    return f"{text} · posterior al registro" if reference.after_record else text


def sharing_text(outcome: MealGlucose) -> str:
    notes = []
    if outcome.near_simultaneous:
        notes.append("Casi simultánea con otra comida")
    if outcome.neighbors:
        names = ", ".join(
            f"{n.type_label} {signed_minutes(n.minutes, 0)}" for n in outcome.neighbors
        )
        notes.append(f"Ventana compartida con: {names}")
    elif outcome.overlapping:
        notes.append("Sus ventanas se tocan con otra comida")
    crossed = sorted(minutes for minutes, others in outcome.crossed_milestones.items() if others)
    if crossed:
        notes.append("Hito cruzado: " + ", ".join(f"+{m}" for m in crossed))
    if outcome.shared_reading_ids:
        notes.append(f"{len(outcome.shared_reading_ids)} lectura(s) compartida(s)")
    return " · ".join(notes) if notes else "Aislada"


def _availability_text(
    outcome: MealGlucose,
    selected: Collection[ReadingSource],
    firebase: FirebaseState = FirebaseState.AVAILABLE,
) -> str:
    """Disponibilidad de glucosa; sin Firebase nunca se afirma «sin mediciones» ni se cuenta 0."""
    sources = [
        s for s in selected if not (s in FIREBASE_SOURCES and firebase is FirebaseState.UNAVAILABLE)
    ]
    down = len(sources) < len(selected)
    present = [
        w for w in (Window.PRE, Window.POST) if any(outcome.summary(w, s).n for s in sources)
    ]
    if not any(
        outcome.any_readings[w] and any(outcome.summary(w, s).n for s in sources)
        for w in WINDOW_ORDER
    ):
        return UNAVAILABLE_TEXT if down else "Sin mediciones cercanas de las fuentes elegidas"
    labels = {Window.PRE: "previa", Window.POST: "posterior"}
    have = [labels[w] for w in present] or ["solo al comer"]
    return "Con " + " y ".join(have) + (" · sin Firebase" if down else "")


def milestones_table(
    outcome: MealGlucose,
    sources: Collection[ReadingSource],
    *,
    has_imported: bool,
    firebase: FirebaseState = FirebaseState.AVAILABLE,
) -> pd.DataFrame:
    """Los hitos +60 y +90 de una comida: una columna por fuente, con la tolerancia usada."""
    rows = []
    for minutes, by_source in sorted(outcome.milestones.items()):
        row: dict[str, object] = {"Hito": f"+{minutes} min"}
        for source in SERIES:
            if source in sources and (source is not ReadingSource.IMPORTED or has_imported):
                row[SOURCE_NAMES[source]] = milestone_text(by_source[source], firebase)
        tolerance = next(iter(by_source.values())).tolerance_minutes
        row["Tolerancia"] = f"±{tolerance} min"
        rows.append(row)
    return pd.DataFrame(rows)


def column_width(name: str) -> int:
    """Ancho en píxeles de una columna de la tabla de comidas."""
    if name in _FIXED_WIDTHS:
        return _FIXED_WIDTHS[name]
    for prefix, width in _PREFIX_WIDTHS:
        if name.startswith(prefix):
            return width
    if name.startswith(("+60", "+90")):
        return _SENSOR_MILESTONE_WIDTH if "(sensor)" in name else _MILESTONE_WIDTH
    return _DEFAULT_WIDTH


def meals_table(
    outcomes: Sequence[MealGlucose],
    meals: Mapping[str, MealView],
    sources: Collection[ReadingSource],
    *,
    has_imported: bool,
    firebase: FirebaseState = FirebaseState.AVAILABLE,
) -> pd.DataFrame:
    """Una fila por comida, de la más reciente a la más antigua."""
    rows = []
    for outcome in sorted(outcomes, key=lambda o: o.eaten_at, reverse=True):
        meal = meals[outcome.uuid]
        row: dict[str, object] = {
            "Fecha y hora": to_santiago(meal.eaten_at).replace(tzinfo=None),
            "Tipo": meal.type_label,
            "Alimentos": ", ".join(" ".join(i.name.split()) for i in meal.items) or NONE_TEXT,
            "Datos de glucosa": _availability_text(outcome, sources, firebase),
        }
        for source in SERIES:
            if source not in sources or (source is ReadingSource.IMPORTED and not has_imported):
                continue
            name = _SHORT[source]
            if source is not ReadingSource.SENSOR:
                masked = _state_text(source, firebase)
                row[f"Previa ({name})"] = masked or _reading_text(outcome.previous.get(source))
                row[f"Referencia ({name})"] = masked or _reference_text(outcome, source)
            row[f"+60 ({name})"] = milestone_text(outcome.milestones[60][source], firebase)
            row[f"+90 ({name})"] = milestone_text(outcome.milestones[90][source], firebase)
            if source is ReadingSource.SENSOR:
                row["Sensor posterior (cobertura)"] = availability_label(
                    outcome.summary(Window.POST, ReadingSource.SENSOR)
                )
        row["Ventanas"] = sharing_text(outcome)
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------- lecturas de una comida
def _notes(item: WindowReading, outcome: MealGlucose, association: MealAssociation) -> str:
    reading = item.reading
    notes = []
    reference = outcome.reference.get(reading.source)
    if reference is not None and reference.reading.reading.id == reading.id:
        notes.append(
            "Referencia (posterior al registro)" if reference.after_record else "Referencia"
        )
    previous = outcome.previous.get(reading.source)
    if previous is not None and previous.reading.id == reading.id:
        notes.append("Glucosa previa")
    for minutes, by_source in outcome.milestones.items():
        result = by_source.get(reading.source)
        if result is not None and result.reading and result.reading.reading.id == reading.id:
            notes.append(f"Más cercana al hito +{minutes}")
    if association.equivalent_manual_of(reading.id) is not None:
        notes.append("Coincidencia probable con una medición manual")
    if reading.id in outcome.shared_reading_ids:
        notes.append("Compartida con otra comida")
    return " · ".join(notes)


def nearby_readings_table(
    outcome: MealGlucose,
    association: MealAssociation,
    sources: Collection[ReadingSource],
    *,
    show_scans: bool,
) -> pd.DataFrame:
    """Lecturas de las ventanas de una comida, en orden de tiempo y rotuladas por fuente."""
    rows = []
    for window in WINDOW_ORDER:
        found = [
            (source, item)
            for source in SERIES
            if source in sources
            for item in outcome.summary(window, source).readings
        ]
        if show_scans:
            found += [(ReadingSource.SCAN, item) for item in outcome.scans[window]]
        for source, item in found:
            rows.append(
                {
                    "Fuente": SOURCE_NAMES[source],
                    "Ventana": WINDOW_LABELS[window],
                    "Hora local": to_santiago(item.reading.instant).replace(tzinfo=None),
                    "Glucosa (mg/dL)": item.reading.value,
                    "Desfase": signed_minutes(item.delta_minutes, 1),
                    "Observaciones": _notes(item, outcome, association),
                }
            )
    columns = [
        "Fuente",
        "Ventana",
        "Hora local",
        "Glucosa (mg/dL)",
        "Desfase",
        "Observaciones",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    return frame.sort_values(["Hora local", "Fuente"], kind="stable").reset_index(drop=True)


def availability_table(
    association: MealAssociation, firebase: FirebaseState = FirebaseState.AVAILABLE
) -> pd.DataFrame:
    """Cobertura de glucosa por fuente; sin Firebase se omiten sus filas (no se muestran ceros)."""
    from glucosa.analytics.meal_glucose import coverage_counts

    rows = []
    for source, counts in coverage_counts(association).items():
        if source in FIREBASE_SOURCES and firebase is FirebaseState.UNAVAILABLE:
            continue
        rows.append(
            {
                "Fuente": SOURCE_NAMES[source],
                "Comidas": counts.meals,
                "Con previa": counts.with_pre,
                "Con posterior": counts.with_post,
                "Con ambas": counts.with_both,
                "Con referencia": counts.with_reference,
                "Estadísticos permitidos (previa)": counts.sufficient_pre,
                "Estadísticos permitidos (posterior)": counts.sufficient_post,
            }
        )
    return pd.DataFrame(rows)
