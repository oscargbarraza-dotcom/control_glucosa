"""Tarjetas de hitos de Alimentación: etiquetas cortas, grupos por hito y sin recalcular nada."""

import re

import pytest

from glucosa.analytics.meal_dashboard import MilestoneKpi
from glucosa.analytics.meal_readings import ReadingSource as S
from glucosa.ui.glucose_kpi import Tone
from glucosa.ui.meal_kpi import MILESTONE_CSS, milestone_groups, milestone_groups_html

MAX_LABEL_CHARS = 18  # cabe en una tarjeta de ~7 rem sin truncarse


def kpis(measured=12, eligible=23, pending=2, not_registered=11, tolerance=10):
    return {
        minutes: MilestoneKpi(minutes, tolerance, eligible, measured, not_registered, pending)
        for minutes in (60, 90)
    }


def test_manual_cards_use_the_short_approved_labels_in_two_groups_of_three():
    groups = milestone_groups({S.MANUAL: kpis()})

    assert [[c.label for c in group] for group in groups] == [
        ["Manual +60", "Elegibles +60", "Pendientes +60"],
        ["Manual +90", "Elegibles +90", "Pendientes +90"],
    ]


def test_numerator_denominator_and_pending_stay_in_separate_cards_unchanged():
    first = milestone_groups({S.MANUAL: kpis(measured=12, eligible=23, pending=2)})[0]

    assert [c.value for c in first] == ["12 de 23", "23", "2"]


def test_the_tooltips_carry_the_explanation_that_the_short_labels_drop():
    first = milestone_groups({S.MANUAL: kpis(tolerance=15)})[0]

    assert "±15 min" in first[0].tip and "11 sin medición registrada" in first[0].tip
    assert "ya ocurrió" in first[1].tip and "aún no ocurre" in first[2].tip


def test_imported_cards_have_their_own_distinguishable_labels_after_the_manual_ones():
    groups = milestone_groups({S.MANUAL: kpis(), S.IMPORTED: kpis()})
    labels = [c.label for group in groups for c in group]

    assert len(groups) == 4 and len(set(labels)) == len(labels)
    assert groups[2][0].label == "Importada +60"


def test_no_label_is_long_enough_to_be_truncated():
    groups = milestone_groups({S.MANUAL: kpis(), S.IMPORTED: kpis()})

    assert max(len(c.label) for group in groups for c in group) <= MAX_LABEL_CHARS


def test_without_sources_there_are_no_groups():
    assert milestone_groups({}) == []


def test_the_html_wraps_each_group_in_its_own_three_column_grid():
    html = milestone_groups_html(milestone_groups({S.MANUAL: kpis()}), Tone.FIREBASE)

    assert html.count('class="kpi-grid kpi-firebase"') == 2
    assert len(re.findall(r'<div class="kpi"', html)) == 6
    assert html.count('<div class="meal-hitos">') == 1


def test_the_css_stacks_the_groups_on_narrow_screens_and_keeps_three_columns_per_group():
    assert "auto-fit" in MILESTONE_CSS and "min(100%" in MILESTONE_CSS
    assert "repeat(3" in MILESTONE_CSS
    assert "<script" not in MILESTONE_CSS.lower() and "http" not in MILESTONE_CSS


@pytest.mark.parametrize("measured", [0, 23])
def test_boundary_counts_render_as_plain_numbers(measured):
    first = milestone_groups({S.MANUAL: kpis(measured=measured)})[0]

    assert first[0].value == f"{measured} de 23"
