"""Página «Alimentación» de Streamlit: presentación y orquestación (la lógica va en analytics/).

* Las comidas vienen de Firebase (solo lectura) y la glucosa de las mismas fuentes que la página
  Glucosa, con la misma caché y sin escribir nada.
* Las fuentes de glucosa se distinguen siempre: manual, importada y sensor. Una medición manual
  suelta nunca se une a otras en una serie continua.
* Todo es descriptivo: la cercanía temporal de una medición a +60 o +90 minutos no indica
  cumplimiento de recordatorios, y no se atribuye ningún efecto de un alimento sobre la glucosa.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

import streamlit as st

from glucosa.analytics.meal_dashboard import (
    apply_visualization_filters,
    milestone_kpis,
    select_association,
)
from glucosa.analytics.meal_glucose import (
    AssociationParams,
    MealAssociation,
    MealGlucose,
    associate_meals,
    export_notice,
)
from glucosa.analytics.meal_milestones import MilestoneParams
from glucosa.analytics.meal_readings import (
    GlucoseInputs,
    HistoryReadings,
    ReadingSource,
    readings_from_history,
    readings_from_records,
)
from glucosa.analytics.meal_summaries import (
    food_diversity,
    food_ranking,
    hour_histogram,
    meals_by_day,
    per_day_indicators,
    summarize_meals,
    type_counts,
)
from glucosa.analytics.meal_view import MealView, filter_meals, meal_views
from glucosa.data.timeutil import to_santiago
from glucosa.models.records import Origin
from glucosa.ui.glucose_charts import EVOLUTION_CONFIG, PLOT_CONFIG
from glucosa.ui.glucose_kpi import Kpi, Tone, kpi_grid_html
from glucosa.ui.glucose_page import (
    _FIREBASE_STATE,
    _LIBRE_STATE,
    ERROR_TTL_SECONDS,
    MANUAL_TTL_SECONDS,
    LibreData,
    _fmt,
    _load_libre,
    _load_manual,
    _source_chip,
)
from glucosa.ui.glucose_sources import GlucoseSources, LibreLoad, ManualLoad, MealLoad, SourceStatus
from glucosa.ui.glucose_style import inject_compact_style
from glucosa.ui.meal_charts import (
    daily_figure,
    hours_figure,
    meal_window_figure,
    ranking_figure,
    type_figure,
)
from glucosa.ui.meal_filters_ui import MealFilterState, render_meal_filters
from glucosa.ui.meal_kpi import milestone_groups, milestone_groups_html
from glucosa.ui.meal_table import (
    PINNED_COLUMNS,
    availability_table,
    column_width,
    meals_table,
    milestones_table,
    nearby_readings_table,
    sharing_text,
)

_MEALS_KEY = "alimentacion_cache_meals"
_SELECTOR_KEY = "alimentacion_comida"
_UNCACHED = frozenset({SourceStatus.NO_SESSION, SourceStatus.SESSION_EXPIRED, SourceStatus.CONFIG})
_SESSION_STATES = (SourceStatus.NO_SESSION, SourceStatus.SESSION_EXPIRED)
SELECTOR_FOODS_CHARS = 40
DISCLAIMER = (
    "Descriptivo: una medición cercana a +60 o +90 minutos no indica cumplimiento de recordatorios "
    "y no se atribuye ningún efecto de un alimento sobre la glucosa."
)


class MealPageSources(GlucoseSources, Protocol):
    def load_meals(self) -> MealLoad: ...


# ----------------------------------------------------------------- carga + caché
def _meals_ttl(status: SourceStatus) -> float | None:
    if status is SourceStatus.OK:
        return MANUAL_TTL_SECONDS
    return None if status in _UNCACHED else ERROR_TTL_SECONDS


def _load_meals(sources: MealPageSources, force: bool) -> MealLoad:
    marker = sources.session_marker()
    entry = st.session_state.get(_MEALS_KEY)
    if entry and not force:
        stored_at, result, stored_marker, ttl = entry
        if stored_marker == marker and time.monotonic() - stored_at < ttl:
            return result
    with st.spinner("Leyendo comidas de Firebase…"):
        result = sources.load_meals()
    ttl = _meals_ttl(result.status)
    if ttl is None:
        st.session_state.pop(_MEALS_KEY, None)
    else:
        st.session_state[_MEALS_KEY] = (time.monotonic(), result, marker, ttl)
    return result


def _memo(key: str, deps: tuple, build: Callable):
    """Guarda el último resultado mientras no cambien sus dependencias (comparadas por valor)."""
    entry = st.session_state.get(key)
    if entry is not None and entry[0] == deps:
        return entry[1]
    value = build()
    st.session_state[key] = (deps, value)
    return value


def _history(libre: LibreData) -> HistoryReadings:
    return _memo(
        "alimentacion_cache_historial",
        (libre.load,),
        lambda: readings_from_history(
            libre.load.readings if libre.load.status is SourceStatus.OK else ()
        ),
    )


def _glucose_inputs(manual: ManualLoad, history: HistoryReadings) -> GlucoseInputs:
    records = manual.records if manual.status is SourceStatus.OK else ()
    readings = [*readings_from_records(records), *history.sensor, *history.scans]
    return GlucoseInputs.of(readings, export_span=history.span)


def _association(
    views: list[MealView], inputs: GlucoseInputs, filters: MealFilterState, current: datetime
) -> MealAssociation:
    params = AssociationParams(milestones=MilestoneParams(filters.tolerance_minutes))
    return associate_meals(views, inputs, current, params)


# --------------------------------------------------------------------- mensajes
def _status_line(
    filters: MealFilterState | None, meals: MealLoad, manual: ManualLoad, libre
) -> str:
    parts = []
    if filters is not None:
        period = filters.period
        parts.append(
            f"**Período:** {period.label} · "
            f"{period.first_day:%d-%m-%Y} → {period.last_day:%d-%m-%Y}"
        )
    when = (
        f" · consulta {_fmt(meals.fetched_at)}"
        if meals.status is SourceStatus.OK and meals.fetched_at
        else ""
    )
    parts.append(_source_chip("Comidas · Firebase", "violet", _FIREBASE_STATE[meals.status], when))
    parts.append(
        _source_chip("Mediciones · Firebase", "violet", _FIREBASE_STATE[manual.status], "")
    )
    last_import = libre.stats.last_import_utc if libre.stats is not None else None
    detail = f" · importación {_fmt(last_import)}" if last_import else ""
    parts.append(_source_chip("LibreView", "blue", _LIBRE_STATE[libre.status], detail))
    return "  │  ".join(parts)


def _messages(meals: MealLoad, manual: ManualLoad, libre: LibreLoad) -> None:
    if meals.status is not SourceStatus.OK:
        icon = "🔒" if meals.status in _SESSION_STATES else "⚠️"
        st.warning(f"Firebase (comidas): {meals.message}", icon=icon)
    else:
        if meals.rejected:
            st.warning(
                f"{meals.rejected} documento(s) de comidas no pasaron la validación y se omitieron."
            )
        if meals.warnings:
            st.caption(f"{meals.warnings} comida(s) con avisos de validación (se conservan).")
    if manual.status not in (SourceStatus.OK, *_SESSION_STATES):
        st.warning(f"Firebase (mediciones): {manual.message}", icon="⚠️")
    if libre.status is SourceStatus.ERROR:
        st.error(f"LibreView: {libre.message}")


def _export_message(association: MealAssociation, filters: MealFilterState) -> None:
    if ReadingSource.SENSOR not in filters.sources or not association.meals:
        return
    notice = export_notice(association)
    if not notice.has_export:
        st.info("Sin datos de LibreView: no se pueden evaluar las ventanas del sensor.")
    elif notice.needs_attention:
        st.info(
            f"El export de LibreView termina el {_fmt(notice.export_end)}: "
            f"{notice.meals_after_export} comida(s) son posteriores y "
            f"{notice.meals_crossing_export_end} cruzan su final. Eso es un export desactualizado, "
            "no un hueco del sensor."
        )


# ------------------------------------------------------------------------- KPI
def _kpis(
    population: list[MealView],
    in_population: MealAssociation,
    filters: MealFilterState,
    has_imported: bool,
) -> None:
    summary = summarize_meals(population, filters.period)
    primary = next(i for i in per_day_indicators(summary) if i.primary)
    per_day = "—" if primary.value is None else f"{primary.value:.1f}"
    st.html(
        kpi_grid_html(
            [
                Kpi("Comidas", str(summary.meals)),
                Kpi(
                    "Días registrados",
                    str(summary.days_with_records),
                    "",
                    f"de {summary.days_in_period} día(s) del período",
                ),
                Kpi("Promedio por día", per_day, "", primary.label),
                Kpi("Alimentos distintos", str(food_diversity(population).distinct_foods)),
            ],
            Tone.FIREBASE,
        )
    )
    by_source = {
        source: milestone_kpis(in_population.meals, source)
        for source in (ReadingSource.MANUAL, ReadingSource.IMPORTED)
        if source in filters.sources and (source is ReadingSource.MANUAL or has_imported)
    }
    groups = milestone_groups(by_source)
    if groups:
        st.html(milestone_groups_html(groups, Tone.FIREBASE))
        st.caption(
            "Manual +60 / +90 = comidas con una medición manual dentro de la tolerancia, de las "
            "elegibles (cuyo hito ya ocurrió); las pendientes se informan aparte. " + DISCLAIMER
        )


# -------------------------------------------------------------------- gráficos
def _distributions(population: list[MealView], filters: MealFilterState) -> None:
    left, right = st.columns(2, gap="medium")
    left.plotly_chart(
        type_figure(type_counts(population)),
        width="stretch",
        key="alimentacion_tipos_fig",
        config=PLOT_CONFIG,
    )
    right.plotly_chart(
        hours_figure(hour_histogram(population)),
        width="stretch",
        key="alimentacion_horas_fig",
        config=PLOT_CONFIG,
    )
    left, right = st.columns(2, gap="medium")
    ranking = ranking_figure(food_ranking(population))
    if ranking is None:
        left.info("Sin alimentos registrados en estas comidas.")
    else:
        left.plotly_chart(
            ranking, width="stretch", key="alimentacion_ranking_fig", config=PLOT_CONFIG
        )
    right.plotly_chart(
        daily_figure(meals_by_day(population, filters.period)),
        width="stretch",
        key="alimentacion_diaria_fig",
        config=PLOT_CONFIG,
    )


# ------------------------------------------------------------- comida individual
def _meal_label(view: MealView) -> str:
    when = to_santiago(view.eaten_at).strftime("%d-%m-%Y %H:%M")
    foods = ", ".join(" ".join(item.name.split()) for item in view.items)
    if len(foods) > SELECTOR_FOODS_CHARS:
        foods = foods[: SELECTOR_FOODS_CHARS - 1] + "…"
    return f"{when} · {view.type_label}" + (f" · {foods}" if foods else "")


def _select_meal(
    visible: list[MealGlucose], views: dict[str, MealView]
) -> tuple[MealGlucose, MealView] | None:
    newest_first = sorted(visible, key=lambda outcome: outcome.eaten_at, reverse=True)
    options = [outcome.uuid for outcome in newest_first]
    if st.session_state.get(_SELECTOR_KEY) not in options:
        st.session_state.pop(_SELECTOR_KEY, None)  # la comida elegida ya no cumple los filtros
    chosen = st.selectbox(
        "Comida",
        options,
        format_func=lambda uuid: _meal_label(views[uuid]),
        key=_SELECTOR_KEY,
        label_visibility="collapsed",
    )
    if chosen is None:
        return None
    return next(o for o in newest_first if o.uuid == chosen), views[chosen]


def _meal_detail(
    visible: list[MealGlucose],
    association: MealAssociation,
    views: dict[str, MealView],
    filters: MealFilterState,
    has_imported: bool,
    target_range: tuple[int, int],
) -> None:
    st.subheader("Comida individual · glucosa de −60 a +180 min")
    if not visible:
        st.info("No hay comidas con los filtros de visualización elegidos.")
        return
    picked = _select_meal(visible, views)
    if picked is None:
        return
    outcome, view = picked
    items = "; ".join(f"{' '.join(i.name.split())} ({i.quantity})" for i in view.items)
    st.text(f"{view.type_label} · alimentos: {items or 'sin alimentos registrados'}")
    if view.comment:
        st.text(f"Comentario: {view.comment}")
    notes = sharing_text(outcome)
    if notes != "Aislada":
        st.warning(notes, icon="⚠️")
    st.plotly_chart(
        meal_window_figure(
            view,
            outcome,
            association,
            tolerance_minutes=filters.tolerance_minutes,
            sources=filters.sources,
            show_scans=filters.show_scans,
            target_range=target_range,
        ),
        width="stretch",
        key="alimentacion_comida_fig",
        config=EVOLUTION_CONFIG,
    )
    st.caption(
        "Diamantes = mediciones manuales (Firebase, sin unir) · diamantes huecos = importadas · "
        "línea azul = sensor (LibreView), cortada donde hay más de 30 min sin datos · bandas = "
        "tolerancia de los hitos +60 y +90. No se interpola ningún valor. " + DISCLAIMER
    )
    st.dataframe(
        milestones_table(outcome, filters.sources, has_imported=has_imported),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Mediciones cercanas de esta comida"):
        frame = nearby_readings_table(
            outcome, association, filters.sources, show_scans=filters.show_scans
        )
        if frame.empty:
            st.write("Esta comida no tiene mediciones en sus ventanas (−60 a +180 min).")
        else:
            st.dataframe(
                frame,
                hide_index=True,
                width="stretch",
                column_config={
                    "Hora local": st.column_config.DatetimeColumn(format="DD-MM-YYYY HH:mm"),
                },
            )


# ----------------------------------------------------------------------- tabla
def _detail_table(
    visible: list[MealGlucose],
    total: int,
    views: dict[str, MealView],
    filters: MealFilterState,
    has_imported: bool,
) -> None:
    st.subheader("Detalle de comidas y mediciones cercanas")
    frame = meals_table(visible, views, filters.sources, has_imported=has_imported)
    st.markdown(f"**Comidas mostradas: {len(visible)} de {total}** · hora local de Chile")
    if frame.empty:
        st.info("No hay comidas con los filtros de visualización elegidos.")
        return
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        height=460,
        column_config={name: _detail_column(name) for name in frame.columns},
    )


def _detail_column(name: str):
    width, pinned = column_width(name), name in PINNED_COLUMNS
    if name == "Fecha y hora":
        return st.column_config.DatetimeColumn(
            format="DD-MM-YYYY HH:mm", width=width, pinned=pinned
        )
    return st.column_config.TextColumn(width=width, pinned=pinned)


# ------------------------------------------------------------------ principal
def render_meal_page(
    sources: MealPageSources, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> None:
    inject_compact_style()
    refresh = st.sidebar.button("Actualizar datos de Firebase", key="alimentacion_actualizar")
    meals = _load_meals(sources, refresh)
    manual = _load_manual(sources, force=refresh)
    libre = _load_libre(sources)

    st.header("Alimentación")
    if meals.status is not SourceStatus.OK or not meals.records:
        st.markdown(_status_line(None, meals, manual, libre.load))
        _messages(meals, manual, libre.load)
        if meals.status is SourceStatus.OK:
            st.info("Aún no hay comidas sincronizadas desde la aplicación Android.")
        return

    views = meal_views(meals.records)
    by_uuid = {view.uuid: view for view in views}
    has_imported = any(r.origin is Origin.IMPORTED for r in manual.records)
    food_names = {rank.normalized: rank.display_name for rank in food_ranking(views)}
    filters = render_meal_filters(food_names, has_imported, now)
    st.markdown(_status_line(filters, meals, manual, libre.load))
    _messages(meals, manual, libre.load)
    if filters is None:
        return

    current = now()
    inputs = _memo(
        "alimentacion_cache_entradas",
        (manual, libre.load),
        lambda: _glucose_inputs(manual, _history(libre)),
    )
    association = _memo(
        "alimentacion_cache_asociacion",
        (
            meals,
            manual,
            libre.load,
            filters.tolerance_minutes,
            current.replace(second=0, microsecond=0),
        ),
        lambda: _association(views, inputs, filters, current),
    )
    population = filter_meals(views, filters.period, filters.types, filters.foods)
    in_population = select_association(association, {m.uuid for m in population})

    _kpis(population, in_population, filters, has_imported)
    _export_message(in_population, filters)
    if not population:
        st.info("No hay comidas con los filtros elegidos.")
        return
    _distributions(population, filters)
    visible = apply_visualization_filters(
        in_population.meals, filters.availability, filters.isolated_only, filters.sources
    )
    target_range = sources.target_range()
    _meal_detail(visible, association, by_uuid, filters, has_imported, target_range)
    _detail_table(visible, len(in_population.meals), by_uuid, filters, has_imported)
    with st.expander("Cobertura de glucosa por fuente"):
        st.dataframe(availability_table(in_population), hide_index=True, width="stretch")
        st.caption(
            "Comidas con mediciones en la ventana previa (−60 a −5 min) y posterior "
            "(+5 a +180 min) por fuente. «Estadísticos permitidos» del sensor exige "
            "cobertura ≥ 70 %."
        )
