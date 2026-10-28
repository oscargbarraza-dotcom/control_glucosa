"""Indicadores de mediciones manuales (Firebase) y del sensor (LibreView), siempre por separado."""

from datetime import UTC, datetime, timedelta

import pytest

from glucosa.analytics.glucose_filters import Period
from glucosa.analytics.glucose_sensor import SensorSample
from glucosa.analytics.glucose_summaries import (
    MANUAL_PERCENT_LABEL,
    histogram,
    summarize_by_moment,
    summarize_manual,
    summarize_sensor,
)
from glucosa.analytics.glucose_view import GlucosePoint, Kind, Source
from glucosa.models.records import GlucoseMoment

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def manual(offset_min, value, moment=GlucoseMoment.NOW):
    return GlucosePoint(
        T0 + timedelta(minutes=offset_min), value, Source.FIREBASE, Kind.MANUAL, moment
    )


def sensor_point(offset_min, value, kind=Kind.SENSOR):
    return GlucosePoint(T0 + timedelta(minutes=offset_min), value, Source.LIBREVIEW, kind)


def period(start_min, end_min):
    start, end = T0 + timedelta(minutes=start_min), T0 + timedelta(minutes=end_min)
    return Period(start, end, "Rango personalizado", start.date(), end.date())


# ----------------------------------------------------------------- manuales
def test_manual_summary_counts_statistics_and_percentages():
    points = [manual(0, 60), manual(10, 100), manual(20, 180), manual(30, 181), manual(40, 300)]

    s = summarize_manual(points, low=70, high=180)

    assert s.count == 5
    assert (s.minimum, s.maximum) == (60, 300)
    assert s.mean == pytest.approx(164.2)
    assert s.median == 180
    assert (s.below, s.in_range, s.above) == (1, 2, 2)
    assert (s.pct_below, s.pct_in_range, s.pct_above) == (0.2, 0.4, 0.4)
    assert s.last_value == 300 and s.last_instant == T0 + timedelta(minutes=40)
    assert s.label == MANUAL_PERCENT_LABEL


def test_last_measurement_is_the_latest_by_time_not_by_position():
    s = summarize_manual([manual(50, 111), manual(0, 222), manual(20, 333)], 70, 180)
    assert s.last_value == 111


def test_only_manual_measurements_are_summarized_even_if_other_kinds_are_passed():
    s = summarize_manual(
        [manual(0, 100), sensor_point(5, 400), sensor_point(6, 401, Kind.SCAN)], 70, 180
    )
    assert s.count == 1 and s.maximum == 100


def test_empty_manual_summary_has_no_numbers_instead_of_zeros():
    s = summarize_manual([], 70, 180)
    assert s.count == 0
    assert s.mean is None and s.median is None and s.last_value is None
    assert s.pct_in_range is None


def test_summary_by_declared_moment_keeps_enum_order_and_counts():
    points = [
        manual(0, 100, GlucoseMoment.AFTER_LUNCH),
        manual(1, 200, GlucoseMoment.AFTER_LUNCH),
        manual(2, 90, GlucoseMoment.WAKING_UP),
        manual(3, 120, GlucoseMoment.NOW),
    ]

    rows = summarize_by_moment(points, 70, 180)

    assert [r.moment for r in rows] == [
        GlucoseMoment.NOW,
        GlucoseMoment.WAKING_UP,
        GlucoseMoment.AFTER_LUNCH,
    ]
    after_lunch = rows[-1]
    assert after_lunch.label == "Después almuerzo"
    assert (after_lunch.count, after_lunch.mean, after_lunch.pct_in_range) == (2, 150.0, 0.5)


def test_moments_are_never_inferred_for_measurements_without_one():
    rows = summarize_by_moment([manual(0, 100, None)], 70, 180)
    assert rows[0].moment is None and rows[0].label == "Sin momento declarado"


# ------------------------------------------------------------------- sensor
def regular(count, value=120, start=0, step=15):
    return [SensorSample(T0 + timedelta(minutes=start + step * i), value) for i in range(count)]


def test_sensor_summary_reports_statistics_range_of_data_and_tir():
    samples = regular(192)  # 2 días a 15 min
    p = period(-7.5, -7.5 + 2 * 1440)

    s = summarize_sensor(samples, p, low=70, high=180)

    assert s.count == 192
    assert (s.mean, s.median, s.minimum, s.maximum) == (120, 120, 120, 120)
    assert s.first_in_period == samples[0].instant and s.last_in_period == samples[-1].instant
    assert s.first_available == samples[0].instant and s.last_available == samples[-1].instant
    assert s.tir.status == "ok" and s.tir.pct_in_range == pytest.approx(1.0)
    assert s.tir.coverage == pytest.approx(1.0)


def test_available_range_covers_the_whole_dataset_not_just_the_period():
    samples = regular(192)
    p = period(-7.5, -7.5 + 1440)  # solo el primer día

    s = summarize_sensor(samples, p, 70, 180)

    assert s.count == 96
    assert s.last_available == samples[-1].instant
    assert s.last_in_period < s.last_available


def test_sensor_summary_without_readings_reports_insufficient_data_not_zeros():
    s = summarize_sensor([], period(0, 1440), 70, 180)
    assert s.count == 0 and s.mean is None and s.first_available is None
    assert s.tir.status == "insufficient" and s.tir.reason == "sin_lecturas"
    assert s.tir.pct_in_range is None


def test_sensor_uses_the_requested_target_range_for_tir():
    samples = regular(96, value=100)
    p = period(-7.5, -7.5 + 1440)
    assert summarize_sensor(samples, p, 70, 180).tir.pct_in_range == pytest.approx(1.0)
    assert summarize_sensor(samples, p, 110, 180).tir.pct_below == pytest.approx(1.0)


def test_interruptions_are_exposed_for_the_ui():
    samples = regular(48) + regular(48, start=48 * 15 + 120)  # hueco de 2 h
    p = period(-7.5, -7.5 + 1440 + 120)
    s = summarize_sensor(samples, p, 70, 180)
    assert len(s.tir.interruptions) == 1 and s.tir.interruptions[0].minutes > 100


def test_histogram_bins_cover_all_values_and_sum_to_the_count():
    bins = histogram([45, 50, 61, 120, 121, 199], width=20)
    assert sum(b.count for b in bins) == 6
    assert bins[0].start == 40 and bins[-1].end == 200
    assert all(b.end - b.start == 20 for b in bins)
    assert histogram([], width=20) == []
