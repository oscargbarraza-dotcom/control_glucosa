"""Importación incremental e idempotente de CSV de LibreView (datos sintéticos)."""

import logging
from datetime import UTC, datetime

import pytest

from glucosa.errors import LibreFormatError, SecureStoreError
from glucosa.sources.libre.importer import import_libre_csv
from glucosa.sources.libre.models import RecordType, TimeFlag
from glucosa.sources.libre.store import LibreStore
from glucosa.storage.secure_store import KeyringKeyProvider
from tests.fakes import FakeKeyring
from tests.libre_fixtures import SERIAL_B, build_csv, minute_series, row

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 24, 9, 30, tzinfo=UTC)


def open_store(tmp_path, backend=None):
    backend = backend or FakeKeyring()
    store = LibreStore.open(tmp_path / "libre.db.enc", KeyringKeyProvider(backend=backend))
    return store, backend


def do_import(store, rows, name="export.csv", now=NOW, **kwargs):
    return import_libre_csv(build_csv(rows, **kwargs), name, store, now=now)


def assert_reconciles(summary):
    valid = summary.historic_rows + summary.scan_rows
    assert summary.rows_total == valid + summary.invalid + sum(summary.other_events.values())
    assert valid == summary.new + summary.repeated + summary.rows_in_conflict


# ---------------------------------------------------------- primera importación
def test_first_import_reports_every_category_and_reconciles(tmp_path):
    store, _ = open_store(tmp_path)
    rows = [
        *minute_series("20-10-2026", 8, 4),
        row("scan", "20-10-2026 08:20", 118),
        row("scan", "20-10-2026 09:05", 130),
        row("food", "20-10-2026 08:30"),
        row("note", "20-10-2026 08:31"),
        row("other", "20-10-2026 08:32"),
        row("hist", "20-10-2026 09:00", "HI"),
        row("hist", "20-10-2026 09:15", ""),
    ]

    summary = do_import(store, rows, name="Paciente_glucose_23-10-2026.csv")

    assert (summary.historic_rows, summary.scan_rows) == (4, 2)
    assert summary.other_events == {"alimento": 1, "nota": 1, "otros": 1}
    assert (summary.new, summary.new_historic, summary.new_scans) == (6, 4, 2)
    assert (summary.repeated, summary.conflicts, summary.invalid) == (0, 0, 2)
    assert summary.invalid_by_reason == {"hi": 1, "valor_ausente": 1}
    assert summary.hi_lo == 1
    assert (summary.total_consolidated, summary.total_historic, summary.total_scans) == (6, 4, 2)
    assert (summary.period_start, summary.period_end) == ("2026-10-20T08:00", "2026-10-20T09:05")
    assert summary.rows_total == 11 and summary.same_file_seen_before is False
    assert summary.imported_at_utc == NOW and summary.last_import_utc == NOW
    assert len(summary.file_sha256) == 64
    assert_reconciles(summary)


def test_food_and_notes_are_not_persisted(tmp_path):
    store, _ = open_store(tmp_path)
    do_import(store, [row("food", "20-10-2026 08:30"), row("note", "20-10-2026 08:31")])
    assert store.stats().total == 0


# --------------------------------------------------------------- idempotencia
def test_reimporting_the_same_file_adds_nothing(tmp_path):
    store, _ = open_store(tmp_path)
    rows = [*minute_series("20-10-2026", 8, 10), row("scan", "20-10-2026 08:20", 118)]
    first = do_import(store, rows)

    second = do_import(store, rows, now=LATER)

    assert second.new == 0 and second.repeated == 11 and second.conflicts == 0
    assert second.total_consolidated == first.total_consolidated == 11
    assert second.same_file_seen_before is True
    assert second.last_import_utc == LATER
    assert len(store.imports()) == 2  # queda la traza del segundo intento
    assert_reconciles(second)


def test_overlapping_exports_only_add_the_new_readings(tmp_path):
    store, _ = open_store(tmp_path)
    all_rows = minute_series("20-10-2026", 0, 20)
    do_import(store, all_rows[:10], name="a.csv")

    second = do_import(store, all_rows[5:], name="b.csv", now=LATER)

    assert (second.new, second.repeated) == (10, 5)
    assert second.total_consolidated == 20
    assert_reconciles(second)


def test_import_order_does_not_change_the_final_content(tmp_path):
    rows = minute_series("20-10-2026", 0, 12)
    first_dir, second_dir = tmp_path / "x", tmp_path / "y"
    first_dir.mkdir(), second_dir.mkdir()
    a, _ = open_store(first_dir)
    b, _ = open_store(second_dir)

    do_import(a, rows[:7])
    do_import(a, rows[4:], now=LATER)
    do_import(b, rows[4:])
    do_import(b, rows[:7], now=LATER)

    values = lambda s: [(r.local_minute, r.glucose_mg_dl) for r in s.readings()]  # noqa: E731
    assert values(a) == values(b) and len(values(a)) == 12


def test_exact_duplicate_rows_inside_one_file_count_as_repeated(tmp_path):
    store, _ = open_store(tmp_path)
    same = row("hist", "20-10-2026 08:00", 100)

    summary = do_import(store, [same, same, same])

    assert (summary.new, summary.repeated) == (1, 2)
    assert_reconciles(summary)


# ------------------------------------------------------------------ conflictos
def test_same_key_different_value_is_a_conflict_and_never_overwrites(tmp_path):
    store, _ = open_store(tmp_path)
    do_import(store, [row("hist", "20-10-2026 08:00", 100)])

    summary = do_import(store, [row("hist", "20-10-2026 08:00", 140)], name="b.csv", now=LATER)

    assert (summary.new, summary.conflicts, summary.rows_in_conflict) == (0, 1, 1)
    assert summary.total_consolidated == 1
    assert [r.glucose_mg_dl for r in store.readings()] == [100]  # el valor original no cambia
    assert_reconciles(summary)


def test_a_recorded_conflict_keeps_blocking_the_key_on_later_imports(tmp_path):
    store, _ = open_store(tmp_path)
    do_import(store, [row("hist", "20-10-2026 08:00", 100)])
    conflicting = [row("hist", "20-10-2026 08:00", 140)]
    do_import(store, conflicting, name="b.csv", now=LATER)

    again = do_import(store, conflicting, name="b.csv", now=LATER)

    assert (again.new, again.conflicts) == (0, 1)
    assert [r.glucose_mg_dl for r in store.readings()] == [100]


def test_conflicting_values_inside_the_same_file_insert_none_of_them(tmp_path):
    store, _ = open_store(tmp_path)
    summary = do_import(
        store,
        [row("hist", "20-10-2026 08:00", 100), row("hist", "20-10-2026 08:00", 140)],
    )
    assert (summary.new, summary.conflicts, summary.rows_in_conflict) == (0, 1, 2)
    assert store.stats().total == 0
    assert_reconciles(summary)


def test_a_known_value_plus_a_different_one_counts_repeated_and_conflict(tmp_path):
    store, _ = open_store(tmp_path)
    do_import(store, [row("hist", "20-10-2026 08:00", 100)])
    summary = do_import(
        store,
        [row("hist", "20-10-2026 08:00", 100), row("hist", "20-10-2026 08:00", 140)],
        now=LATER,
    )
    assert (summary.repeated, summary.conflicts, summary.rows_in_conflict) == (1, 1, 1)
    assert_reconciles(summary)


# --------------------------------------------------------------------- escaneos
def test_two_scans_in_the_same_minute_with_different_values_are_independent(tmp_path):
    store, _ = open_store(tmp_path)

    summary = do_import(
        store,
        [row("scan", "20-10-2026 08:00", 100), row("scan", "20-10-2026 08:00", 101)],
    )

    assert (summary.new_scans, summary.conflicts, summary.repeated) == (2, 0, 0)
    assert [r.glucose_mg_dl for r in store.readings(RecordType.SCAN)] == [100, 101]


def test_identical_scans_are_repeated_and_scans_never_mix_with_the_historic_series(tmp_path):
    store, _ = open_store(tmp_path)
    rows = [
        row("scan", "20-10-2026 08:00", 100),
        row("scan", "20-10-2026 08:00", 100),
        row("hist", "20-10-2026 08:00", 100),
    ]

    summary = do_import(store, rows)

    assert (summary.new_historic, summary.new_scans, summary.repeated) == (1, 1, 1)
    assert store.stats().historic == 1 and store.stats().scans == 1


# ------------------------------------------------------------------ dispositivos
def test_different_devices_keep_independent_records_for_the_same_minute(tmp_path):
    store, _ = open_store(tmp_path)
    rows = [
        row("hist", "20-10-2026 08:00", 100),
        row("hist", "20-10-2026 08:00", 100, serial=SERIAL_B),
        row("hist", "20-10-2026 08:00", 150, serial=SERIAL_B),
    ]

    summary = do_import(store, rows)

    assert summary.new == 1 and summary.conflicts == 1  # el conflicto es solo del dispositivo B
    assert len({r.device_id for r in store.readings()}) == 1


def test_serial_numbers_are_never_stored(tmp_path):
    store, _ = open_store(tmp_path)
    do_import(store, [row("hist", "20-10-2026 08:00", 100)])
    assert all("SERIE-SECRETA" not in r.device_id for r in store.readings())
    assert len(store.readings()[0].device_id) == 32


# ------------------------------------------------------------------- errores
def test_invalid_rows_do_not_stop_the_import(tmp_path):
    store, _ = open_store(tmp_path)
    rows = [
        row("hist", "20-10-2026 08:00", 100),
        row("hist", "20-10-2026 08:15", "LO"),
        row("hist", "20-10-2026 08:30", "abc"),
        row("hist", "fecha-mala", 100),
        row("hist", "20-10-2026 08:45", 101),
    ]
    summary = do_import(store, rows)
    assert summary.new == 2 and summary.invalid == 3
    assert summary.invalid_by_reason == {"lo": 1, "valor_no_numerico": 1, "fecha_invalida": 1}
    assert_reconciles(summary)


def test_format_error_leaves_the_store_untouched(tmp_path):
    store, _ = open_store(tmp_path)
    do_import(store, [row("hist", "20-10-2026 08:00", 100)])
    with pytest.raises(LibreFormatError):
        import_libre_csv(b"esto,no,es,libreview\r\n", "x.csv", store, now=NOW)
    assert store.stats().total == 1 and len(store.imports()) == 1


def test_failure_during_the_transaction_preserves_existing_records(tmp_path, monkeypatch):
    store, backend = open_store(tmp_path)
    do_import(store, [row("hist", "20-10-2026 08:00", 100)])

    monkeypatch.setattr(
        store, "_insert_invalid_rows", lambda *a: (_ for _ in ()).throw(OSError("x"))
    )
    with pytest.raises(OSError):
        do_import(store, [row("hist", "20-10-2026 08:15", 101), row("hist", "bad", 1)], now=LATER)
    monkeypatch.undo()

    assert store.stats().total == 1
    assert open_store(tmp_path, backend)[0].stats().total == 1


# ------------------------------------------------------------ fechas y trazas
def test_time_flags_and_offsets_are_stored_for_dst_edge_cases(tmp_path):
    store, _ = open_store(tmp_path)
    do_import(
        store,
        [
            row("hist", "04-04-2026 23:30", 100),  # hora repetida
            row("hist", "06-09-2026 00:30", 101),  # hora inexistente
            row("hist", "15-08-2026 12:00", 102),
        ],
    )
    flags = {r.local_minute: r.time_flag for r in store.readings()}
    assert flags["2026-04-04T23:30"] is TimeFlag.AMBIGUOUS
    assert flags["2026-09-06T00:30"] is TimeFlag.NONEXISTENT
    assert flags["2026-08-15T12:00"] is TimeFlag.NORMAL


def test_import_trace_records_hash_size_counts_and_time(tmp_path):
    store, _ = open_store(tmp_path)
    content = build_csv(
        [row("hist", "20-10-2026 08:00", 100), row("hist", "20-10-2026 08:15", "HI")]
    )

    summary = import_libre_csv(content, "Paciente_glucose_23-10-2026.csv", store, now=NOW)

    (record,) = store.imports()
    assert record.file_sha256 == summary.file_sha256
    assert record.file_bytes == len(content)
    assert (record.inserted, record.invalid, record.repeated, record.conflicts) == (1, 1, 0, 0)
    assert record.imported_at_utc == NOW


def test_logs_never_contain_glucose_values_or_the_file_name(tmp_path, caplog):
    store, _ = open_store(tmp_path)
    caplog.set_level(logging.DEBUG)

    do_import(
        store,
        [row("hist", "20-10-2026 08:00", 321), row("scan", "20-10-2026 08:05", 457)],
        name="NombrePrivado_glucose.csv",
    )

    assert "321" not in caplog.text and "457" not in caplog.text
    assert "NombrePrivado" not in caplog.text


# ------------------------------------------------------------------ recuperación
def test_losing_the_key_is_recoverable_by_deleting_the_file_and_reimporting(tmp_path):
    rows = minute_series("20-10-2026", 8, 20)
    store, _ = open_store(tmp_path)
    original = do_import(store, rows)
    store.close()

    with pytest.raises(SecureStoreError, match="importar"):
        open_store(tmp_path, FakeKeyring())  # clave perdida: la base no se puede abrir

    (tmp_path / "libre.db.enc").unlink()  # procedimiento documentado
    new_store, _ = open_store(tmp_path, FakeKeyring())
    recovered = do_import(new_store, rows, now=LATER)

    assert recovered.total_consolidated == original.total_consolidated == 20
    assert recovered.new == 20
