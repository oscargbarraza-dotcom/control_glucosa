"""Script que ejecuta AppTest: monta la página Alimentación con fuentes simuladas."""

import os
from datetime import datetime

import streamlit as st

from glucosa.ui.meal_page import render_meal_page
from tests.meal_fakes import NOW, FakeMealSources

st.set_page_config(layout="wide")
sources = st.session_state.setdefault(
    "fuentes", FakeMealSources(os.environ.get("GLUCOSA_TEST_SCENARIO", "full"))
)
now = datetime.fromisoformat(os.environ.get("GLUCOSA_TEST_NOW", NOW.isoformat()))
render_meal_page(sources, now=lambda: now)
