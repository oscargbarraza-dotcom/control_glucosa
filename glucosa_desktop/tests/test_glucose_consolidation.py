"""A-1: consolidación del historial cuando hay varios dispositivos (una sola implementación)."""

from datetime import UTC, datetime, timedelta

import pytest

from glucosa.analytics.glucose_sensor import (
    TirParams,
    compute_tir,
    consolidate_history,
    samples_from_stored,
)
from glucosa.sources.libre.models import RecordType, StoredReading, TimeFlag

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def reading(device, minutes, value, record_type=RecordType.HISTORIC, seconds=0):
    instant = T0 + timedelta(minutes=minutes, seconds=seconds)
    return StoredReading(device, "x", instant, -240, TimeFlag.NORMAL, record_type, value, 1)


def test_the_same_reading_from_two_devices_is_counted_once():
    stored = [reading("a", 0, 110), reading("b", 0, 110)]

    result = consolidate_history(stored)

    assert len(result.readings) == 1
    assert result.duplicates == 1
    assert result.conflict_minutes == 0


def test_overlapping_series_keep_one_reading_per_minute():
    first = [reading("a", 15 * i, 100 + i) for i in range(6)]
    second = [reading("b", 15 * i, 100 + i) for i in range(3, 9)]  # se solapa en 3 lecturas

    result = consolidate_history(first + second)

    assert len(result.readings) == 9
    assert result.duplicates == 3
    assert result.conflict_minutes == 0


def test_same_minute_with_different_values_is_never_merged_and_is_reported():
    stored = [reading("a", 0, 110), reading("b", 0, 150)]

    result = consolidate_history(stored)

    assert sorted(r.glucose_mg_dl for r in result.readings) == [110, 150]
    assert result.duplicates == 0
    assert result.conflict_minutes == 1


def test_seconds_inside_the_same_minute_are_the_same_reading():
    stored = [reading("a", 0, 110), reading("b", 0, 110, seconds=40)]

    assert consolidate_history(stored).duplicates == 1


def test_scans_are_not_part_of_the_history():
    stored = [reading("a", 0, 110), reading("a", 0, 110, record_type=RecordType.SCAN)]

    result = consolidate_history(stored)

    assert [r.record_type for r in result.readings] == [RecordType.HISTORIC]
    assert result.duplicates == 0


def test_a_clean_series_is_returned_unchanged_and_in_order():
    stored = [reading("a", 15 * i, 100 + i) for i in range(5)]

    result = consolidate_history(stored)

    assert result.readings == tuple(stored)
    assert (result.duplicates, result.conflict_minutes) == (0, 0)


def test_samples_use_the_same_consolidation():
    stored = [reading("a", 0, 110), reading("b", 0, 110), reading("a", 15, 120)]

    samples = samples_from_stored(stored)

    assert [s.value for s in samples] == [110, 120]


def test_duplicates_do_not_inflate_the_reading_count_or_the_coverage_gate():
    # 60 lecturas reales (15 h) leídas por dos dispositivos: con duplicados parecerían 120.
    base = [reading("a", 15 * i, 120) for i in range(60)]
    doubled = base + [reading("b", 15 * i, 120) for i in range(60)]
    start, end = T0, T0 + timedelta(minutes=15 * 60)
    params = TirParams(min_readings=96, min_coverage=0.0)

    single = compute_tir(samples_from_stored(base), start, end, params)
    both = compute_tir(samples_from_stored(doubled), start, end, params)

    assert both.readings_in_window == single.readings_in_window == 60
    assert both.status == single.status == "insufficient"  # no alcanza el mínimo de 96
    assert both.coverage == pytest.approx(single.coverage)


def test_conflicting_minutes_keep_both_readings_without_double_counting_time():
    stored = [reading("a", 15 * i, 120) for i in range(8)]
    stored.append(reading("b", 30, 200))  # conflicto en el minuto 30
    params = TirParams(min_readings=1, min_coverage=0.0)

    result = compute_tir(samples_from_stored(stored), T0, T0 + timedelta(minutes=120), params)

    assert result.covered_minutes <= result.window_minutes + 1e-6
    assert result.coverage <= 1.0 + 1e-9
