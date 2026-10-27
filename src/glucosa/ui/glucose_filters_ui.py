"""Filtros globales de la página Glucosa (barra lateral de Streamlit).

Qué afecta cada filtro (se indica también en la propia interfaz):

* **Período** y **Fuente**: todo (indicadores, gráfico y tabla).
* **Momento declarado**: solo registros de Firebase (el sensor no tiene momento). Incluye la opción
  «Sin momento declarado» para no ocultar en silencio esos registros.
* **Clasificación**: qué puntos se ven en el gráfico y la tabla. Los indicadores y el TIR describen
  siempre el período completo: filtrar por clasificación no debe alterar el tiempo en rango.
* **Escaneos**: un solo control para el gráfico y la tabla (apagado por defecto).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import streamlit as st

from glucosa.analytics.glucose_filters import CUSTOM, PERIOD_OPTIONS, Period, resolve_period
from glucosa.analytics.glucose_summaries import NO_MOMENT_LABEL
from glucosa.analytics.glucose_view import BAND_LABELS, Band, Source
from glucosa.data.timeutil import SANTIAGO
from glucosa.errors import GlucosaError
from glucosa.models.records import GlucoseMoment
from glucosa.ui.glucose_sources import GlucoseSources

DEFAULT_PERIOD = "Últimos 30 días"
SOURCE_CHOICES = ("Ambas", "Firebase (manual)", "LibreView (sensor)")
_SOURCE_MAP = {
    "Ambas": {Source.FIREBASE, Source.LIBREVIEW},
    "Firebase (manual)": {Source.FIREBASE},
    "LibreView (sensor)": {Source.LIBREVIEW},
}


@dataclass(frozen=True)
class FilterState:
    period: Period
    sources: frozenset[Source]
    moments: frozenset[GlucoseMoment | None] | None  # None = todos; None dentro = sin momento
    bands: frozenset[Band] | None  # None = todas
    low: int
    high: int
    show_scans: bool

    @property
    def revision_key(self) -> str:
        """Cambia con el período/fuente: el gráfico reinicia el zoom solo cuando corresponde."""
        sources = ",".join(sorted(s.value for s in self.sources))
        return f"{self.period.first_day}|{self.period.last_day}|{sources}"


def _custom_dates(today: date) -> tuple[date, date] | None:
    chosen = st.date_input(
        "Fechas (inicio y fin)",
        value=(today - timedelta(days=6), today),
        max_value=today,
        format="DD/MM/YYYY",
        key="glucosa_fechas",
    )
    if isinstance(chosen, tuple) and len(chosen) == 2:
        return chosen
    st.sidebar.info("Elige también la fecha de fin.")
    return None


_MOMENTS_KEY = "glucosa_momentos"


def _moment_options() -> dict[str, GlucoseMoment | None]:
    options: dict[str, GlucoseMoment | None] = {m.label: m for m in GlucoseMoment}
    options[NO_MOMENT_LABEL] = None
    return options


def _set_moments(labels: list[str]) -> None:
    st.session_state[_MOMENTS_KEY] = labels


def _selection_summary(selected: int, total: int) -> str:
    if selected == total:
        return "todos"
    return "ninguno" if selected == 0 else f"{selected} de {total}"


def _moment_filter(options: dict[str, GlucoseMoment | None]) -> list[str]:
    """Selector compacto: un botón con el resumen de la selección y la lista dentro de un menú."""
    labels = list(options)
    st.session_state.setdefault(_MOMENTS_KEY, labels)
    # Si cambiaran las opciones, se descarta lo que ya no existe.
    st.session_state[_MOMENTS_KEY] = [x for x in st.session_state[_MOMENTS_KEY] if x in options]
    summary = _selection_summary(len(st.session_state[_MOMENTS_KEY]), len(labels))
    with st.popover(f"Momento declarado: {summary}", width="stretch"):
        st.caption("Solo registros de Firebase (el sensor no tiene momento).")
        all_col, none_col = st.columns(2)
        all_col.button(
            "Seleccionar todos", key="glucosa_momentos_todos", on_click=_set_moments, args=(labels,)
        )
        none_col.button(
            "Limpiar selección", key="glucosa_momentos_ninguno", on_click=_set_moments, args=([],)
        )
        return st.multiselect(
            "Momento declarado", labels, key=_MOMENTS_KEY, label_visibility="collapsed"
        )


def _target_range_controls(sources: GlucoseSources) -> tuple[int, int]:
    info = sources.target_range_info()
    if info.notice:
        st.warning(info.notice, icon="⚠️")
    st.caption("Rango objetivo (mg/dL)")
    low_col, high_col = st.columns(2)
    low = low_col.number_input("Mínimo", 20, 599, info.low, key="glucosa_min")
    high = high_col.number_input("Máximo", 21, 600, info.high, key="glucosa_max")
    changed = (low, high) != (info.low, info.high) and low < high
    if changed and st.button("Guardar como predeterminado", key="glucosa_guardar_rango"):
        try:
            sources.save_target_range(int(low), int(high))
            st.success("Rango guardado.")
        except (ValueError, GlucosaError) as exc:
            st.error(str(exc))
    return int(low), int(high)


def render_filters(
    sources: GlucoseSources, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> FilterState | None:
    """Dibuja los filtros y devuelve su estado; ``None`` si falta algún dato obligatorio."""
    current = now()
    today = current.astimezone(SANTIAGO).date()
    with st.sidebar:
        st.subheader("Filtros · Glucosa")
        option = st.selectbox(
            "Período",
            PERIOD_OPTIONS,
            index=PERIOD_OPTIONS.index(DEFAULT_PERIOD),
            key="glucosa_periodo",
        )
        custom = _custom_dates(today) if option == CUSTOM else (None, None)
        if option == CUSTOM and custom is None:
            return None
        source_choice = st.radio("Fuente", SOURCE_CHOICES, key="glucosa_fuente")
        moment_options = _moment_options()
        chosen_moments = _moment_filter(moment_options)
        band_labels = {label: band for band, label in BAND_LABELS.items()}
        chosen_bands = st.multiselect(
            "Clasificación (gráfico y tabla)",
            list(band_labels),
            default=list(band_labels),
            key="glucosa_clasificacion",
        )
        low, high = _target_range_controls(sources)
        show_scans = st.checkbox(
            "Mostrar escaneos del sensor (gráfico y tabla)", False, key="glucosa_escaneos"
        )

    if low >= high:
        st.error("El mínimo del rango objetivo debe ser menor que el máximo.")
        return None
    try:
        period = resolve_period(option, current, custom[0], custom[1])
    except ValueError as exc:
        st.error(str(exc))
        return None
    moments = {moment_options[label] for label in chosen_moments}
    bands = {band_labels[label] for label in chosen_bands}
    return FilterState(
        period=period,
        sources=frozenset(_SOURCE_MAP[source_choice]),
        moments=None if len(moments) == len(moment_options) else frozenset(moments),
        bands=None if len(bands) == len(band_labels) else frozenset(bands),
        low=low,
        high=high,
        show_scans=show_scans,
    )
