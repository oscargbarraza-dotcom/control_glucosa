"""Página «Glucosa» de Streamlit: presentación y orquestación (la lógica está en ``analytics/``).

Fuentes independientes y siempre rotuladas:

* :violet[**Firebase · mediciones manuales**] — puntos aislados; su porcentaje cuenta MEDICIONES.
* :violet[**Firebase · mediciones importadas**] — registros de Firebase marcados «Importado desde
  otra aplicación»: se conservan todos, pero nunca se mezclan con las manuales ni se tratan como
  lecturas del sensor.
* :blue[**LibreView · sensor FreeStyle Libre**] — historial cada ~15 min; el tiempo en rango es una
  ESTIMACIÓN con cobertura visible y solo se muestra si hay datos suficientes.

Nunca se mezclan en un mismo estadístico y no se deduplica ni fusiona nada entre fuentes.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from glucosa.analytics.glucose_filters import filter_points
from glucosa.analytics.glucose_match import match_manual_to_scans
from glucosa.analytics.glucose_sensor import (
    HistoryConsolidation,
    SensorSample,
    consolidate_history,
)
from glucosa.analytics.glucose_summaries import (
    ManualSummary,
    SensorSummary,
    summarize_by_moment,
    summarize_imported,
    summarize_manual,
    summarize_sensor,
)
from glucosa.analytics.glucose_view import (
    GlucosePoint,
    Kind,
    Source,
    manual_points,
    sensor_points,
)
from glucosa.data.timeutil import to_santiago
from glucosa.errors import GlucosaError
from glucosa.models.records import Origin
from glucosa.sources.libre.models import RecordType
from glucosa.sources.libre.summary import render_summary
from glucosa.ui.glucose_charts import (
    EVOLUTION_CONFIG,
    PLOT_CONFIG,
    evolution_figure,
    manual_bands_figure,
    sensor_bands_figure,
    sensor_histogram_figure,
)
from glucosa.ui.glucose_filters_ui import FilterState, render_filters
from glucosa.ui.glucose_kpi import Kpi, Tone, kpi_grid_html
from glucosa.ui.glucose_sources import (
    GlucoseSources,
    LibreLoad,
    ManualLoad,
    SourceStatus,
)
from glucosa.ui.glucose_style import inject_compact_style
from glucosa.ui.glucose_table import points_table

MANUAL_TTL_SECONDS = 300
ERROR_TTL_SECONDS = 10  # un error de red no se repite en cada interacción, pero se reintenta pronto
MANUAL_HEADING = ":violet[Mediciones manuales · Firebase]"
IMPORTED_HEADING = ":violet[Mediciones importadas · Firebase]"
SENSOR_HEADING = ":blue[Sensor FreeStyle Libre · LibreView]"
SOURCE_BADGES = {"Firebase": "🟣 Firebase", "LibreView": "🔵 LibreView"}
_MANUAL_KEY = "glucosa_cache_manual"
_LIBRE_KEY = "glucosa_cache_libre"
_LAST_IMPORT_KEY = "glucosa_ultima_importacion"
_UPLOAD_NONCE_KEY = "glucosa_csv_nonce"
# Estados que nunca se guardan en caché: se vuelven a comprobar en cada recarga (son locales y
# baratos) para que iniciar sesión por la línea de comandos se note de inmediato.
_UNCACHED_MANUAL = frozenset({SourceStatus.NO_SESSION, SourceStatus.SESSION_EXPIRED})


@dataclass(frozen=True)
class LibreData:
    load: LibreLoad
    sensor: list[GlucosePoint]
    scans: list[GlucosePoint]
    samples: list[SensorSample]
    history: HistoryConsolidation


def _fmt(moment: datetime | None) -> str:
    return "—" if moment is None else to_santiago(moment).strftime("%d-%m-%Y %H:%M")


def _num(value: float | None, digits: int = 0) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


# ----------------------------------------------------------------- carga + caché
def _manual_ttl(result: ManualLoad) -> float | None:
    if result.status is SourceStatus.OK:
        return MANUAL_TTL_SECONDS
    if result.status in _UNCACHED_MANUAL or result.status is SourceStatus.CONFIG:
        return None
    return ERROR_TTL_SECONDS


def _load_manual(sources: GlucoseSources, force: bool) -> ManualLoad:
    marker = sources.session_marker()
    entry = st.session_state.get(_MANUAL_KEY)
    if entry and not force:
        stored_at, result, stored_marker, ttl = entry
        # Si cerraron sesión o cambiaron de cuenta por la línea de comandos, no se reutiliza.
        if stored_marker == marker and time.monotonic() - stored_at < ttl:
            return result
    with st.spinner("Leyendo mediciones manuales de Firebase…"):
        result = sources.load_manual()
    ttl = _manual_ttl(result)
    if ttl is None:
        st.session_state.pop(_MANUAL_KEY, None)
    else:
        st.session_state[_MANUAL_KEY] = (time.monotonic(), result, marker, ttl)
    return result


def _libre_data(load: LibreLoad) -> LibreData:
    history = consolidate_history(load.readings)
    scans = [r for r in load.readings if r.record_type is RecordType.SCAN]
    return LibreData(
        load=load,
        sensor=sensor_points(history.readings),
        scans=sensor_points(scans),
        samples=[SensorSample(r.instant_utc, r.glucose_mg_dl) for r in history.readings],
        history=history,
    )


def _load_libre(sources: GlucoseSources) -> LibreData:
    signature = sources.libre_signature()
    entry = st.session_state.get(_LIBRE_KEY)
    if entry and entry[0] == signature:
        return entry[1]
    with st.spinner("Abriendo la base local de LibreView…"):
        data = _libre_data(sources.load_libre())
    if data.load.status is SourceStatus.ERROR:  # un error (p. ej. archivo en uso) se reintenta
        st.session_state.pop(_LIBRE_KEY, None)
    else:
        st.session_state[_LIBRE_KEY] = (signature, data)
    return data


# --------------------------------------------------------------- bloques de UI
def _status_messages(manual: ManualLoad, libre: LibreLoad) -> None:
    if manual.status is not SourceStatus.OK:
        icon = (
            "🔒"
            if manual.status in (SourceStatus.NO_SESSION, SourceStatus.SESSION_EXPIRED)
            else "⚠️"
        )
        st.warning(f"Firebase: {manual.message}", icon=icon)
    elif manual.rejected:
        st.warning(
            f"{manual.rejected} documento(s) de Firebase no pasaron la validación y se omitieron."
        )
    if libre.status is SourceStatus.ERROR:
        st.error(f"LibreView: {libre.message}")


_FIREBASE_STATE = {
    SourceStatus.OK: (":green[●]", "disponible"),
    SourceStatus.NO_SESSION: (":orange[●]", "sin sesión"),
    SourceStatus.SESSION_EXPIRED: (":orange[●]", "sesión vencida"),
    SourceStatus.CONFIG: (":orange[●]", "sin configurar"),
    SourceStatus.ERROR: (":red[●]", "con error"),
    SourceStatus.EMPTY: (":orange[●]", "sin datos"),
}
_LIBRE_STATE = {**_FIREBASE_STATE, SourceStatus.EMPTY: (":orange[●]", "sin datos")}


def _source_chip(name: str, color: str, state: tuple[str, str], detail: str) -> str:
    dot, text = state
    return f":{color}[**{name}**] {dot} {text}{detail}"


def _status_line(filters: FilterState | None, manual: ManualLoad, libre: LibreLoad) -> str:
    """Una sola línea: período, rango objetivo y estado + última actualización de cada fuente."""
    parts = []
    if filters is not None:
        period = filters.period
        parts.append(
            f"**Período:** {period.label} · {period.first_day:%d-%m-%Y} → {period.last_day:%d-%m-%Y}"
        )
        parts.append(f"**Rango objetivo:** {filters.low}–{filters.high} mg/dL")
    firebase_when = (
        f" · consulta {_fmt(manual.fetched_at)}"
        if manual.status is SourceStatus.OK and manual.fetched_at
        else ""
    )
    parts.append(_source_chip("Firebase", "violet", _FIREBASE_STATE[manual.status], firebase_when))
    last_import = libre.stats.last_import_utc if libre.stats is not None else None
    libre_when = f" · importación {_fmt(last_import)}" if last_import else ""
    parts.append(_source_chip("LibreView", "blue", _LIBRE_STATE[libre.status], libre_when))
    return "  │  ".join(parts)


def _sources_detail(manual: ManualLoad, libre: LibreLoad) -> None:
    with st.expander("Detalle de las fuentes"):
        parts = []
        if manual.status is SourceStatus.OK and manual.records:
            first, last = manual.records[0].measured_at, manual.records[-1].measured_at
            parts.append(
                f"🟣 **Firebase**: {len(manual.records)} mediciones sincronizadas "
                f"({_fmt(first)} → {_fmt(last)})"
            )
        if libre.stats is not None and libre.stats.total:
            stats = libre.stats
            parts.append(
                f"🔵 **LibreView**: {stats.historic} lecturas del historial y {stats.scans} escaneos "
                f"({(stats.period_start or '—').replace('T', ' ')} → {(stats.period_end or '—').replace('T', ' ')}); "
                f"última importación {_fmt(stats.last_import_utc)}"
            )
        if parts:
            st.caption("Solo se muestran datos sincronizados / importados. " + " · ".join(parts))
        _firebase_freshness(manual)
        if not parts and manual.fetched_at is None:
            st.caption("Aún no hay datos de ninguna fuente.")


def _firebase_freshness(manual: ManualLoad) -> None:
    """Dos datos distintos: cuándo se consultó Firebase y cuál es la última medición disponible."""
    if manual.status is not SourceStatus.OK or manual.fetched_at is None:
        return
    last = max((r.measured_at for r in manual.records), default=None)
    st.caption(
        f"🟣 **Última consulta exitosa a Firebase:** {_fmt(manual.fetched_at)} · "
        f"**Última medición disponible:** {_fmt(last)}. "
        "La primera es la hora en que esta aplicación leyó Firestore; no confirma que el teléfono "
        "haya sincronizado en ese momento."
    )


def _run_import(sources: GlucoseSources, file_name: str, content: bytes) -> None:
    """Importa, descarta la caché del sensor y recarga: los números se actualizan al instante."""
    try:
        with st.spinner("Importando…"):
            summary = sources.import_csv(file_name, content)
    except GlucosaError as exc:
        st.error(str(exc))
        return
    headline = (
        f"Importación completa: {summary.new} nuevos, {summary.repeated} repetidos, "
        f"{summary.invalid} inválidos, {summary.conflicts} conflictos."
    )
    st.session_state[_LAST_IMPORT_KEY] = (headline, render_summary(summary))
    st.session_state.pop(_LIBRE_KEY, None)
    # Cambiar la clave del cargador libera el CSV de la memoria del servidor.
    st.session_state[_UPLOAD_NONCE_KEY] = st.session_state.get(_UPLOAD_NONCE_KEY, 0) + 1
    st.rerun()


def _import_section(sources: GlucoseSources) -> None:
    nonce = st.session_state.get(_UPLOAD_NONCE_KEY, 0)
    with st.expander("Importar un CSV de LibreView", expanded=_LAST_IMPORT_KEY in st.session_state):
        st.caption(
            "Exporta el CSV desde LibreView (en español) y súbelo aquí. La importación es incremental "
            "e idempotente: puedes subir archivos que se solapen o repetir el mismo. El archivo "
            "original no se modifica ni se guarda en disco; solo se conservan las lecturas de glucosa."
        )
        uploaded = st.file_uploader("CSV de LibreView", type=["csv"], key=f"glucosa_csv_{nonce}")
        if uploaded is not None and st.button("Importar este archivo", key="glucosa_importar"):
            _run_import(sources, uploaded.name, uploaded.getvalue())
        if _LAST_IMPORT_KEY in st.session_state:
            headline, report = st.session_state[_LAST_IMPORT_KEY]
            st.success(headline)
            st.code(report, language=None)


def _columns_for(show_manual: bool, show_sensor: bool) -> tuple[DeltaGenerator, DeltaGenerator]:
    """Dos columnas si se ven ambas fuentes; si no, el mismo contenedor a todo el ancho."""
    if show_manual and show_sensor:
        left, right = st.columns(2, gap="medium")
        return left, right
    container = st.container()
    return container, container


def _stat(value: float | int | None) -> str:
    return "—" if value is None else f"{value:.0f}"


def _firebase_kpis(summary: ManualSummary) -> None:
    unit = "mg/dL"
    last = "—" if summary.last_value is None else str(summary.last_value)
    items = [
        Kpi("Última", last, unit, _fmt(summary.last_instant)),
        Kpi("Mediciones", str(summary.count)),
        Kpi("Promedio", _stat(summary.mean), unit),
        Kpi("Mediana", _stat(summary.median), unit),
        Kpi("Mínimo", _stat(summary.minimum), unit),
        Kpi("Máximo", _stat(summary.maximum), unit),
    ]
    st.html(kpi_grid_html(items, Tone.FIREBASE))


def _manual_kpis(summary: ManualSummary, load: ManualLoad) -> None:
    st.subheader(MANUAL_HEADING)
    if summary.count == 0:
        if load.status is SourceStatus.OK:
            st.info("Sin mediciones manuales en este período.")
        else:
            st.info("No se pudieron cargar las mediciones de Firebase (ver el aviso de arriba).")
        return
    _firebase_kpis(summary)


def _imported_kpis(summary: ManualSummary) -> None:
    """Indicadores propios de las importadas; no se suman a las manuales."""
    st.subheader(IMPORTED_HEADING)
    if summary.count == 0:
        st.info("Sin mediciones importadas en este período.")
        return
    st.caption(
        "Marcadas «Importado/Tomado desde otra aplicación»: no se asumen lecturas del sensor "
        "ni cuentan como manuales."
    )
    _firebase_kpis(summary)


def _sensor_kpis(data: LibreData, summary: SensorSummary | None) -> None:
    st.subheader(SENSOR_HEADING)
    if summary is None:
        if data.load.status is SourceStatus.ERROR:
            st.info("No se pudo leer la base local de LibreView (ver el aviso de arriba).")
        else:
            st.info("Sin lecturas del sensor: importa un CSV de LibreView.")
        return
    unit = "mg/dL"
    items = [
        Kpi("Lecturas", str(summary.count), "", "Lecturas del historial del sensor en el período"),
        Kpi("Promedio", _stat(summary.mean), unit),
        Kpi("Mediana", _stat(summary.median), unit),
        Kpi("Mínimo", _stat(summary.minimum), unit),
        Kpi("Máximo", _stat(summary.maximum), unit),
        Kpi("Cobertura", f"{summary.tir.coverage:.0%}", "", "Cobertura del período solicitado"),
    ]
    st.html(kpi_grid_html(items, Tone.LIBREVIEW))
    st.caption(
        f"Datos disponibles: {_fmt(summary.first_available)} → {_fmt(summary.last_available)} · "
        f"en el período: {_fmt(summary.first_in_period)} → {_fmt(summary.last_in_period)}"
    )


def _bands_chart(summary: ManualSummary, key: str) -> None:
    figure = manual_bands_figure(summary)
    if figure is not None:
        st.plotly_chart(figure, width="stretch", key=key, config=PLOT_CONFIG)


def _tir_figure(summary: SensorSummary) -> None:
    tir = summary.tir
    figure = sensor_bands_figure(tir)
    if figure is None:
        st.warning(
            f"{tir.message} (lecturas en el período: {tir.readings_in_window}, cobertura "
            f"{tir.coverage:.0%}; se exigen ≥ 96 lecturas y ≥ 70 % de cobertura)."
        )
        return
    st.plotly_chart(figure, width="stretch", key="glucosa_bandas_sensor", config=PLOT_CONFIG)
    if tir.estimated:
        st.caption(
            f"TIR estimado con cobertura {tir.coverage:.0%}: el tiempo sin lecturas no se "
            "interpola ni se atribuye."
        )


def _history_notices(history: HistoryConsolidation) -> None:
    if history.duplicates:
        st.caption(
            f"{history.duplicates} lectura(s) repetida(s) entre dispositivos se contaron una sola vez."
        )
    if history.conflict_minutes:
        st.warning(
            f"{history.conflict_minutes} minuto(s) tienen valores distintos entre dispositivos: "
            "se conservaron todos y no se fusionaron."
        )


def _histogram(summary: SensorSummary, f: FilterState) -> None:
    if summary.histogram:
        with st.expander("Distribución de las lecturas (mg/dL)"):
            st.plotly_chart(
                sensor_histogram_figure(list(summary.histogram), f.low, f.high),
                width="stretch",
                key="glucosa_histograma",
                config=PLOT_CONFIG,
            )


def _interruptions(summary: SensorSummary) -> None:
    tir = summary.tir
    label = (
        f"Intervalos sin datos (> 30 min): {len(tir.interruptions)} · "
        f"días sin lecturas: {tir.days_without_readings}"
    )
    with st.expander(label):
        if not tir.interruptions:
            st.write("No hay interrupciones de más de 30 minutos en el período.")
            return
        frame = pd.DataFrame(
            [
                {
                    "Desde": to_santiago(i.start).replace(tzinfo=None),
                    "Hasta": to_santiago(i.end).replace(tzinfo=None),
                    "Duración (min)": round(i.minutes),
                }
                for i in tir.interruptions
            ]
        )
        st.dataframe(frame, hide_index=True, width="stretch")
        st.caption("Duración del intervalo entre dos lecturas; la línea del gráfico se corta ahí.")


ROW_HEIGHT = 30


def _moment_table(points: Sequence[GlucosePoint], f: FilterState) -> None:
    rows = summarize_by_moment(points, f.low, f.high)
    st.subheader(":violet[Resumen por momento declarado] (solo mediciones manuales)")
    if not rows:
        st.info("Sin mediciones manuales en este período.")
        return
    frame = pd.DataFrame(
        [
            {
                "Momento declarado": r.label,
                "Mediciones": r.count,
                "Promedio": r.mean,
                "Mediana": r.median,
                "Mín.": r.minimum,
                "Máx.": r.maximum,
                "% en rango": round(r.pct_in_range * 100),
            }
            for r in rows
        ]
    )
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        row_height=ROW_HEIGHT,
        height=(len(frame) + 1) * ROW_HEIGHT + 3,
        column_config={
            "Momento declarado": st.column_config.TextColumn(width=150),
            "Mediciones": st.column_config.NumberColumn(format="%d", width=100),
            "Promedio": st.column_config.NumberColumn(format="%.1f", width=100),
            "Mediana": st.column_config.NumberColumn(format="%.1f", width=100),
            "Mín.": st.column_config.NumberColumn(format="%d", width=80),
            "Máx.": st.column_config.NumberColumn(format="%d", width=80),
            "% en rango": st.column_config.NumberColumn(format="%d %%", width=110),
        },
    )
    st.caption(
        "Promedio, mediana, mínimo y máximo en mg/dL. «% en rango» es el porcentaje de MEDICIONES "
        "dentro del rango objetivo (no es tiempo en rango). El momento es el que declaraste en "
        "Android; no se infiere desde Alimentación."
    )


def _select(
    points: Sequence[GlucosePoint], f: FilterState, source: Source, kinds: set[Kind] | None = None
) -> list[GlucosePoint]:
    """Filtros globales del gráfico y la tabla (los indicadores no usan la clasificación)."""
    moments = f.moments if source is Source.FIREBASE else None
    return filter_points(
        points, f.period, {source} & f.sources, kinds, f.bands, moments, f.low, f.high
    )


def _evolution(firebase: list[GlucosePoint], data: LibreData, f: FilterState) -> None:
    st.subheader("Evolución temporal")
    manual = _select(firebase, f, Source.FIREBASE, {Kind.MANUAL})
    imported = _select(firebase, f, Source.FIREBASE, {Kind.IMPORTED})
    sensor = _select(data.sensor, f, Source.LIBREVIEW)
    scans = _select(data.scans, f, Source.LIBREVIEW)
    if not (manual or imported or sensor or (f.show_scans and scans)):
        st.info("No hay registros para mostrar con los filtros elegidos.")
        return
    st.plotly_chart(
        evolution_figure(
            manual, sensor, scans, f.low, f.high, f.show_scans, f.revision_key, imported
        ),
        width="stretch",
        key="glucosa_evolucion",
        config=EVOLUTION_CONFIG,
    )
    st.caption(
        f"Franja verde = rango objetivo {f.low}–{f.high} mg/dL · rombos = mediciones manuales "
        "(Firebase) · rombos huecos = importadas desde otra aplicación · línea azul = historial "
        "del sensor (LibreView), cortada donde hay más de 30 min sin datos · círculos = escaneos "
        "(opcional). No se interpola ningún valor."
    )


def _match_block(manual: ManualLoad, libre: LibreLoad) -> None:
    records = [r for r in manual.records if r.origin is Origin.MANUAL]
    if manual.status is not SourceStatus.OK or not records or not libre.readings:
        return
    with st.expander("Coincidencia manual ↔ escaneo (informativa)"):
        coverage = (libre.readings[0].instant_utc, libre.readings[-1].instant_utc)
        result = match_manual_to_scans(records, libre.readings, coverage=coverage)
        st.write(result.label)
        st.caption(
            f"Una medición manual coincide si hay un escaneo a ±{result.params.time_tolerance_minutes:g} min "
            f"y con diferencia ≤ {result.params.value_tolerance_mg_dl} mg/dL. Solo se evalúan las "
            "mediciones dentro del período cubierto por la exportación de LibreView. Es solo informativo: "
            "no se fusiona ni se elimina nada entre fuentes."
        )


CLASS_BADGES = {
    "Bajo el rango": "🔴 Bajo el rango",
    "Dentro del rango": "🟢 Dentro del rango",
    "Sobre el rango": "🟠 Sobre el rango",
}


def _available_count(firebase: list[GlucosePoint], data: LibreData, f: FilterState) -> int:
    """Registros del período y de las fuentes elegidas, sin filtros de visualización (M)."""
    firebase_all = filter_points(firebase, f.period, {Source.FIREBASE} & f.sources)
    sensor_all = filter_points(data.sensor, f.period, {Source.LIBREVIEW} & f.sources)
    scans_all = filter_points(data.scans, f.period, {Source.LIBREVIEW} & f.sources)
    return len(firebase_all) + len(sensor_all) + len(scans_all)


def _table(firebase: list[GlucosePoint], data: LibreData, f: FilterState) -> None:
    st.subheader("Detalle de registros")
    points = _select(firebase, f, Source.FIREBASE)
    points += _select(data.sensor, f, Source.LIBREVIEW)
    if f.show_scans:  # los escaneos solo aparecen si el usuario lo pide (igual que en el gráfico)
        points += _select(data.scans, f, Source.LIBREVIEW)
    frame = points_table(points, f.low, f.high)
    if not frame["Cambio de hora"].any():  # solo se muestra si hay horas repetidas en la tabla
        frame = frame.drop(columns="Cambio de hora")
    search_col, count_col = st.columns([2, 3], vertical_alignment="center")
    query = (
        search_col.text_input(
            "Buscar en observaciones o momento",
            key="glucosa_buscar",
            placeholder="Buscar en observaciones o momento",
            label_visibility="collapsed",
        )
        .strip()
        .lower()
    )
    if query:
        haystack = (frame["Observaciones"] + " " + frame["Momento declarado"]).str.lower()
        frame = frame[haystack.str.contains(query, regex=False)]
    frame = frame.assign(
        Fuente=frame["Fuente"].map(SOURCE_BADGES),
        Clasificación=frame["Clasificación"].map(CLASS_BADGES),
    )
    hidden_scans = (
        0
        if f.show_scans
        else len(filter_points(data.scans, f.period, {Source.LIBREVIEW} & f.sources))
    )
    hidden = f" · escaneos ocultos: {hidden_scans}" if hidden_scans else ""
    count_col.markdown(
        f"**Registros mostrados: {len(frame)} de {_available_count(firebase, data, f)}**{hidden}"
        " · hora local de Chile"
    )
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        height=460,
        column_config={
            "Fecha y hora": st.column_config.DatetimeColumn(format="DD-MM-YYYY HH:mm", width=140),
            "Cambio de hora": st.column_config.TextColumn(width=160),
            "Glucosa (mg/dL)": st.column_config.NumberColumn(format="%d", width=125),
            "Fuente": st.column_config.TextColumn(width=110),
            "Tipo de registro": st.column_config.TextColumn(width=150),
            "Momento declarado": st.column_config.TextColumn(width=150),
            "Observaciones": st.column_config.TextColumn(),
            "Clasificación": st.column_config.TextColumn(width=150),
        },
    )


# ------------------------------------------------------------------ principal
def _summaries(
    firebase_in_period: list[GlucosePoint],
    libre: LibreData,
    f: FilterState,
    show_manual: bool,
    show_sensor: bool,
) -> tuple[ManualSummary, ManualSummary, SensorSummary | None]:
    """Cada indicador se calcula una sola vez por recarga y lo comparten KPI y distribuciones."""
    manual = summarize_manual(firebase_in_period, f.low, f.high)
    imported = summarize_imported(firebase_in_period, f.low, f.high)
    sensor = (
        summarize_sensor(libre.samples, f.period, f.low, f.high)
        if show_sensor and libre.samples
        else None
    )
    return manual, imported, sensor


def _indicator_rows(
    manual_summary: ManualSummary,
    imported_summary: ManualSummary,
    sensor_summary: SensorSummary | None,
    manual: ManualLoad,
    libre: LibreData,
    f: FilterState,
    has_imported: bool,
) -> None:
    show_manual, show_sensor = Source.FIREBASE in f.sources, Source.LIBREVIEW in f.sources
    # Fila 1: indicadores. Fila 2: distribuciones por rango (Firebase y LibreView lado a lado).
    left, right = _columns_for(show_manual, show_sensor)
    if show_manual:
        with left:
            _manual_kpis(manual_summary, manual)
            if has_imported:
                _imported_kpis(imported_summary)
    if show_sensor:
        with right:
            _sensor_kpis(libre, sensor_summary)
    left, right = _columns_for(show_manual, show_sensor)
    if show_manual:
        with left:
            _bands_chart(manual_summary, "glucosa_bandas_manual")
            if has_imported and imported_summary.count:
                _bands_chart(imported_summary, "glucosa_bandas_importadas")
    if show_sensor and sensor_summary is not None:
        with right:
            _history_notices(libre.history)
            _tir_figure(sensor_summary)


def _detail_expanders(
    sensor_summary: SensorSummary | None,
    manual: ManualLoad,
    libre: LibreData,
    f: FilterState,
) -> None:
    show_manual, show_sensor = Source.FIREBASE in f.sources, Source.LIBREVIEW in f.sources
    left, right = _columns_for(show_manual, show_sensor)
    if show_manual and show_sensor:
        with left:
            _match_block(manual, libre.load)
    if show_sensor and sensor_summary is not None:
        with right:
            _histogram(sensor_summary, f)
            _interruptions(sensor_summary)


def render_glucose_page(
    sources: GlucoseSources, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> None:
    inject_compact_style()
    refresh = st.sidebar.button("Actualizar datos de Firebase", key="glucosa_actualizar")
    manual = _load_manual(sources, force=refresh)
    libre = _load_libre(sources)
    filters = render_filters(sources, now)

    st.header("Glucosa")
    st.markdown(_status_line(filters, manual, libre.load))
    _status_messages(manual, libre.load)
    detail_col, import_col = st.columns(2, gap="medium")
    with detail_col:
        _sources_detail(manual, libre.load)
    with import_col:
        _import_section(sources)
    if filters is None:
        return

    firebase = manual_points(manual.records)
    has_imported = any(p.kind is Kind.IMPORTED for p in firebase)
    firebase_in_period = filter_points(
        firebase, filters.period, {Source.FIREBASE}, None, None, filters.moments
    )
    show_manual, show_sensor = (
        Source.FIREBASE in filters.sources,
        Source.LIBREVIEW in filters.sources,
    )
    manual_summary, imported_summary, sensor_summary = _summaries(
        firebase_in_period, libre, filters, show_manual, show_sensor
    )
    _indicator_rows(
        manual_summary, imported_summary, sensor_summary, manual, libre, filters, has_imported
    )
    _detail_expanders(sensor_summary, manual, libre, filters)
    _evolution(firebase, libre, filters)
    if show_manual and manual.status is SourceStatus.OK:
        _moment_table(firebase_in_period, filters)
    _table(firebase, libre, filters)
