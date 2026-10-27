"""Tarjetas de indicadores (KPI) compactas y responsivas, estilo dashboard operativo.

Se generan como HTML con una cuadrícula CSS que reparte las tarjetas según el ancho disponible
(``auto-fit``): nunca se cortan los valores ni hay desplazamiento horizontal. Todo el texto se
escapa; los valores son números y rótulos que decide el código, nunca texto libre del usuario.
Sin dependencias de Streamlit para poder probarlo.
"""

import html
from dataclasses import dataclass
from enum import StrEnum


class Tone(StrEnum):
    FIREBASE = "firebase"  # violeta
    LIBREVIEW = "libreview"  # azul


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    unit: str = ""
    tip: str = ""


def _card(kpi: Kpi) -> str:
    label, value = html.escape(kpi.label), html.escape(kpi.value)
    unit = f' <span class="kpi-unit">{html.escape(kpi.unit)}</span>' if kpi.unit else ""
    title = f' title="{html.escape(kpi.tip, quote=True)}"' if kpi.tip else ""
    return (
        f'<div class="kpi"{title}><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}{unit}</div></div>'
    )


def kpi_grid_html(items: list[Kpi], tone: Tone) -> str:
    cards = "".join(_card(item) for item in items)
    return f'<div class="kpi-grid kpi-{tone.value}">{cards}</div>'
