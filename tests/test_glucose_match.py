"""Indicador informativo «N de M mediciones manuales coinciden con un escaneo»."""

from datetime import UTC, datetime, timedelta

import pytest

from glucosa.analytics.glucose_match import MatchParams, match_manual_to_scans
from glucosa.data.timeutil import parse_timestamp
from glucosa.models.records import GlucoseMoment, GlucoseRecord, Origin
from glucosa.sources.libre.models import RecordType, StoredReading, TimeFlag

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def manual(offset_min, value=150, uuid=None):
    when = (T0 + timedelta(minutes=offset_min)).astimezone(
        parse_timestamp("2026-10-20T12:00:00").tzinfo
    )
    return GlucoseRecord(
        uuid or f"m{offset_min}", value, GlucoseMoment.NOW, when, None, Origin.MANUAL
    )


def scan(offset_min, value=150, kind=RecordType.SCAN):
    return StoredReading(
        "dev", "x", T0 + timedelta(minutes=offset_min), -240, TimeFlag.NORMAL, kind, value, 1
    )


def test_manual_with_a_scan_of_the_same_value_nearby_is_counted():
    result = match_manual_to_scans([manual(0, 150)], [scan(3, 150)])
    assert (result.manual_total, result.matched) == (1, 1)
    assert result.label == "1 de 1 mediciones manuales coinciden con un escaneo"


def test_default_value_tolerance_is_exact():
    assert match_manual_to_scans([manual(0, 150)], [scan(1, 151)]).matched == 0
    params = MatchParams(value_tolerance_mg_dl=1)
    assert match_manual_to_scans([manual(0, 150)], [scan(1, 151)], params).matched == 1


def test_time_tolerance_is_symmetric_and_inclusive():
    assert match_manual_to_scans([manual(0)], [scan(10)]).matched == 1
    assert match_manual_to_scans([manual(0)], [scan(-10)]).matched == 1
    assert match_manual_to_scans([manual(0)], [scan(10.1)]).matched == 0
    assert (
        match_manual_to_scans(
            [manual(0)], [scan(10.1)], MatchParams(time_tolerance_minutes=15)
        ).matched
        == 1
    )


def test_any_scan_inside_the_window_can_match():
    scans = [scan(-30, 90), scan(-8, 99), scan(2, 150), scan(60, 150)]
    assert match_manual_to_scans([manual(0, 150)], scans).matched == 1


def test_only_scans_are_considered_never_the_historic_series():
    result = match_manual_to_scans([manual(0)], [scan(1, 150, RecordType.HISTORIC)])
    assert result.matched == 0


def test_a_scan_may_support_several_manual_records_and_nothing_is_merged_or_removed():
    manuals = [manual(0, 150, "a"), manual(2, 150, "b"), manual(100, 150, "c")]
    scans = [scan(1, 150)]
    snapshot = (list(manuals), list(scans))

    result = match_manual_to_scans(manuals, scans)

    assert (result.manual_total, result.matched) == (2, 2)  # "c" queda fuera del período cubierto
    assert result.outside_coverage == 1
    assert (manuals, scans) == snapshot  # entradas intactas: no se fusiona ni se elimina nada


def test_manual_records_outside_the_period_covered_by_the_export_are_not_evaluated():
    scans = [scan(-60, 100), scan(0, 150), scan(60, 160)]
    manuals = [manual(0, 150, "dentro"), manual(500, 150, "despues"), manual(-500, 90, "antes")]

    result = match_manual_to_scans(manuals, scans)

    assert (result.manual_total, result.matched, result.outside_coverage) == (1, 1, 2)
    assert result.label == (
        "1 de 1 mediciones manuales coinciden con un escaneo "
        "(2 fuera del período cubierto por la exportación)"
    )


def test_coverage_can_be_given_explicitly_from_the_whole_export():
    # La exportación cubre 12 h aunque los escaneos estén solo en un tramo.
    start, end = T0 - timedelta(hours=6), T0 + timedelta(hours=6)
    result = match_manual_to_scans([manual(240, 150)], [scan(0, 150)], coverage=(start, end))
    assert (result.manual_total, result.matched, result.outside_coverage) == (1, 0, 0)


def test_without_any_scan_nothing_can_be_evaluated():
    result = match_manual_to_scans([manual(0)], [])
    assert (result.manual_total, result.matched, result.outside_coverage) == (0, 0, 1)


def test_empty_inputs_and_invalid_tolerances():
    assert match_manual_to_scans([], [scan(0)]).matched == 0
    assert match_manual_to_scans([manual(0)], []).matched == 0
    with pytest.raises(ValueError):
        MatchParams(time_tolerance_minutes=-1)
    with pytest.raises(ValueError):
        MatchParams(value_tolerance_mg_dl=-1)
