"""Script de AppTest: la página Glucosa más un botón que simula la importación de un CSV.

AppTest no puede subir archivos; este botón llama a la misma función que usa el botón real
«Importar este archivo» (``_run_import``), así se comprueba que la pantalla se actualiza.
"""

import os

import streamlit as st

from glucosa.ui.glucose_page import _run_import, render_glucose_page
from tests.glucose_fakes import NOW, FakeSources

st.set_page_config(layout="wide")
sources = st.session_state.setdefault(
    "fuentes", FakeSources(os.environ.get("GLUCOSA_TEST_SCENARIO", "full"))
)
render_glucose_page(sources, now=lambda: NOW)
if st.sidebar.button("simular importación", key="simular"):
    _run_import(sources, "x.csv", b"contenido")
