"""Tarjetas de los hitos +60 y +90 de Alimentación (sin Streamlit, para poder probarlas).

Cada hito es un grupo de tres tarjetas —con medición, elegibles y pendientes— que nunca se mezclan.
Las etiquetas son cortas para no truncarse; la explicación va en la ayuda de cada tarjeta. Los
grupos se reparten en la misma fila si caben y se apilan en ventanas angostas.
"""

from collections.abc import Mapping, Sequence

from glucosa.analytics.meal_dashboard import MilestoneKpi
from glucosa.analytics.meal_readings import ReadingSource
from glucosa.ui.glucose_kpi import Kpi, Tone, kpi_grid_html

# Etiquetas por fuente: (con medición, elegibles, pendientes). La manual es la principal.
_LABELS = {
    ReadingSource.MANUAL: ("Manual", "Elegibles", "Pendientes"),
    ReadingSource.IMPORTED: ("Importada", "Eleg. imp.", "Pend. imp."),
}
_SOURCE_TEXT = {ReadingSource.MANUAL: "manual", ReadingSource.IMPORTED: "importada"}

MILESTONE_CSS = """
<style>
.meal-hitos { display: grid; gap: 0.5rem;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr)); }
.meal-hitos .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
</style>
"""


def _group(source: ReadingSource, kpi: MilestoneKpi) -> list[Kpi]:
    measured, eligible, pending = _LABELS[source]
    text = _SOURCE_TEXT[source]
    return [
        Kpi(
            f"{measured} +{kpi.minutes}",
            f"{kpi.measured} de {kpi.eligible}",
            "",
            f"Comidas con una medición {text} dentro de ±{kpi.tolerance_minutes} min de "
            f"+{kpi.minutes}, de las elegibles · {kpi.not_registered} sin medición registrada",
        ),
        Kpi(f"{eligible} +{kpi.minutes}", str(kpi.eligible), "", "Comidas cuyo hito ya ocurrió"),
        Kpi(
            f"{pending} +{kpi.minutes}",
            str(kpi.pending),
            "",
            "Comidas cuyo hito aún no ocurre: no cuentan como sin medición",
        ),
    ]


def milestone_groups(
    by_source: Mapping[ReadingSource, Mapping[int, MilestoneKpi]],
) -> list[list[Kpi]]:
    """Un grupo por fuente y por hito, manual primero."""
    return [
        _group(source, by_source[source][minutes])
        for source in _LABELS
        if source in by_source
        for minutes in sorted(by_source[source])
    ]


def milestone_groups_html(groups: Sequence[Sequence[Kpi]], tone: Tone) -> str:
    inner = "".join(kpi_grid_html(list(group), tone) for group in groups)
    return f'{MILESTONE_CSS}<div class="meal-hitos">{inner}</div>'
