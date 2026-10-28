"""Estilo compacto del módulo Glucosa (inspirado en un dashboard operativo de Power BI).

Solo ajusta espacios y tamaños: el CSS es una constante estática, sin ningún dato del usuario, y se
inyecta con ``st.html`` (no se usa ``unsafe_allow_html`` ni se interpola texto). Los colores del tema
(oscuro, controles en gris neutro) están en ``.streamlit/config.toml``.
"""

import streamlit as st

# Selectores por ``data-testid``: son los estables de Streamlit (las clases emotion cambian).
COMPACT_CSS = """
<style>
.block-container {
  padding: 2.4rem 1.4rem 1rem 1.4rem !important;
  max-width: 100% !important;
}
[data-testid="stMain"] [data-testid="stVerticalBlock"] { gap: 0.6rem; }
[data-testid="stMain"] h1 {
  font-size: 1.6rem !important; line-height: 1.2 !important; padding: 0 !important; margin: 0 !important;
}
[data-testid="stMain"] h3 {
  font-size: 1rem !important; font-weight: 600 !important; line-height: 1.3 !important;
  padding: 0.45rem 0 0.4rem 0 !important; margin: 0 !important; letter-spacing: 0.01em;
}
[data-testid="stMain"] h3, [data-testid="stMain"] h3 * { text-decoration: none !important; }
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(7.2rem, 1fr)); gap: 0.5rem; }
.kpi {
  border: 1px solid rgba(150, 160, 175, 0.28); border-radius: 0.5rem;
  background-color: rgba(255, 255, 255, 0.025); padding: 0.4rem 0.7rem 0.4rem 0.7rem; min-width: 0;
  overflow: hidden; background-repeat: no-repeat; background-size: 100% 3px; background-position: top;
}
.kpi-firebase .kpi { background-image: linear-gradient(#B388EB, #B388EB); }
.kpi-libreview .kpi { background-image: linear-gradient(#4DA3FF, #4DA3FF); }
.kpi-label {
  font-size: 0.74rem; opacity: 0.78; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.kpi-value { font-size: 1.4rem; font-weight: 600; line-height: 1.25; white-space: nowrap; }
.kpi-unit { font-size: 0.72rem; font-weight: 400; opacity: 0.7; margin-left: 0.25rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.55rem; }
[data-testid="stSidebar"] h3 { font-size: 1rem !important; margin: 0 0 0.3rem 0 !important; padding: 0 !important; }
[data-testid="stSidebar"] .stButton button, [data-testid="stSidebar"] [data-testid="stPopover"] button {
  min-height: 2rem; padding: 0.1rem 0.6rem;
}
[data-testid="stCaptionContainer"] { line-height: 1.35; }
[data-testid="stExpander"] summary { padding: 0.35rem 0.75rem; }
</style>
"""


def inject_compact_style() -> None:
    st.html(COMPACT_CSS)
