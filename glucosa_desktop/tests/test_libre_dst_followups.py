"""Hora repetida (fin del horario de verano) y demás correcciones de la revisión de código."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from glucosa import libre_import
from glucosa.analytics.glucose_sensor import (
    SensorSample,
    compute_tir,
    samples_from_stored,
)
from glucosa.errors import LibreStoreError, SecureStoreError
from glucosa.sources.libre.csv_parser import parse_libre_csv
from glucosa.sources.libre.importer import import_libre_csv
from glucosa.sources.libre.models import RecordType, StoredReading, TimeFlag
from glucosa.sources.libre.store import LibreStore
from glucosa.storage.secure_store import EncryptedBytesStore, KeyringKeyProvider
from tests.fakes import FakeKeyring
from tests.libre_fixtures import build_csv, minute_series, row
from tests.test_libre_store import plan, reading

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def repeated_hour_rows(second_pass_values=(105, 106, 107, 108)):
    """Noche del 4 al 5 de abril de 2026: la hora 23:xx ocurre dos veces (UTC-3 y luego UTC-4)."""
    first_pass = [("23:05", 101), ("23:20", 102), ("23:35", 103), ("23:50", 104)]
    second_pass = list(zip(["23:05", "23:20", "23:35", "23:50"], second_pass_values, strict=True))
    rows = [row("hist", "04-04-2026 22:50", 100)]
    rows += [row("hist", f"04-04-2026 {t}", v) for t, v in first_pass]
    rows += [row("hist", f"04-04-2026 {t}", v) for t, v in second_pass]
    rows += [row("hist", "05-04-2026 00:05", 109)]
    return rows


# ---------------------------------------------------------------- hora repetida
def test_second_pass_of_the_repeated_hour_gets_the_later_instant():
    parsed = parse_libre_csv(build_csv(repeated_hour_rows()))

    instants = [r.instant_utc for r in parsed.readings]
    assert instants == sorted(instants) and len(set(instants)) == len(instants)
    gaps = {(b - a).total_seconds() / 60 for a, b in zip(instants, instants[1:], strict=False)}
    assert gaps == {15.0}  # 22:50 → 23:05 → … → 23:50 → 23:05(2.ª) → … → 00:05 sin saltos
    ambiguous = [r for r in parsed.readings if r.time_flag is TimeFlag.AMBIGUOUS]
    assert [r.fold for r in ambiguous] == [0, 0, 0, 0, 1, 1, 1, 1]
    assert [r.utc_offset_minutes for r in ambiguous] == [-180] * 4 + [-240] * 4


def test_the_same_resolution_works_for_a_file_in_descending_order():
    ascending = parse_libre_csv(build_csv(repeated_hour_rows()))
    descending = parse_libre_csv(build_csv(list(reversed(repeated_hour_rows()))))
    assert sorted((r.local_minute, r.fold, r.instant_utc) for r in descending.readings) == sorted(
        (r.local_minute, r.fold, r.instant_utc) for r in ascending.readings
    )


def test_both_passes_are_stored_even_when_minute_and_value_coincide(tmp_path):
    backend = FakeKeyring()
    store = LibreStore.open(tmp_path / "libre.db.enc", KeyringKeyProvider(backend=backend))
    # La 2.ª pasada repite exactamente minuto y valor de la 1.ª (101, 102, 103, 104).
    content = build_csv(repeated_hour_rows(second_pass_values=(101, 102, 103, 104)))

    summary = import_libre_csv(content, "x.csv", store, now=NOW)

    assert (summary.new, summary.repeated, summary.conflicts) == (10, 0, 0)
    assert len(store.readings()) == 10
    # Reimportar sigue siendo idempotente.
    again = import_libre_csv(content, "x.csv", store, now=NOW)
    assert (again.new, again.repeated) == (0, 10)


def test_repeated_hour_does_not_create_a_false_interruption_in_the_tir(tmp_path):
    store = LibreStore.open(tmp_path / "libre.db.enc", KeyringKeyProvider(backend=FakeKeyring()))
    import_libre_csv(build_csv(repeated_hour_rows()), "x.csv", store, now=NOW)
    samples = samples_from_stored(store.readings(RecordType.HISTORIC))
    start = samples[0].instant - timedelta(minutes=7.5)
    end = samples[-1].instant + timedelta(minutes=7.5)

    result = compute_tir(samples, start, end, TirParamsLoose())

    assert result.interruptions == ()
    assert result.coverage == pytest.approx(1.0)


def TirParamsLoose():  # noqa: N802 - pequeño helper de prueba
    from glucosa.analytics.glucose_sensor import TirParams

    return TirParams(min_readings=1, min_coverage=0.0)


def test_a_single_pass_file_flags_the_ambiguity_without_failing():
    only_second = [row("hist", "04-04-2026 23:20", 100), row("hist", "04-04-2026 23:35", 101)]
    parsed = parse_libre_csv(build_csv(only_second))
    assert all(
        r.time_flag is TimeFlag.AMBIGUOUS for r in parsed.readings
    )  # se avisa; fold por defecto


# ---------------------------------------------------- errores transitorios de disco
def test_a_locked_file_is_a_retry_message_not_an_instruction_to_delete_it(tmp_path, monkeypatch):
    backend = FakeKeyring()
    path = tmp_path / "libre.db.enc"
    first = LibreStore.open(path, KeyringKeyProvider(backend=backend))
    first.apply_import(plan([reading(0)], sha="1" * 64))
    first.close()

    def locked(self):
        raise PermissionError("en uso por otro programa")

    monkeypatch.setattr(type(path), "read_bytes", locked)
    with pytest.raises(SecureStoreError) as info:
        LibreStore.open(path, KeyringKeyProvider(backend=backend))
    assert "elimina" not in str(info.value)
    assert "reintenta" in str(info.value).lower()


def test_non_uniqueness_integrity_errors_are_not_reported_as_duplicates(tmp_path):
    store = LibreStore.open(tmp_path / "libre.db.enc", KeyringKeyProvider(backend=FakeKeyring()))
    with pytest.raises(LibreStoreError) as info:
        store.apply_import(plan([reading(0, value=5)]))  # fuera del rango de glucosa permitido
    assert "duplicad" not in str(info.value).lower()
    assert store.stats().total == 0


# ------------------------------------------------- estado desactualizado entre instancias
def test_an_import_refreshes_a_stale_store_instead_of_failing(tmp_path):
    backend = FakeKeyring()
    path = tmp_path / "libre.db.enc"
    provider = KeyringKeyProvider(backend=backend)
    rows = minute_series("20-10-2026", 0, 10)
    seed = LibreStore.open(path, provider)
    import_libre_csv(build_csv(rows[:2]), "a.csv", seed, now=NOW)
    stale = LibreStore.open(path, provider)
    fresh = LibreStore.open(path, provider)

    import_libre_csv(build_csv(rows[2:6]), "b.csv", fresh, now=NOW)
    summary = import_libre_csv(build_csv(rows[4:]), "c.csv", stale, now=NOW)  # stale no veía b.csv

    assert summary.repeated == 2 and summary.total_consolidated == 10
    assert LibreStore.open(path, provider).stats().total == 10


# ------------------------------------------------------------------- analítica
def test_identical_readings_from_two_devices_are_counted_once():
    base = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    stored = [
        StoredReading("dev-a", "x", base, -240, TimeFlag.NORMAL, RecordType.HISTORIC, 120, 1),
        StoredReading("dev-b", "x", base, -240, TimeFlag.NORMAL, RecordType.HISTORIC, 120, 1),
        StoredReading(
            "dev-b",
            "x",
            base + timedelta(minutes=15),
            -240,
            TimeFlag.NORMAL,
            RecordType.HISTORIC,
            121,
            1,
        ),
    ]
    assert len(samples_from_stored(stored)) == 2


def test_timezone_naive_datetimes_are_rejected_with_a_clear_error():
    naive = datetime(2026, 10, 20, 12, 0)
    with pytest.raises(ValueError, match="zona horaria"):
        compute_tir([SensorSample(naive, 100)], naive, naive + timedelta(hours=1))


# --------------------------------------------------------------------- parser
def test_record_type_and_values_use_strict_digit_patterns():
    odd_type = row("hist", "20-10-2026 08:00", 100)
    odd_type[3] = "1_0"
    plus_type = row("hist", "20-10-2026 08:15", 100)
    plus_type[3] = "+1"
    parsed = parse_libre_csv(
        build_csv([odd_type, plus_type, row("hist", "20-10-2026 08:30", "99999")])
    )
    assert [i.reason for i in parsed.invalid] == [
        "tipo_invalido",
        "tipo_invalido",
        "fuera_de_rango_plausible",
    ]


# ------------------------------------------------------------ etiqueta de archivo
def test_the_original_file_name_is_not_stored_only_a_neutral_label(tmp_path):
    store = LibreStore.open(tmp_path / "libre.db.enc", KeyringKeyProvider(backend=FakeKeyring()))
    summary = import_libre_csv(
        build_csv(minute_series("20-10-2026", 8, 2)),
        "Paciente Privado_glucose_23-10-2026.csv",
        store,
        now=NOW,
    )
    (record,) = store.imports()
    assert "Privado" not in record.file_name and "Privado" not in summary.file_name
    assert (
        record.file_name
        == summary.file_name
        == f"exportación del 23-10-2026 [{summary.file_sha256[:8]}]"
    )
    assert (
        "Privado"
        not in EncryptedBytesStore(
            tmp_path / "libre.db.enc",
            KeyringKeyProvider(
                backend=FakeKeyring(),
            ),
        ).path.name
    )


# ------------------------------------------------------------------------ CLI
def test_cli_never_shows_a_traceback_for_unexpected_database_errors(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / "e.csv"
    csv_path.write_bytes(build_csv(minute_series("20-10-2026", 8, 2)))

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("detalle interno")

    monkeypatch.setattr(libre_import, "import_libre_csv", boom)
    code = libre_import.main(
        [str(csv_path), "--db", str(tmp_path / "libre.db.enc")],
        key_provider=KeyringKeyProvider(backend=FakeKeyring()),
    )
    err = capsys.readouterr().err
    assert code == 1 and "OperationalError" in err and "Traceback" not in err
    assert "detalle interno" not in err
