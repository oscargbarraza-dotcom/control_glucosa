"""Las fechas de Android son texto ISO 8601 sin zona (hora local de Chile)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from glucosa.data.timeutil import SANTIAGO, parse_timestamp, to_santiago, wall_clock_issue

CHILE = ZoneInfo("America/Santiago")


def test_naive_timestamp_is_interpreted_as_santiago_local_time():
    parsed = parse_timestamp("2026-08-07T21:59:54.000")
    assert parsed == datetime(2026, 8, 7, 21, 59, 54, tzinfo=CHILE)
    assert parsed.tzinfo is not None


def test_original_wall_clock_is_preserved_for_naive_input():
    parsed = parse_timestamp("2026-08-07T21:59:54.123456")
    assert (parsed.hour, parsed.minute, parsed.second) == (21, 59, 54)
    assert parsed.microsecond == 123456


def test_utc_timestamp_is_converted_to_santiago():
    # Agosto: Chile está en horario de invierno (UTC-4).
    parsed = parse_timestamp("2026-08-08T01:59:54.000Z")
    assert parsed == datetime(2026, 8, 7, 21, 59, 54, tzinfo=CHILE)
    assert parsed.hour == 21


def test_offset_timestamp_is_converted_to_santiago():
    parsed = parse_timestamp("2026-08-07T21:59:54-04:00")
    assert parsed.hour == 21


def test_summer_time_offset_is_applied_for_naive_and_utc_inputs():
    # Enero: horario de verano (UTC-3).
    naive = parse_timestamp("2026-01-15T12:00:00.000")
    utc = parse_timestamp("2026-01-15T15:00:00.000Z")
    assert naive == utc


@pytest.mark.parametrize("bad", ["", "no-es-fecha", "2026-13-45T00:00:00", None, 12345])
def test_invalid_timestamp_raises_value_error(bad):
    with pytest.raises(ValueError):
        parse_timestamp(bad)


def test_santiago_constant_is_the_chilean_zone():
    assert str(SANTIAGO) == "America/Santiago"


# ---- hora repetida (fin del horario de verano, 2026-04-04/05)
def test_ordering_and_subtraction_follow_the_real_instant_in_the_repeated_hour():
    first = parse_timestamp("2026-04-05T02:30:00Z")  # 23:30 UTC-3
    second = parse_timestamp("2026-04-05T03:10:00Z")  # 23:10 UTC-4 (una hora de pared "anterior")
    assert first < second
    assert second - first == timedelta(minutes=40)
    assert first != second
    assert len({first, second}) == 2


def test_wall_clock_is_still_preserved_in_the_repeated_hour():
    assert parse_timestamp("2026-04-05T03:10:00Z").hour == 23


def test_to_santiago_returns_a_zone_aware_value_for_display():
    shown = to_santiago(parse_timestamp("2026-08-08T01:59:54.000Z"))
    assert shown.tzinfo == SANTIAGO
    assert shown.hour == 21


# ---- entradas que no deben aceptarse
@pytest.mark.parametrize(
    "bad",
    [
        "2026-10-23",  # solo día: no se inventa una hora
        "20261023T1000",  # formato básico
        "2026-10-23T10:00",  # sin segundos: Android siempre los incluye
        "0001-01-01T00:00:00Z",  # desborda al convertir a Santiago
    ],
)
def test_ambiguous_formats_and_overflow_are_value_errors(bad):
    with pytest.raises(ValueError):
        parse_timestamp(bad)


# ---- horas locales ambiguas o inexistentes (texto sin zona)
def test_repeated_local_hour_is_reported_as_ambiguous():
    assert wall_clock_issue("2026-04-04T23:30:00.000") == "ambiguous"


def test_skipped_local_hour_is_reported_as_nonexistent():
    assert wall_clock_issue("2026-09-06T00:30:00.000") == "nonexistent"


def test_normal_and_explicit_zone_timestamps_have_no_issue():
    assert wall_clock_issue("2026-08-07T12:00:00.000") is None
    assert wall_clock_issue("2026-04-05T03:10:00.000Z") is None
