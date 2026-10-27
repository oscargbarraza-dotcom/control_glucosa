"""Tarjetas de los hitos +60 y +90 de Alimentación (sin Streamlit, para poder probarlas).

Cada hito es un grupo de tres tarjetas —con medición, elegibles y pendientes— que nunca se mezclan.
Las etiquetas son cortas para no truncarse; la explicación va en la ayuda de cada tarjeta. Los
grupos se reparten en la misma fila si caben y se apilan en ventanas angostas.

Si la fuente de Firebase no se pudo leer, o su colección está vacía, el grupo se reemplaza por una
sola tarjeta que lo dice: nunca se muestran ceros como si fueran un resultado válido.
"""

from collections.abc import Mapping, Sequence

from glucosa.analytics.meal_dashboard import MilestoneKpi
from glucosa.analytics.meal_readings import ReadingSource
from glucosa.ui.glucose_kpi import Kpi, Tone, kpi_grid_html
from glucosa.ui.meal_labels import EMPTY_TEXT, UNAVAILABLE_TEXT, FirebaseState

# Etiquetas por fuente: (con medición, elegibles, pendientes). La manual es la principal.
_LABELS = {
    ReadingSource.MANUAL: ("Manual", "Elegibles", "Pendientes"),
    ReadingSource.IMPORTED: ("Importada", "Eleg. imp.", "Pend. imp."),
}
_SOURCE_TEXT = {ReadingSource.MANUAL: "manual", ReadingSource.IMPORTED: "importada"}
NO_TOLERANCE = "—"  # sin comidas no hay hito evaluado: la tolerancia configurada no se muestra
SHARED_NOTE = "Una misma medición puede aparecer asociada a más de una comida cercana"

MILESTONE_CSS = """
<style>
.meal-hitos { display: grid; gap: 0.5rem;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr)); }
.meal-hitos .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.meal-hitos .kpi-grid.kpi-solo { grid-template-columns: minmax(0, 1fr); }
.meal-hitos .kpi-solo .kpi-value { font-size: 1.05rem; white-space: normal; }
</style>
"""


def _tolerance_text(kpi: MilestoneKpi) -> str:
    return f"±{kpi.tolerance_minutes} min" if kpi.tolerance_minutes else NO_TOLERANCE


def _group(source: ReadingSource, kpi: MilestoneKpi) -> list[Kpi]:
    measured, eligible, pending = _LABELS[source]
    text = _SOURCE_TEXT[source]
    return [
        Kpi(
            f"{measured} +{kpi.minutes}",
            f"{kpi.measured} de {kpi.eligible}",
            "",
            f"Comidas con una medición {text} cerca de +{kpi.minutes} (tolerancia: "
            f"{_tolerance_text(kpi)}), de las elegibles · {kpi.not_registered} sin medición "
            f"registrada. {SHARED_NOTE}.",
        ),
        Kpi(f"{eligible} +{kpi.minutes}", str(kpi.eligible), "", "Comidas cuyo hito ya ocurrió"),
        Kpi(
            f"{pending} +{kpi.minutes}",
            str(kpi.pending),
            "",
            "Comidas cuyo hito aún no ocurre: no cuentan como sin medición",
        ),
    ]


def _state_group(source: ReadingSource, minutes: int, firebase: FirebaseState) -> list[Kpi]:
    label = f"{_LABELS[source][0]} +{minutes}"
    if firebase is FirebaseState.UNAVAILABLE:
        tip = (
            "No se pudo leer la fuente de mediciones de Firebase: no se sabe si hay mediciones, "
            "así que no se muestran conteos."
        )
        return [Kpi(label, UNAVAILABLE_TEXT, "", tip)]
    tip = "La colección de mediciones de Firebase está vacía: aún no hay mediciones sincronizadas."
    return [Kpi(label, EMPTY_TEXT, "", tip)]


def milestone_groups(
    by_source: Mapping[ReadingSource, Mapping[int, MilestoneKpi]],
    firebase: FirebaseState = FirebaseState.AVAILABLE,
) -> list[list[Kpi]]:
    """Un grupo por fuente y por hito, manual primero."""
    groups = []
    for source in _LABELS:
        if source not in by_source:
            continue
        for minutes in sorted(by_source[source]):
            if firebase is FirebaseState.AVAILABLE:
                groups.append(_group(source, by_source[source][minutes]))
            else:
                groups.append(_state_group(source, minutes, firebase))
    return groups


def milestone_groups_html(groups: Sequence[Sequence[Kpi]], tone: Tone) -> str:
    parts = []
    for group in groups:
        html = kpi_grid_html(list(group), tone)
        if len(group) == 1:  # una sola tarjeta (estado de la fuente): ocupa todo el ancho
            html = html.replace('class="kpi-grid ', 'class="kpi-grid kpi-solo ', 1)
        parts.append(html)
    return f'{MILESTONE_CSS}<div class="meal-hitos">{"".join(parts)}</div>'
