"""Punto de entrada Streamlit: navegación y módulos disponibles.

* **Glucosa**: módulo implementado (Fase 4, Etapa C).
* **Alimentación**: módulo implementado (Etapa D4).
* Resto de secciones: pendientes de las fases siguientes.

El inicio de sesión de Firebase se hace por línea de comandos
(``python -m glucosa.login login``); la interfaz usa la sesión guardada.
"""

import streamlit as st

from glucosa.config import config_from_environment
from glucosa.ui.access import require_access
from glucosa.ui.glucose_page import render_glucose_page
from glucosa.ui.glucose_sources import DefaultGlucoseSources
from glucosa.ui.meal_page import render_meal_page
from glucosa.ui.navigation import PAGES, PLANNED_PHASE


def main() -> None:
    st.set_page_config(page_title="_glucosa", page_icon="🩸", layout="wide")
    require_access()  # antes de leer configuración, datos o mostrar nada
    config = config_from_environment()

    st.sidebar.title("_glucosa")
    page = st.sidebar.radio("Navegación", PAGES)
    st.sidebar.caption("Solo lectura · datos de SeguimientoGlucosa")

    if page in ("Glucosa", "Alimentación"):
        # Se conserva la misma instancia entre recargas (reutiliza la sesión de Firebase).
        sources = st.session_state.setdefault("glucosa_fuentes", DefaultGlucoseSources(config))
        (render_glucose_page if page == "Glucosa" else render_meal_page)(sources)
        return

    if not config.api_key:
        st.warning(
            "Falta configuración: define GLUCOSA_FIREBASE_API_KEY en tu archivo .env "
            "(ver README.md)."
        )
    st.info("La sesión se inicia por línea de comandos: python -m glucosa.login login")
    st.header(page)
    st.caption(f"Pantalla pendiente de implementación ({PLANNED_PHASE[page]}).")


main()
