"""Vista unificada de glucosa, períodos y filtros (lógica pura)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from glucosa.analytics.glucose_filters import PERIOD_OPTIONS, filter_points, resolve_period
from glucosa.analytics.glucose_view import (
    Band,
    GlucosePoint,
    Kind,
    Source,
    classify,
    manual_points,
    sensor_points,
)
from glucosa.data.timeutil import SANTIAGO, parse_timestamp
from glucosa.models.records import GlucoseMoment, GlucoseRecord, Origin
from glucosa.sources.libre.models import RecordType, StoredReading, TimeFlag

# 26-10-2026 15:00 hora de Santiago (UTC-3 en octubre)
NOW = datetime(2026, 10, 26, 15, 0, tzinfo=SANTIAGO).astimezone(UTC)


def local(day: str, hm: str = "00:00") -> datetime:
    y, m, d = (int(x) for x in day.split("-"))
    h, mi = (int(x) for x in hm.split(":"))
    return datetime(y, m, d, h, mi, tzinfo=SANTIAGO).astimezone(UTC)


# ------------------------------------------------------------------ clasificación
@pytest.mark.parametrize(
    ("value", "band"),
    [(69, Band.BELOW), (70, Band.IN_RANGE), (180, Band.IN_RANGE), (181, Band.ABOVE)],
)
def test_classification_limits_are_inclusive_and_consistent(value, band):
    assert classify(value, 70, 180) is band


# --------------------------------------------------------------------- períodos
def test_period_options_are_the_ones_requested():
    assert PERIOD_OPTIONS == (
        "Hoy",
        "Últimos 7 días",
        "Últimos 30 días",
        "Últimos 3 meses",
        "Últimos 6 meses",
        "Últimos 12 meses",
        "Rango personalizado",
    )


@pytest.mark.parametrize(
    ("option", "first_day"),
    [
        ("Hoy", date(2026, 10, 26)),
        ("Últimos 7 días", date(2026, 10, 20)),
        ("Últimos 30 días", date(2026, 9, 27)),
        ("Últimos 3 meses", date(2026, 7, 27)),
        ("Últimos 6 meses", date(2026, 4, 27)),
        ("Últimos 12 meses", date(2025, 10, 27)),
    ],
)
def test_relative_periods_start_at_local_midnight_and_end_now(option, first_day):
    period = resolve_period(option, NOW)
    assert period.start == local(first_day.isoformat())
    assert period.end == NOW  # no se penaliza la cobertura con horas futuras
    assert period.first_day == first_day and period.last_day == date(2026, 10, 26)


def test_month_arithmetic_clamps_to_the_last_day_of_shorter_months():
    now = datetime(2026, 5, 31, 12, 0, tzinfo=SANTIAGO).astimezone(UTC)
    # 3 meses antes del 31-05 es el 28-02 (2026 no es bisiesto) → la ventana empieza el 01-03
    assert resolve_period("Últimos 3 meses", now).first_day == date(2026, 3, 1)


def test_custom_period_covers_whole_local_days_and_end_is_exclusive():
    period = resolve_period("Rango personalizado", NOW, date(2026, 10, 1), date(2026, 10, 3))
    assert period.start == local("2026-10-01")
    assert period.end == local("2026-10-04")
    assert (period.first_day, period.last_day) == (date(2026, 10, 1), date(2026, 10, 3))


def test_custom_period_including_today_is_clipped_to_now():
    period = resolve_period("Rango personalizado", NOW, date(2026, 10, 25), date(2026, 10, 26))
    assert period.end == NOW


def test_period_over_the_summer_time_change_is_23_hours_long():
    period = resolve_period("Rango personalizado", NOW, date(2026, 9, 6), date(2026, 9, 6))
    assert period.end - period.start == timedelta(hours=23)


def test_invalid_custom_periods_are_rejected():
    with pytest.raises(ValueError, match="fechas"):
        resolve_period("Rango personalizado", NOW)
    with pytest.raises(ValueError, match="posterior"):
        resolve_period("Rango personalizado", NOW, date(2026, 10, 5), date(2026, 10, 1))
    with pytest.raises(ValueError, match="Período"):
        resolve_period("Siempre", NOW)


# ----------------------------------------------------------- vista unificada
def record(uuid, when, value, moment=GlucoseMoment.NOW, comment=None):
    return GlucoseRecord(uuid, value, moment, parse_timestamp(when), comment, Origin.MANUAL)


def stored(minutes, value, kind=RecordType.HISTORIC):
    instant = datetime(2026, 10, 20, 12, 0, tzinfo=UTC) + timedelta(minutes=minutes)
    return StoredReading("d", "x", instant, -240, TimeFlag.NORMAL, kind, value, 1)


def test_points_keep_source_and_kind_for_each_origin():
    manual = manual_points([record("a", "2026-10-20T08:00:00", 120, comment="nota")])
    sensor = sensor_points([stored(0, 100), stored(1, 101, RecordType.SCAN)])

    assert (manual[0].source, manual[0].kind) == (Source.FIREBASE, Kind.MANUAL)
    assert manual[0].comment == "nota" and manual[0].moment is GlucoseMoment.NOW
    assert [(p.source, p.kind) for p in sensor] == [
        (Source.LIBREVIEW, Kind.SENSOR),
        (Source.LIBREVIEW, Kind.SCAN),
    ]
    assert sensor[0].moment is None and sensor[0].comment is None


# ------------------------------------------------------------------- filtros
def sample_points():
    return [
        GlucosePoint(
            local("2026-10-20", "08:00"), 60, Source.FIREBASE, Kind.MANUAL, GlucoseMoment.WAKING_UP
        ),
        GlucosePoint(
            local("2026-10-21", "08:00"), 120, Source.FIREBASE, Kind.MANUAL, GlucoseMoment.NOW
        ),
        GlucosePoint(
            local("2026-10-22", "08:00"),
            250,
            Source.FIREBASE,
            Kind.MANUAL,
            GlucoseMoment.AFTER_LUNCH,
        ),
        GlucosePoint(local("2026-10-21", "09:00"), 130, Source.LIBREVIEW, Kind.SENSOR),
        GlucosePoint(local("2026-10-21", "09:05"), 300, Source.LIBREVIEW, Kind.SCAN),
    ]


def test_period_filter_is_inclusive_at_start_and_exclusive_at_end():
    period = resolve_period("Rango personalizado", NOW, date(2026, 10, 21), date(2026, 10, 21))
    values = [p.value for p in filter_points(sample_points(), period=period)]
    assert values == [120, 130, 300]


def test_source_and_kind_filters_separate_firebase_from_libreview():
    points = sample_points()
    assert {p.source for p in filter_points(points, sources={Source.FIREBASE})} == {Source.FIREBASE}
    assert [p.kind for p in filter_points(points, kinds={Kind.SCAN})] == [Kind.SCAN]


def test_classification_filter_uses_the_target_range():
    values = [p.value for p in filter_points(sample_points(), bands={Band.ABOVE}, low=70, high=180)]
    assert values == [250, 300]
    values = [p.value for p in filter_points(sample_points(), bands={Band.BELOW, Band.IN_RANGE})]
    assert values == [60, 120, 130]


def test_declared_moment_filter_only_applies_to_manual_measurements():
    kept = filter_points(sample_points(), moments={GlucoseMoment.NOW})
    # La manual «Ahora» y TODAS las del sensor (que no tienen momento) se conservan.
    assert [p.value for p in kept] == [120, 130, 300]
    assert filter_points(sample_points(), moments=set()) == [
        p for p in sample_points() if p.kind is not Kind.MANUAL
    ]


def test_no_filters_returns_everything_in_the_original_order():
    assert filter_points(sample_points()) == sample_points()
