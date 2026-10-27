"""Figuras Plotly de Alimentación (sin Streamlit, para poder probarlas).

Convenciones (las mismas del módulo Glucosa): violeta = Firebase, azul = LibreView, escaneos en
gris y opcionales. Las lecturas **manuales nunca se unen con línea**; el sensor se corta en
interrupciones de más de 30 minutos y no se interpola. Los nombres de alimentos son texto libre:
se escapan antes de llegar a Plotly (que interpreta HTML básico en etiquetas y tooltips).
"""

import html
from collections.abc import Collection, Sequence
from datetime import datetime, timedelta

import plotly.graph_objects as go

from glucosa.analytics.glucose_view import Band
from glucosa.analytics.meal_glucose import (
    WINDOW_ORDER,
    MealAssociation,
    MealGlucose,
    Window,
)
from glucosa.analytics.meal_milestones import SENSOR_MINIMUM_TOLERANCE_MINUTES, MilestoneStatus
from glucosa.analytics.meal_readings import ReadingSource, WindowReading
from glucosa.analytics.meal_summaries import DayCount, FoodRank, HourBin, TypeCount
from glucosa.analytics.meal_view import MealView
from glucosa.data.timeutil import to_santiago
from glucosa.ui.glucose_charts import BAND_COLORS, COLOR_MANUAL, COLOR_SCAN, COLOR_SENSOR
from glucosa.ui.meal_labels import LEGEND_NAMES, signed_minutes

GAP_MINUTES = 30
GRID = "rgba(150,160,175,0.15)"
_WINDOW_NAMES = {Window.PRE: "Previa", Window.AT: "Al comer", Window.POST: "Posterior"}
_WINDOW_FILL = {
    Window.PRE: "rgba(150,160,175,0.05)",
    Window.AT: "rgba(150,160,175,0.14)",
    Window.POST: "rgba(150,160,175,0.05)",
}
_TICKS = list(range(-60, 181, 30))


def _headroom(values: Sequence[int]) -> list[float]:
    """Rango del eje de barras con holgura a la derecha para que quepa el texto «n · %»."""
    return [0, max(values, default=1) * 1.3 or 1]


def _compact(fig: go.Figure, height: int, title: str) -> go.Figure:
    fig.update_layout(
        title={"text": title, "font": {"size": 13}},
        height=height,
        margin={"l": 10, "r": 10, "t": 38, "b": 10},
        font={"size": 12},
        showlegend=False,
    )
    return fig


# ------------------------------------------------------------------ distribuciones
def type_figure(counts: Sequence[TypeCount]) -> go.Figure:
    """Comidas por tipo DECLARADO (no se infiere de la hora)."""
    shown = [c for c in counts if c.type is not None or c.meals > 0]
    ordered = list(reversed(shown))  # el primer tipo arriba
    fig = go.Figure(
        go.Bar(
            x=[c.meals for c in ordered],
            y=[c.label for c in ordered],
            orientation="h",
            marker_color=COLOR_MANUAL,
            text=[
                f"{c.meals}" + (f" · {c.share:.0%}" if c.share is not None else "") for c in ordered
            ],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x} comidas<extra></extra>",
        )
    )
    fig.update_xaxes(gridcolor=GRID, range=_headroom([c.meals for c in ordered]))
    return _compact(fig, 230, "Comidas por tipo declarado")


def hours_figure(histogram: Sequence[HourBin]) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=[b.hour for b in histogram],
            y=[b.meals for b in histogram],
            marker_color=COLOR_MANUAL,
            hovertemplate="%{x}:00 – %{x}:59 · %{y} comidas<extra></extra>",
        )
    )
    fig.update_xaxes(
        title="Hora del día (hora local de Chile)", dtick=2, range=[-0.6, 23.6], gridcolor=GRID
    )
    fig.update_yaxes(gridcolor=GRID, rangemode="tozero", dtick=1)
    return _compact(fig, 230, "Comidas por hora del día")


def ranking_figure(ranking: Sequence[FoodRank], top: int = 10) -> go.Figure | None:
    """Alimentos que aparecen en más comidas (cuenta nombres, no nutrientes ni cantidades)."""
    rows = list(ranking)[:top]
    if not rows:
        return None
    positions = list(range(len(rows)))[::-1]  # el primero arriba
    names = [html.escape(r.display_name) for r in rows]
    fig = go.Figure(
        go.Bar(
            x=[r.meals for r in rows],
            y=positions,
            orientation="h",
            marker_color=COLOR_MANUAL,
            text=[f"{r.meals} · {r.share_of_meals:.0%}" for r in rows],
            textposition="outside",
            cliponaxis=False,
            customdata=[(n, r.meals, r.occurrences) for n, r in zip(names, rows, strict=True)],
            hovertemplate="%{customdata[0]}: en %{customdata[1]} comidas (%{customdata[2]} veces)"
            "<extra></extra>",
        )
    )
    fig.update_yaxes(tickmode="array", tickvals=positions, ticktext=names)
    fig.update_xaxes(gridcolor=GRID, range=_headroom([r.meals for r in rows]), dtick=1)
    return _compact(
        fig, max(230, 26 * len(rows) + 60), "Alimentos más frecuentes (comidas que los contienen)"
    )


def daily_figure(days: Sequence[DayCount]) -> go.Figure:
    """Un punto por cada día del período: sin registro ≠ sin comer."""
    recorded = [d for d in days if d.has_records]
    empty = [d for d in days if not d.has_records]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Comidas",
            x=[d.day for d in recorded],
            y=[d.meals for d in recorded],
            marker_color=COLOR_MANUAL,
            hovertemplate="%{x|%d-%m-%Y}: %{y} comidas<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            name="Días sin registro",
            x=[d.day for d in empty],
            y=[0] * len(empty),
            mode="markers",
            marker={"color": COLOR_SCAN, "size": 5, "symbol": "line-ew-open"},
            hovertemplate="%{x|%d-%m-%Y}: sin registro<extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%d-%m", gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID, rangemode="tozero", dtick=1)
    return _compact(fig, 230, "Comidas por día · un día sin registro no es un día sin comer")


# ------------------------------------------------------------ una comida y su glucosa
def _clock(reading: WindowReading) -> str:
    return to_santiago(reading.reading.instant).strftime("%d-%m %H:%M")


def _hover(item: WindowReading, flags: Sequence[str] = ()) -> str:
    reading = item.reading
    parts = [
        f"{reading.value} mg/dL",
        f"{_clock(item)} · {signed_minutes(item.delta_minutes, 0)} de la comida",
        LEGEND_NAMES[reading.source],
        *flags,
    ]
    return "<br>".join(parts)


def _all_readings(outcome: MealGlucose, source: ReadingSource) -> list[WindowReading]:
    found = [r for w in WINDOW_ORDER for r in outcome.summary(w, source).readings]
    return sorted(found, key=lambda r: r.reading.instant)


def _flags(item: WindowReading, outcome: MealGlucose, association: MealAssociation) -> list[str]:
    flags = []
    if association.equivalent_manual_of(item.reading.id) is not None:
        flags.append("Coincidencia probable con una medición manual (no prueba identidad)")
    if item.reading.id in outcome.shared_reading_ids:
        flags.append("Lectura compartida con la ventana de otra comida")
    return flags


def _sensor_trace(outcome, association) -> go.Scatter | None:
    readings = _all_readings(outcome, ReadingSource.SENSOR)
    if not readings:
        return None
    xs: list[float | None] = []
    ys: list[int | None] = []
    texts: list[str] = []
    previous: datetime | None = None
    for item in readings:
        if previous is not None and item.reading.instant - previous > timedelta(
            minutes=GAP_MINUTES
        ):
            xs.append(None)
            ys.append(None)
            texts.append("")  # corta la línea: no se interpola a través de un hueco
        xs.append(item.delta_minutes)
        ys.append(item.reading.value)
        texts.append(_hover(item, _flags(item, outcome, association)))
        previous = item.reading.instant
    return go.Scatter(
        name=LEGEND_NAMES[ReadingSource.SENSOR],
        x=xs,
        y=ys,
        mode="lines+markers",
        line={"color": COLOR_SENSOR, "width": 1.5},
        marker={"color": COLOR_SENSOR, "size": 5},
        connectgaps=False,
        hovertext=texts,
        hoverinfo="text",
    )


def _point_trace(source, readings, outcome, association, marker) -> go.Scatter | None:
    if not readings:
        return None
    return go.Scatter(
        name=LEGEND_NAMES[source],
        x=[r.delta_minutes for r in readings],
        y=[r.reading.value for r in readings],
        mode="markers",  # puntos aislados: nunca se unen con línea
        marker=marker,
        hovertext=[_hover(r, _flags(r, outcome, association)) for r in readings],
        hoverinfo="text",
    )


def _reference_trace(outcome, sources) -> go.Scatter | None:
    items = [(s, outcome.reference[s]) for s in outcome.reference if s in sources]
    if not items:
        return None
    return go.Scatter(
        name="Referencia",
        x=[ref.reading.delta_minutes for _, ref in items],
        y=[ref.reading.reading.value for _, ref in items],
        mode="markers",
        marker={"symbol": "circle-open", "size": 17, "color": "#E6EAF0", "line": {"width": 2}},
        hovertext=[
            _hover(
                ref.reading,
                ["Referencia · posterior al registro" if ref.after_record else "Referencia"],
            )
            for _, ref in items
        ],
        hoverinfo="text",
    )


def _milestone_trace(outcome, sources) -> go.Scatter | None:
    xs, ys, texts = [], [], []
    for minutes, by_source in outcome.milestones.items():
        for source, result in by_source.items():
            if source in sources and result.status is MilestoneStatus.MEASURED and result.reading:
                xs.append(result.reading.delta_minutes)
                ys.append(result.reading.reading.value)
                texts.append(
                    f"Más cercana al hito +{minutes}: {result.reading.reading.value} mg/dL"
                    f"<br>{signed_minutes(result.offset_minutes or 0, 0)} del hito"
                    f" · {LEGEND_NAMES[source]}"
                )
    if not xs:
        return None
    return go.Scatter(
        name="Más cercana al hito",
        x=xs,
        y=ys,
        mode="markers",
        marker={"symbol": "square-open", "size": 15, "color": "#F0A830", "line": {"width": 2}},
        hovertext=texts,
        hoverinfo="text",
    )


def _add_marks(fig: go.Figure, tolerance: int) -> None:
    """Registro (0), +60 y +90 con bandas de tolerancia (y la del sensor si su mínimo es mayor)."""
    sensor_tolerance = max(tolerance, SENSOR_MINIMUM_TOLERANCE_MINUTES)
    for window, (start, end) in {
        Window.PRE: (-60, -5),
        Window.AT: (-5, 5),
        Window.POST: (5, 180),
    }.items():
        fig.add_vrect(x0=start, x1=end, fillcolor=_WINDOW_FILL[window], line_width=0, layer="below")
        fig.add_annotation(
            x=(start + end) / 2,
            y=1.02,
            yref="paper",
            text=_WINDOW_NAMES[window],
            showarrow=False,
            font={"size": 11, "color": "#9AA4B2"},
        )
    bands = [(tolerance, "rgba(240,168,48,0.16)")]
    if sensor_tolerance > tolerance:  # el mínimo del sensor (±8) es mayor: se dibuja aparte
        bands.insert(0, (sensor_tolerance, "rgba(77,163,255,0.10)"))
    for minutes in (60, 90):
        for half, color in bands:
            fig.add_shape(
                type="rect",
                x0=minutes - half,
                x1=minutes + half,
                y0=0,
                y1=1,
                yref="paper",
                fillcolor=color,
                line_width=0,
                layer="below",
            )
        fig.add_annotation(
            x=minutes,
            y=0.02,
            yref="paper",
            text=f"+{minutes}",
            showarrow=False,
            font={"size": 11, "color": "#F0A830"},
        )
    for x, dash, color in (
        (0, "solid", "#E6EAF0"),
        (60, "dash", "#F0A830"),
        (90, "dash", "#F0A830"),
    ):
        fig.add_shape(
            type="line",
            x0=x,
            x1=x,
            y0=0,
            y1=1,
            yref="paper",
            line={"color": color, "dash": dash, "width": 1.5},
        )


def meal_window_figure(
    meal: MealView,
    outcome: MealGlucose,
    association: MealAssociation,
    *,
    tolerance_minutes: int,
    sources: Collection[ReadingSource],
    show_scans: bool,
    target_range: tuple[int, int],
) -> go.Figure:
    """Glucosa de −60 a +180 min alrededor del registro, con marcas en 0, +60 y +90."""
    fig = go.Figure()
    fig.add_hrect(
        y0=target_range[0],
        y1=target_range[1],
        fillcolor=BAND_COLORS[Band.IN_RANGE],
        opacity=0.10,
        line_width=0,
        layer="below",
    )
    _add_marks(fig, tolerance_minutes)
    traces = [
        _sensor_trace(outcome, association) if ReadingSource.SENSOR in sources else None,
        _point_trace(
            ReadingSource.IMPORTED,
            _all_readings(outcome, ReadingSource.IMPORTED)
            if ReadingSource.IMPORTED in sources
            else [],
            outcome,
            association,
            {
                "symbol": "diamond-open",
                "size": 10,
                "color": COLOR_MANUAL,
                "line": {"color": COLOR_MANUAL, "width": 2},
            },
        ),
        _point_trace(
            ReadingSource.MANUAL,
            _all_readings(outcome, ReadingSource.MANUAL) if ReadingSource.MANUAL in sources else [],
            outcome,
            association,
            {
                "symbol": "diamond",
                "size": 10,
                "color": COLOR_MANUAL,
                "line": {"color": "white", "width": 1},
            },
        ),
    ]
    if show_scans:
        scans = [r for w in WINDOW_ORDER for r in outcome.scans[w]]
        traces.append(
            _point_trace(
                ReadingSource.SCAN,
                scans,
                outcome,
                association,
                {
                    "symbol": "circle-open",
                    "size": 8,
                    "color": COLOR_SCAN,
                    "line": {"color": COLOR_SCAN, "width": 1.5},
                },
            )
        )
    traces += [_reference_trace(outcome, sources), _milestone_trace(outcome, sources)]
    for trace in traces:
        if trace is not None:
            fig.add_trace(trace)
    _annotate_neighbors(fig, outcome)
    if not any(trace is not None and trace.name in LEGEND_NAMES.values() for trace in traces):
        fig.add_annotation(
            x=60,
            y=0.5,
            yref="paper",
            text="Sin mediciones de glucosa en estas ventanas",
            showarrow=False,
            font={"size": 14, "color": "#9AA4B2"},
        )
    fig.update_xaxes(
        title="Minutos desde el registro de la comida",
        range=[-65, 185],
        tickvals=_TICKS,
        ticktext=[f"+{t}" if t > 0 else (f"−{abs(t)}" if t < 0 else "0") for t in _TICKS],
        gridcolor=GRID,
    )
    fig.update_yaxes(title="Glucosa (mg/dL)", gridcolor=GRID)
    fig.update_layout(
        height=400,
        margin={"l": 10, "r": 10, "t": 56, "b": 10},
        font={"size": 12},
        hovermode="closest",
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.08, "xanchor": "left", "x": 0},
    )
    return fig


def _annotate_neighbors(fig: go.Figure, outcome: MealGlucose) -> None:
    for neighbor in outcome.overlapping:
        if -65 <= neighbor.minutes <= 185:
            fig.add_shape(
                type="line",
                x0=neighbor.minutes,
                x1=neighbor.minutes,
                y0=0,
                y1=1,
                yref="paper",
                line={"color": "#9AA4B2", "dash": "dot", "width": 1},
            )
            fig.add_annotation(
                x=neighbor.minutes,
                y=0.93,
                yref="paper",
                text=f"Otra comida ({neighbor.type_label}) {signed_minutes(neighbor.minutes, 0)}",
                showarrow=False,
                font={"size": 11, "color": "#9AA4B2"},
                textangle=-90,
                xanchor="left",
            )
