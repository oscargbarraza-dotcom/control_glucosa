"""Script que ejecuta AppTest: monta la página Glucosa con fuentes simuladas."""

import os

import streamlit as st

from glucosa.ui.glucose_page import render_glucose_page
from tests.glucose_fakes import NOW, FakeSources

st.set_page_config(layout="wide")
sources = st.session_state.setdefault(
    "fuentes", FakeSources(os.environ.get("GLUCOSA_TEST_SCENARIO", "full"))
)
render_glucose_page(sources, now=lambda: NOW)
