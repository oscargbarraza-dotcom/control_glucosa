"""Figuras Plotly del módulo Glucosa (sin Streamlit, para poder probarlas).

Convenciones visuales (se repiten en toda la interfaz):

* **Firebase / manual**: violeta, rombos, puntos independientes (nunca se unen con línea).
* **LibreView / sensor**: azul, línea fina. Se **corta** en toda interrupción de más de 30 min y no
  se interpola glucosa en ningún caso.
* **Firebase / importadas desde otra aplicación**: rombos huecos del mismo violeta (misma fuente,
  distinta procedencia).
* **Escaneos de LibreView**: círculos grises huecos, capa opcional (desactivada por defecto).
* Bandas de clasificación: bajo = rojo, dentro = verde, sobre = ámbar.
"""

import html
from datetime import datetime, timedelta

import plotly.graph_objects as go

from glucosa.analytics.glucose_sensor import TirResult
from glucosa.analytics.glucose_summaries import HistogramBin, ManualSummary
from glucosa.analytics.glucose_view import (
    BAND_LABELS,
    KIND_LABELS,
    SOURCE_LABELS,
    Band,
    GlucosePoint,
    Source,
)
from glucosa.data.timeutil import repeated_hour_pass, to_santiago

# Paleta para el tema oscuro: violeta = Firebase, azul = LibreView, verde / ámbar / rojo = rango.
COLOR_MANUAL = "#B388EB"
COLOR_SENSOR = "#4DA3FF"
COLOR_SCAN = "#9AA4B2"
BAND_COLORS = {Band.BELOW: "#E5534B", Band.IN_RANGE: "#3FB27F", Band.ABOVE: "#F0A830"}
_ON_BAND_TEXT = "#0E1117"  # texto oscuro sobre las barras de color
EVOLUTION_HEIGHT = 500
_HOUR_MS = 3_600_000
# Etiquetas del eje de tiempo según el nivel de zoom (en milisegundos entre marcas).
_TICK_STOPS = [
    {"dtickrange": [None, 6 * _HOUR_MS], "value": "%d-%m %H:%M"},
    {"dtickrange": [6 * _HOUR_MS, 48 * _HOUR_MS], "value": "%d-%m<br>%H:%M"},
    {"dtickrange": [48 * _HOUR_MS, None], "value": "%d-%m-%Y"},
]
SENSOR_NAME = "Sensor LibreView"
MANUAL_NAME = "Manual Firebase"
IMPORTED_NAME = "Importado Firebase"
SCAN_NAME = "Escaneo LibreView"
GAP_MINUTES = 30
MAX_COMMENT_CHARS = 80
_LINE_ONLY_ABOVE_POINTS = 300  # con muchas lecturas se omiten los marcadores
# Sin descarga de imagen: los datos de salud no deben salir hacia Descargas (puede ser OneDrive).
PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["toImage"]}
EVOLUTION_CONFIG = {**PLOT_CONFIG, "scrollZoom": True}


def _local(point: GlucosePoint) -> datetime:
    """Hora de pared de Chile (sin zona) para el eje X."""
    return to_santiago(point.instant).replace(tzinfo=None)


def _hover(point: GlucosePoint) -> str:
    lines = [
        f"<b>{point.value} mg/dL</b>",
        _local(point).strftime("%d-%m-%Y %H:%M"),
        f"Fuente: {SOURCE_LABELS[point.source]} · {KIND_LABELS[point.kind]}",
    ]
    repeated = repeated_hour_pass(point.instant)
    if repeated:
        lines.append(f"Hora repetida por el cambio de horario ({repeated}.ª vez)")
    if point.source is Source.FIREBASE:
        moment = point.moment.label if point.moment else "sin momento declarado"
        lines.append(f"Momento declarado: {moment}")
        if point.comment:
            lines.append("Observación: " + html.escape(point.comment[:MAX_COMMENT_CHARS]))
    return "<br>".join(lines)


def _sensor_trace(points: list[GlucosePoint]) -> go.Scattergl:
    xs: list[datetime] = []
    ys: list[int | None] = []
    hovers: list[str] = []
    previous: GlucosePoint | None = None
    for point in sorted(points, key=lambda p: p.instant):
        if previous is not None and (
            point.instant - previous.instant > timedelta(minutes=GAP_MINUTES)
            or _local(point) < _local(previous)  # hora repetida: la hora de pared retrocede
        ):
            xs.append(_local(point))
            ys.append(None)  # corta la línea: no se conecta a través de la interrupción
            hovers.append("")
        xs.append(_local(point))
        ys.append(point.value)
        hovers.append(_hover(point))
        previous = point
    many = len(points) > _LINE_ONLY_ABOVE_POINTS
    return go.Scattergl(
        name=SENSOR_NAME,
        x=xs,
        y=ys,
        mode="lines" if many else "lines+markers",
        line={"color": COLOR_SENSOR, "width": 1.5},
        marker={"color": COLOR_SENSOR, "size": 4},
        connectgaps=False,
        hovertext=hovers,
        hoverinfo="text",
    )


def _marker_trace(name: str, points: list[GlucosePoint], marker: dict) -> go.Scatter:
    ordered = sorted(points, key=lambda p: p.instant)
    return go.Scatter(
        name=name,
        x=[_local(p) for p in ordered],
        y=[p.value for p in ordered],
        mode="markers",
        marker=marker,
        hovertext=[_hover(p) for p in ordered],
        hoverinfo="text",
    )


def evolution_figure(
    manual: list[GlucosePoint],
    sensor: list[GlucosePoint],
    scans: list[GlucosePoint],
    low: int,
    high: int,
    show_scans: bool = False,
    revision_key: str = "glucosa",
    imported: list[GlucosePoint] | None = None,
) -> go.Figure:
    """Evolución temporal: sensor (línea con cortes), manuales (rombos) y escaneos (opcional)."""
    imported = imported or []
    fig = go.Figure()
    if sensor:
        fig.add_trace(_sensor_trace(sensor))
    if show_scans and scans:
        fig.add_trace(
            _marker_trace(
                SCAN_NAME,
                scans,
                {
                    "symbol": "circle-open",
                    "size": 7,
                    "color": COLOR_SCAN,
                    "line": {"color": COLOR_SCAN, "width": 1.5},
                },
            )
        )
    if manual:
        fig.add_trace(
            _marker_trace(
                MANUAL_NAME,
                manual,
                {
                    "symbol": "diamond",
                    "size": 10,
                    "color": COLOR_MANUAL,
                    "line": {"color": "white", "width": 1},
                },
            )
        )
    if imported:
        fig.add_trace(
            _marker_trace(
                IMPORTED_NAME,
                imported,
                {
                    "symbol": "diamond-open",
                    "size": 10,
                    "color": COLOR_MANUAL,
                    "line": {"color": COLOR_MANUAL, "width": 2},
                },
            )
        )
    fig.add_hrect(
        y0=low,
        y1=high,
        fillcolor=BAND_COLORS[Band.IN_RANGE],
        opacity=0.12,
        line_width=0,
        layer="below",
    )
    shown = [p.value for p in (*manual, *imported, *sensor, *(scans if show_scans else []))]
    layout = {
        "dragmode": "zoom",
        "hovermode": "closest",
        "height": EVOLUTION_HEIGHT,
        "margin": {"l": 10, "r": 10, "t": 40, "b": 10},
        "font": {"size": 13},
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 13},
        },
        "uirevision": revision_key,
        "yaxis": {"title": "Glucosa (mg/dL)", "gridcolor": "rgba(150,160,175,0.18)"},
        "xaxis": {
            "rangeslider": {"visible": False},
            "title": "Hora local (Chile)",
            "gridcolor": "rgba(150,160,175,0.12)",
            "tickformatstops": _TICK_STOPS,
            "hoverformat": "%d-%m-%Y %H:%M",
        },
    }
    fig.update_layout(**layout)
    if shown:
        fig.update_yaxes(range=[max(0, min([*shown, low]) - 15), max([*shown, high]) + 15])
    return fig


def manual_bands_figure(summary: ManualSummary) -> go.Figure | None:
    """Porcentaje de MEDICIONES manuales bajo / dentro / sobre el rango (no es tiempo en rango)."""
    if summary.count == 0:
        return None
    fig = go.Figure()
    parts = (
        (Band.BELOW, summary.below, summary.pct_below),
        (Band.IN_RANGE, summary.in_range, summary.pct_in_range),
        (Band.ABOVE, summary.above, summary.pct_above),
    )
    for band, count, pct in parts:
        assert pct is not None
        fig.add_trace(
            go.Bar(
                name=BAND_LABELS[band],
                x=[pct * 100],
                y=[""],
                orientation="h",
                marker_color=BAND_COLORS[band],
                text=[f"{count} · {pct:.0%}"],
                textposition="inside",
                textfont={"color": _ON_BAND_TEXT, "size": 12},
                hovertemplate=f"{BAND_LABELS[band]}: {count} mediciones ({pct:.1%})<extra></extra>",
            )
        )
    _style_stacked_bar(fig, summary.label)
    return fig


def sensor_bands_figure(tir: TirResult) -> go.Figure | None:
    """Tiempo estimado del sensor bajo / dentro / sobre el rango; ``None`` si faltan datos."""
    if tir.status != "ok" or tir.pct_below is None:
        return None
    assert tir.pct_in_range is not None and tir.pct_above is not None
    fig = go.Figure()
    for band, pct, minutes in (
        (Band.BELOW, tir.pct_below, tir.below_minutes),
        (Band.IN_RANGE, tir.pct_in_range, tir.in_range_minutes),
        (Band.ABOVE, tir.pct_above, tir.above_minutes),
    ):
        fig.add_trace(
            go.Bar(
                name=BAND_LABELS[band],
                x=[pct * 100],
                y=[""],
                orientation="h",
                marker_color=BAND_COLORS[band],
                text=[f"{pct:.0%} · {pct * 24:.1f} h/día"],
                textposition="inside",
                textfont={"color": _ON_BAND_TEXT, "size": 12},
                hovertemplate=(
                    f"{BAND_LABELS[band]}: {pct:.1%} del tiempo cubierto "
                    f"(≈ {minutes / 60:.1f} h)<extra></extra>"
                ),
            )
        )
    _style_stacked_bar(fig, f"{tir.label} · cobertura {tir.coverage:.0%}")
    return fig


def _style_stacked_bar(fig: go.Figure, title: str) -> None:
    fig.update_layout(
        barmode="stack",
        title={"text": title, "font": {"size": 12}},
        height=130,
        margin={"l": 10, "r": 10, "t": 34, "b": 30},
        font={"size": 12},
        # Sin marcas del eje: cada tramo ya muestra su cantidad y porcentaje.
        xaxis={"range": [0, 100], "showticklabels": False, "gridcolor": "rgba(150,160,175,0.15)"},
        yaxis={"showticklabels": False},
        legend={"orientation": "h", "yanchor": "top", "y": -0.02, "xanchor": "left", "x": 0},
    )


def sensor_histogram_figure(bins: list[HistogramBin], low: int, high: int) -> go.Figure:
    """Distribución de las lecturas del sensor, con cada lectura pintada según SU clase.

    Una barra que cruza un límite del rango (p. ej. 60–79 con mínimo 70) se apila en colores:
    nunca se pinta entera por la clase de su punto medio.
    """
    centers = [(b.start + b.end - 1) / 2 for b in bins]
    fig = go.Figure()
    for band, counts in (
        (Band.BELOW, [b.below for b in bins]),
        (Band.IN_RANGE, [b.in_range for b in bins]),
        (Band.ABOVE, [b.above for b in bins]),
    ):
        fig.add_trace(
            go.Bar(
                name=BAND_LABELS[band],
                x=centers,
                y=counts,
                width=[b.end - b.start for b in bins],
                marker_color=BAND_COLORS[band],
                customdata=[(b.start, b.end - 1) for b in bins],
                hovertemplate=(
                    f"%{{customdata[0]}}–%{{customdata[1]}} mg/dL · {BAND_LABELS[band]}: "
                    "%{y} lecturas<extra></extra>"
                ),
            )
        )
    for limit in (low, high):
        fig.add_vline(x=limit, line_dash="dash", line_color="#555", line_width=1)
    fig.update_layout(
        barmode="stack",
        title={"text": "Distribución de las lecturas del sensor", "font": {"size": 14}},
        height=280,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        font={"size": 12},
        xaxis={"title": "Glucosa (mg/dL)"},
        yaxis={"title": "Lecturas", "gridcolor": "rgba(150,160,175,0.15)"},
        bargap=0.05,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    return fig
