"""Cobertura y tiempo en rango (TIR) estimado a partir del historial del sensor."""

from datetime import UTC, datetime, timedelta

import pytest

from glucosa.analytics.glucose_sensor import (
    SensorSample,
    TirParams,
    compute_tir,
    samples_from_stored,
)
from glucosa.data.timeutil import SANTIAGO
from glucosa.sources.libre.models import RecordType, StoredReading, TimeFlag

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)  # 08:00 en Santiago (UTC-4)
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


def series(start, count, step_min=15, value=120):
    return [SensorSample(start + timedelta(minutes=step_min * i), value) for i in range(count)]


def loose(**overrides):
    """Parámetros con los mínimos relajados para probar la aritmética en ventanas cortas."""
    base = {"min_readings": 1, "min_coverage": 0.0}
    base.update(overrides)
    return TirParams(**base)


# ------------------------------------------------------- asignación de tiempo
def test_each_reading_represents_half_the_gap_to_each_neighbour():
    # 3 lecturas cada 15 min: 120 / 200 / 120 → la central representa 15 min, las de los
    # extremos 7,5 min dentro de la ventana (la mitad exterior cae fuera de los datos).
    samples = [
        SensorSample(T0, 60),
        SensorSample(T0 + timedelta(minutes=15), 120),
        SensorSample(T0 + timedelta(minutes=30), 200),
    ]
    result = compute_tir(
        samples, T0 - timedelta(minutes=7.5), T0 + timedelta(minutes=37.5), loose()
    )

    assert result.below_minutes == pytest.approx(15.0)  # 7,5 + 7,5 de la lectura baja
    assert result.in_range_minutes == pytest.approx(15.0)
    assert result.above_minutes == pytest.approx(15.0)
    assert result.covered_minutes == pytest.approx(45.0)
    assert result.coverage == pytest.approx(1.0)


def test_time_is_assigned_by_interval_not_by_counting_rows():
    # Lecturas en 0, 10 y 30 min (bajo, bajo, sobre). Por filas serían 2/3 bajo (66,7 %).
    # Por tiempo: r0 aporta 10 min (de -5 a 5), r1 15 min (5 a 20) y r2 17,5 min (20 a 37,5).
    samples = [
        SensorSample(T0, 60),
        SensorSample(T0 + timedelta(minutes=10), 60),
        SensorSample(T0 + timedelta(minutes=30), 200),
    ]
    result = compute_tir(samples, T0 - timedelta(minutes=5), T0 + timedelta(minutes=40), loose())

    assert result.below_minutes == pytest.approx(25.0)
    assert result.above_minutes == pytest.approx(17.5)
    assert result.covered_minutes == pytest.approx(42.5)
    assert result.pct_below == pytest.approx(25 / 42.5)  # 58,8 %, no 66,7 %


def test_no_glucose_is_interpolated_each_reading_keeps_its_own_class():
    samples = [SensorSample(T0, 60), SensorSample(T0 + timedelta(minutes=30), 200)]
    result = compute_tir(samples, T0, T0 + timedelta(minutes=30), loose())
    assert result.in_range_minutes == 0  # nunca se «cruza» por el rango entre dos lecturas
    assert result.below_minutes == pytest.approx(15.0)
    assert result.above_minutes == pytest.approx(15.0)


def test_period_boundaries_clip_the_time_of_readings_and_use_outside_neighbours():
    # La lectura previa al inicio aporta la parte de su tiempo que cae dentro de la ventana.
    samples = [
        SensorSample(T0 - timedelta(minutes=3), 60),  # representa hasta +4,5 min
        SensorSample(T0 + timedelta(minutes=12), 200),  # representa desde +4,5 min
    ]
    result = compute_tir(samples, T0, T0 + timedelta(minutes=12), loose())

    assert result.below_minutes == pytest.approx(4.5)
    assert result.above_minutes == pytest.approx(7.5)
    assert (
        result.readings_in_window == 0
    )  # ninguna lectura cae en [inicio, fin) salvo la del fin exclusivo


def test_window_end_is_exclusive_for_counting_readings():
    samples = series(T0, 5)
    result = compute_tir(samples, T0, T0 + timedelta(minutes=60), loose())
    assert result.readings_in_window == 4  # 0, 15, 30, 45; la de +60 queda fuera


# ------------------------------------------------------------- interrupciones
def test_gap_of_exactly_30_minutes_is_not_an_interruption_and_gets_its_time():
    samples = [SensorSample(T0, 120), SensorSample(T0 + timedelta(minutes=30), 120)]
    result = compute_tir(
        samples, T0 - timedelta(minutes=7.5), T0 + timedelta(minutes=37.5), loose()
    )
    assert result.interruptions == ()
    # 7,5 (borde) + 15 + 15 + 7,5 (borde): el hueco de 30 min se reparte entre ambas lecturas
    assert result.covered_minutes == pytest.approx(45.0)
    assert result.coverage == pytest.approx(1.0)


def test_gap_over_30_minutes_is_an_interruption_and_no_time_is_attributed_to_it():
    samples = [SensorSample(T0, 120), SensorSample(T0 + timedelta(minutes=60), 120)]
    result = compute_tir(
        samples, T0 - timedelta(minutes=7.5), T0 + timedelta(minutes=67.5), loose()
    )

    # Cada lectura representa como máximo ±7,5 min: 30 min de los 60 quedan sin atribuir.
    assert result.covered_minutes == pytest.approx(30.0)
    assert result.window_minutes == pytest.approx(75.0)
    assert len(result.interruptions) == 1
    assert result.interruptions[0].minutes == pytest.approx(60.0)
    assert result.longest_gap_minutes == pytest.approx(60.0)


def test_gap_is_measured_in_real_time_not_wall_clock_across_the_dst_change():
    # 2026-09-06 00:00 → 01:00 local no existe: 23:52 y 01:07 están separadas por 15 min reales.
    before = datetime(2026, 9, 5, 23, 52, tzinfo=SANTIAGO).astimezone(UTC)
    after = datetime(2026, 9, 6, 1, 7, tzinfo=SANTIAGO).astimezone(UTC)
    assert after - before == timedelta(minutes=15)

    result = compute_tir(
        [SensorSample(before, 120), SensorSample(after, 120)],
        before - timedelta(minutes=7.5),
        after + timedelta(minutes=7.5),
        loose(),
    )
    assert result.interruptions == ()
    assert result.covered_minutes == pytest.approx(30.0)


# ------------------------------------------------------- cobertura del período
def test_coverage_counts_days_without_readings_against_the_requested_period():
    day1 = series(T0, 96)  # un día completo de lecturas
    result = compute_tir(
        day1, T0 - timedelta(minutes=7.5), T0 - timedelta(minutes=7.5) + 3 * DAY, loose()
    )

    assert result.coverage == pytest.approx(1 / 3, abs=0.01)
    assert result.days_without_readings == 2


def test_full_day_of_regular_readings_gives_full_coverage_and_correct_percentages():
    samples = series(T0, 96, value=120)
    start = T0 - timedelta(minutes=7.5)
    result = compute_tir(samples, start, start + DAY)

    assert result.status == "ok"
    assert result.coverage == pytest.approx(1.0)
    assert result.pct_in_range == pytest.approx(1.0)
    assert result.estimated is False
    assert result.in_range_hours_per_day == pytest.approx(24.0)
    assert "estimado" in result.label.lower() and "libreview" in result.label.lower()


def test_estimated_flag_is_set_when_coverage_is_below_100_percent():
    start = T0 - timedelta(minutes=7.5)
    result = compute_tir(series(T0, 96), start, start + timedelta(hours=30))  # 80 % de cobertura
    assert result.status == "ok" and result.estimated is True
    assert result.coverage == pytest.approx(0.8)


# --------------------------------------------------------- datos insuficientes
@pytest.mark.parametrize(
    ("count", "window", "reason"),
    [
        (0, DAY, "sin_lecturas"),
        (95, DAY, "lecturas_insuficientes"),  # < 96 lecturas
        (96, 2 * DAY, "cobertura_insuficiente"),  # 96 lecturas pero ~50 % de cobertura
    ],
)
def test_insufficient_data_is_reported_instead_of_a_number(count, window, reason):
    start = T0 - timedelta(minutes=7.5)
    result = compute_tir(series(T0, count), start, start + window)
    assert result.status == "insufficient"
    assert result.reason == reason
    assert result.pct_in_range is None and result.in_range_hours_per_day is None


def test_exactly_96_readings_and_70_percent_coverage_are_enough():
    start = T0 - timedelta(minutes=7.5)
    samples = series(T0, 96)
    window = timedelta(minutes=1440 / 0.70)  # 96 lecturas cubren 1440 min → 70 % exacto
    result = compute_tir(samples, start, start + window)
    assert result.status == "ok"
    assert result.coverage == pytest.approx(0.70, abs=1e-6)


# ------------------------------------------------------------ rango configurable
@pytest.mark.parametrize(
    ("value", "klass"),
    [(69, "below"), (70, "in"), (180, "in"), (181, "above")],
)
def test_range_limits_are_inclusive_and_consistent(value, klass):
    result = compute_tir(
        [SensorSample(T0, value)], T0 - timedelta(minutes=7.5), T0 + timedelta(minutes=7.5), loose()
    )
    minutes = {
        "below": result.below_minutes,
        "in": result.in_range_minutes,
        "above": result.above_minutes,
    }
    assert minutes[klass] == pytest.approx(15.0)
    assert sum(minutes.values()) == pytest.approx(15.0)


def test_custom_range_is_applied_and_validated():
    sample = [SensorSample(T0, 100)]
    window = (T0 - timedelta(minutes=7.5), T0 + timedelta(minutes=7.5))
    custom = compute_tir(sample, *window, loose(low=110, high=140))
    assert custom.below_minutes == pytest.approx(15.0)
    with pytest.raises(ValueError):
        TirParams(low=180, high=70)
    with pytest.raises(ValueError):
        compute_tir(sample, window[1], window[0], loose())  # ventana invertida


def test_unsorted_input_gives_the_same_result():
    start = T0 - timedelta(minutes=7.5)
    ordered = series(T0, 96)
    shuffled = list(reversed(ordered))
    assert compute_tir(ordered, start, start + DAY) == compute_tir(shuffled, start, start + DAY)


# --------------------------------------------------------------- adaptador
def test_only_historic_readings_become_sensor_samples():
    stored = [
        StoredReading(
            "d", "2026-10-20T08:00", T0, -240, TimeFlag.NORMAL, RecordType.HISTORIC, 100, 1
        ),
        StoredReading(
            "d",
            "2026-10-20T08:05",
            T0 + timedelta(minutes=5),
            -240,
            TimeFlag.NORMAL,
            RecordType.SCAN,
            300,
            1,
        ),
    ]
    samples = samples_from_stored(stored)
    assert samples == [SensorSample(T0, 100)]
