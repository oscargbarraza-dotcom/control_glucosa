"""Filtros de la página Alimentación (barra lateral de Streamlit).

Qué afecta cada filtro (se indica también en la propia interfaz):

* **Período**, **Tipo** y **Alimento**: definen la POBLACIÓN de comidas; alimentan los indicadores,
  los gráficos, el selector y la tabla.
* **Fuente de glucosa**: qué mediciones se muestran y se cuentan en el gráfico y la tabla.
* **Disponibilidad** y **Solo comidas aisladas**: filtros de VISUALIZACIÓN; acotan el selector y la
  tabla, nunca los indicadores.
* **Tolerancia de los hitos**: entero de 5 a 20 minutos alrededor de +60 y +90.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import streamlit as st

from glucosa.analytics.glucose_filters import CUSTOM, PERIOD_OPTIONS, Period, resolve_period
from glucosa.analytics.meal_dashboard import AVAILABILITY_LABELS, AvailabilityFilter
from glucosa.analytics.meal_milestones import (
    DEFAULT_TOLERANCE_MINUTES,
    MAX_TOLERANCE_MINUTES,
    MIN_TOLERANCE_MINUTES,
)
from glucosa.analytics.meal_readings import SERIES_SOURCES, ReadingSource
from glucosa.analytics.meal_view import NO_TYPE_LABEL, TYPE_LABELS
from glucosa.data.timeutil import SANTIAGO
from glucosa.models.records import MealType
from glucosa.ui.meal_labels import SOURCE_NAMES

DEFAULT_PERIOD = "Últimos 30 días"


@dataclass(frozen=True)
class MealFilterState:
    period: Period
    types: frozenset[MealType | None] | None  # None = todos; None dentro = tipo desconocido
    foods: frozenset[str] | None  # nombres normalizados; None = todos
    sources: frozenset[ReadingSource]  # series de glucosa visibles
    availability: AvailabilityFilter
    isolated_only: bool
    tolerance_minutes: int
    show_scans: bool


def _custom_dates(today: date) -> tuple[date, date] | None:
    chosen = st.date_input(
        "Fechas (inicio y fin)",
        value=(today - timedelta(days=6), today),
        max_value=today,
        format="DD/MM/YYYY",
        key="alimentacion_fechas",
    )
    if isinstance(chosen, tuple) and len(chosen) == 2:
        return chosen
    st.sidebar.info("Elige también la fecha de fin.")
    return None


def _type_options() -> dict[str, MealType | None]:
    options: dict[str, MealType | None] = {TYPE_LABELS[kind]: kind for kind in MealType}
    options[NO_TYPE_LABEL] = None
    return options


def _source_options(has_imported: bool) -> dict[str, ReadingSource]:
    return {
        SOURCE_NAMES[source]: source
        for source in SERIES_SOURCES
        if source is not ReadingSource.IMPORTED or has_imported
    }


def render_meal_filters(
    food_names: Mapping[str, str],
    has_imported: bool,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MealFilterState | None:
    """Dibuja los filtros y devuelve su estado; ``None`` si falta algún dato obligatorio.

    ``food_names`` mapea el nombre normalizado de cada alimento a cómo se escribe habitualmente.
    """
    current = now()
    today = current.astimezone(SANTIAGO).date()
    with st.sidebar:
        st.subheader("Filtros · Alimentación")
        option = st.selectbox(
            "Período",
            PERIOD_OPTIONS,
            index=PERIOD_OPTIONS.index(DEFAULT_PERIOD),
            key="alimentacion_periodo",
        )
        custom = _custom_dates(today) if option == CUSTOM else (None, None)
        if option == CUSTOM and custom is None:
            return None
        type_options = _type_options()
        chosen_types = st.multiselect(
            "Tipo de comida",
            list(type_options),
            default=list(type_options),
            key="alimentacion_tipos",
        )
        chosen_foods = st.multiselect(
            "Alimento (contiene alguno)",
            list(food_names),
            format_func=lambda key: food_names[key],
            placeholder="Todos los alimentos",
            key="alimentacion_alimentos",
        )
        source_options = _source_options(has_imported)
        chosen_sources = st.multiselect(
            "Fuente de glucosa",
            list(source_options),
            default=list(source_options),
            key="alimentacion_fuentes",
        )
        st.caption("Visualización (tabla y selector; los indicadores no cambian)")
        availability = st.selectbox(
            "Disponibilidad de glucosa",
            list(AVAILABILITY_LABELS),
            format_func=AVAILABILITY_LABELS.__getitem__,
            key="alimentacion_disponibilidad",
        )
        isolated_only = st.checkbox(
            "Solo comidas aisladas (sin otra comida cerca)", False, key="alimentacion_aisladas"
        )
        tolerance = st.number_input(
            "Tolerancia de los hitos (± min)",
            MIN_TOLERANCE_MINUTES,
            MAX_TOLERANCE_MINUTES,
            DEFAULT_TOLERANCE_MINUTES,
            step=1,
            key="alimentacion_tolerancia",
        )
        show_scans = st.checkbox(
            "Mostrar escaneos del sensor (gráfico y tabla)", False, key="alimentacion_escaneos"
        )

    try:
        period = resolve_period(option, current, custom[0], custom[1])
    except ValueError as exc:
        st.error(str(exc))
        return None
    types = {type_options[label] for label in chosen_types}
    return MealFilterState(
        period=period,
        types=None if len(types) == len(type_options) else frozenset(types),
        foods=frozenset(chosen_foods) if chosen_foods else None,
        sources=frozenset(source_options[label] for label in chosen_sources),
        availability=availability,
        isolated_only=isolated_only,
        tolerance_minutes=int(tolerance),
        show_scans=show_scans,
    )
