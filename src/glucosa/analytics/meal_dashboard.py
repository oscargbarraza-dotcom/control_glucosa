"""Lógica pura de la página Alimentación (sin Streamlit): filtros de visualización y KPI de hitos.

Reutiliza D2 y D3 sin alterar sus reglas:

* Los filtros de **población** (período, tipo, alimento) se aplican antes, con ``filter_meals``.
* Los filtros de **visualización** de aquí (disponibilidad de glucosa y comidas aisladas) solo
  acotan la tabla y el selector: los KPI describen siempre la población.
* Los KPI de hitos son descriptivos («medición cercana a +60 / +90 min»); nunca hablan de
  cumplimiento de recordatorios. El denominador son las comidas **elegibles** (el hito ya ocurrió);
  las **pendientes** se informan aparte.
"""

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from glucosa.analytics.meal_glucose import MealAssociation, MealGlucose, Window
from glucosa.analytics.meal_milestones import MILESTONES, MilestoneStatus
from glucosa.analytics.meal_readings import ReadingSource


class AvailabilityFilter(StrEnum):
    ALL = "all"
    WITH_PRE = "with_pre"
    WITH_POST = "with_post"
    WITH_BOTH = "with_both"
    WITHOUT_PRE = "without_pre"
    WITHOUT_POST = "without_post"
    WITHOUT_ANY = "without_any"


AVAILABILITY_LABELS: dict[AvailabilityFilter, str] = {
    AvailabilityFilter.ALL: "Todas las comidas",
    AvailabilityFilter.WITH_PRE: "Con glucosa previa",
    AvailabilityFilter.WITH_POST: "Con glucosa posterior",
    AvailabilityFilter.WITH_BOTH: "Con previa y posterior",
    AvailabilityFilter.WITHOUT_PRE: "Sin glucosa previa",
    AvailabilityFilter.WITHOUT_POST: "Sin glucosa posterior",
    AvailabilityFilter.WITHOUT_ANY: "Sin ninguna medición cercana",
}


def has_readings(outcome: MealGlucose, window: Window, sources: Collection[ReadingSource]) -> bool:
    """¿Hay lecturas de alguna de las fuentes elegidas en esa ventana de la comida?"""
    return any(outcome.summary(window, source).n > 0 for source in sources)


def _matches(outcome: MealGlucose, choice: AvailabilityFilter, sources) -> bool:
    pre = has_readings(outcome, Window.PRE, sources)
    post = has_readings(outcome, Window.POST, sources)
    return {
        AvailabilityFilter.ALL: True,
        AvailabilityFilter.WITH_PRE: pre,
        AvailabilityFilter.WITH_POST: post,
        AvailabilityFilter.WITH_BOTH: pre and post,
        AvailabilityFilter.WITHOUT_PRE: not pre,
        AvailabilityFilter.WITHOUT_POST: not post,
        AvailabilityFilter.WITHOUT_ANY: not any(
            has_readings(outcome, window, sources) for window in Window
        ),
    }[choice]


def apply_visualization_filters(
    outcomes: Sequence[MealGlucose],
    availability: AvailabilityFilter,
    isolated_only: bool,
    sources: Collection[ReadingSource],
) -> list[MealGlucose]:
    """Filtros de visualización (tabla y selector); conservan el orden cronológico."""
    return [
        outcome
        for outcome in outcomes
        if _matches(outcome, availability, sources) and (outcome.isolated or not isolated_only)
    ]


@dataclass(frozen=True)
class MilestoneKpi:
    minutes: int
    tolerance_minutes: int
    eligible: int  # el hito ya ocurrió y la fuente aplica: medida + sin medición registrada
    measured: int  # con lectura cercana (±tolerancia)
    not_registered: int  # sin medición registrada cerca del hito
    pending: int  # el hito aún no ocurre: no cuenta como «sin medición»


def milestone_kpis(
    outcomes: Iterable[MealGlucose], source: ReadingSource = ReadingSource.MANUAL
) -> dict[int, MilestoneKpi]:
    """Conteos descriptivos por hito para una fuente, con denominadores separados."""
    rows = list(outcomes)
    kpis = {}
    for minutes in MILESTONES:
        results = [outcome.milestones[minutes][source] for outcome in rows]
        counted = [r for r in results if r.status is not MilestoneStatus.NOT_APPLICABLE]
        pending = sum(r.status is MilestoneStatus.PENDING for r in counted)
        measured = sum(r.status is MilestoneStatus.MEASURED for r in counted)
        kpis[minutes] = MilestoneKpi(
            minutes=minutes,
            tolerance_minutes=results[0].tolerance_minutes if results else 0,
            eligible=len(counted) - pending,
            measured=measured,
            not_registered=sum(r.status is MilestoneStatus.NOT_REGISTERED for r in counted),
            pending=pending,
        )
    return kpis


def select_association(association: MealAssociation, uuids: Collection[str]) -> MealAssociation:
    """Subconjunto de comidas conservando todo lo demás (la vecindad ya se calculó con todas)."""
    wanted = set(uuids)
    return replace(association, meals=tuple(m for m in association.meals if m.uuid in wanted))
