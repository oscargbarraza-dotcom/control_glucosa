"""Base local cifrada de LibreView: cifrado en reposo, transacciones y recuperación."""

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from glucosa.errors import LibreStoreError, SecureStoreError
from glucosa.sources.libre.models import InvalidRow, RecordType, TimeFlag
from glucosa.sources.libre.store import (
    ConflictRecord,
    ImportPlan,
    LibreStore,
    NewReading,
)
from glucosa.storage.secure_store import EncryptedBytesStore, KeyringKeyProvider
from tests.fakes import FakeKeyring

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
BASE = datetime(2026, 10, 20, 11, 0, tzinfo=UTC)  # 07:00 hora de Santiago (UTC-4)


def reading(
    index,
    value=150,
    kind=RecordType.HISTORIC,
    device="dev-a",
    minute_offset=None,
    flag=TimeFlag.NORMAL,
):
    moment = BASE + timedelta(minutes=15 * index if minute_offset is None else minute_offset)
    local = (moment - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M")
    return NewReading(device, local, moment, -240, flag, kind, value)


def plan(
    readings=(),
    conflicts=(),
    invalid=(),
    sha="a" * 64,
    name="export.csv",
    repeated=0,
    when=NOW,
):
    return ImportPlan(
        imported_at_utc=when,
        file_name=name,
        file_sha256=sha,
        file_bytes=1234,
        rows_total=len(readings) + len(invalid) + repeated,
        repeated=repeated,
        conflicts=len(conflicts),
        period_start=readings[0].local_minute if readings else None,
        period_end=readings[-1].local_minute if readings else None,
        new_readings=tuple(readings),
        conflict_records=tuple(conflicts),
        invalid_rows=tuple(invalid),
    )


def open_store(tmp_path, backend=None):
    backend = backend or FakeKeyring()
    path = tmp_path / "libre.db.enc"
    return LibreStore.open(path, KeyringKeyProvider(backend=backend)), path, backend


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------- apertura
def test_opening_a_missing_store_creates_nothing_on_disk(tmp_path):
    store, path, _ = open_store(tmp_path)
    stats = store.stats()
    assert (stats.total, stats.historic, stats.scans, stats.imports) == (0, 0, 0, 0)
    assert stats.last_import_utc is None and stats.period_start is None
    assert not path.exists()


def test_data_survive_close_and_reopen_with_the_stored_key(tmp_path):
    store, path, backend = open_store(tmp_path)
    store.apply_import(plan([reading(0, 140), reading(1, 150), reading(2, 99, RecordType.SCAN)]))
    store.close()

    reopened, _, _ = open_store(tmp_path, backend)

    stats = reopened.stats()
    assert (stats.total, stats.historic, stats.scans) == (3, 2, 1)
    assert stats.last_import_utc == NOW
    assert [r.glucose_mg_dl for r in reopened.readings(RecordType.HISTORIC)] == [140, 150]
    assert path.exists()


def test_file_on_disk_is_encrypted_and_the_key_is_not_next_to_it(tmp_path):
    store, path, backend = open_store(tmp_path)
    store.apply_import(plan([reading(0, 321)], name="mi-archivo-privado.csv"))

    raw = path.read_bytes()
    for plain in (b"SQLite format 3", b"libre_reading", b"libre_import", b"mi-archivo-privado"):
        assert plain not in raw
    assert KeyringKeyProvider(backend=backend).key() not in raw
    assert sorted(p.name for p in tmp_path.iterdir() if p.suffix != ".lock") == ["libre.db.enc"]


def test_wrong_key_gives_a_clear_recovery_message_and_never_touches_the_file(tmp_path):
    store, path, _ = open_store(tmp_path)
    store.apply_import(plan([reading(0)]))
    before = digest(path)

    with pytest.raises(SecureStoreError, match="importar"):
        open_store(tmp_path, FakeKeyring())  # clave perdida

    assert digest(path) == before


def test_corrupted_file_is_reported_not_silently_replaced(tmp_path):
    store, path, backend = open_store(tmp_path)
    store.apply_import(plan([reading(0)]))
    path.write_bytes(b"basura")
    with pytest.raises(SecureStoreError):
        open_store(tmp_path, backend)
    assert path.read_bytes() == b"basura"


def test_unknown_schema_version_is_refused(tmp_path):
    backend = FakeKeyring()
    other = sqlite3.connect(":memory:")
    other.execute("CREATE TABLE x (a)")
    other.execute("PRAGMA user_version = 99")
    path = tmp_path / "libre.db.enc"
    payload = other.serialize()
    other.close()
    EncryptedBytesStore(path, KeyringKeyProvider(backend=backend)).write(payload)
    with pytest.raises(SecureStoreError, match="versión"):
        open_store(tmp_path, backend)


# ------------------------------------------------------------- transaccionalidad
def test_failure_in_the_middle_of_an_import_rolls_back_memory_and_disk(tmp_path, monkeypatch):
    store, path, backend = open_store(tmp_path)
    store.apply_import(plan([reading(0, 140)], sha="1" * 64))
    before = digest(path)

    def explode(*args, **kwargs):
        raise RuntimeError("falla simulada a mitad de la importación")

    monkeypatch.setattr(store, "_insert_invalid_rows", explode)
    with pytest.raises(RuntimeError):
        store.apply_import(
            plan([reading(1, 150), reading(2, 160)], invalid=[InvalidRow(5, "hi")], sha="2" * 64)
        )
    monkeypatch.undo()

    assert store.stats().total == 1 and store.stats().imports == 1
    assert digest(path) == before
    assert open_store(tmp_path, backend)[0].stats().total == 1


def test_disk_write_failure_preserves_existing_records_and_resyncs_memory(tmp_path, monkeypatch):
    store, path, backend = open_store(tmp_path)
    store.apply_import(plan([reading(0, 140)], sha="1" * 64))
    before = digest(path)

    monkeypatch.setattr(
        "glucosa.storage.secure_store.os.replace",
        lambda *a: (_ for _ in ()).throw(OSError("lleno")),
    )
    with pytest.raises(OSError):
        store.apply_import(plan([reading(1, 150)], sha="2" * 64))
    monkeypatch.undo()

    assert digest(path) == before
    assert store.stats().total == 1  # la memoria volvió al estado del disco
    store.apply_import(plan([reading(1, 150)], sha="2" * 64))  # y se puede reintentar
    assert store.stats().total == 2


def test_duplicate_historic_key_is_rejected_by_the_database_and_rolled_back(tmp_path):
    store, path, _ = open_store(tmp_path)
    store.apply_import(plan([reading(0, 140)], sha="1" * 64))
    before = digest(path)
    with pytest.raises(LibreStoreError, match="duplicad"):
        store.apply_import(plan([reading(1, 150), reading(0, 141)], sha="2" * 64))
    assert store.stats().total == 1 and digest(path) == before


def test_two_scans_in_the_same_minute_with_different_values_are_both_stored(tmp_path):
    store, _, _ = open_store(tmp_path)
    store.apply_import(plan([reading(0, 100, RecordType.SCAN), reading(0, 101, RecordType.SCAN)]))
    assert store.stats().scans == 2
    with pytest.raises(LibreStoreError):
        store.apply_import(plan([reading(0, 100, RecordType.SCAN)], sha="2" * 64))


def test_concurrent_modification_by_another_instance_is_detected_without_data_loss(tmp_path):
    first, path, backend = open_store(tmp_path)
    first.apply_import(plan([reading(0)], sha="1" * 64))
    a, _, _ = open_store(tmp_path, backend)
    b, _, _ = open_store(tmp_path, backend)

    a.apply_import(plan([reading(1)], sha="2" * 64))
    with pytest.raises(SecureStoreError, match="otro proceso"):
        b.apply_import(plan([reading(2)], sha="3" * 64))

    assert b.stats().total == 2  # b se resincronizó con el disco
    assert open_store(tmp_path, backend)[0].stats().total == 2


# --------------------------------------------------------------- consultas
def test_readings_are_filtered_by_type_and_instant_range_and_sorted(tmp_path):
    store, _, _ = open_store(tmp_path)
    store.apply_import(
        plan(
            [
                reading(2, 120),
                reading(0, 100),
                reading(1, 110),
                reading(3, 90, RecordType.SCAN),
            ]
        )
    )

    all_historic = store.readings(RecordType.HISTORIC)
    assert [r.glucose_mg_dl for r in all_historic] == [100, 110, 120]

    window = store.readings(
        RecordType.HISTORIC, start=BASE + timedelta(minutes=10), end=BASE + timedelta(minutes=30)
    )
    assert [r.glucose_mg_dl for r in window] == [110]  # inicio inclusivo, fin exclusivo
    assert [r.glucose_mg_dl for r in store.readings(RecordType.SCAN)] == [90]
    assert len(store.readings()) == 4


def test_stored_instants_keep_their_offset_and_time_flag(tmp_path):
    store, _, _ = open_store(tmp_path)
    store.apply_import(plan([reading(0, 100, flag=TimeFlag.AMBIGUOUS)]))
    (stored,) = store.readings()
    assert stored.instant_utc == BASE and stored.instant_utc.tzinfo is not None
    assert stored.utc_offset_minutes == -240
    assert stored.time_flag is TimeFlag.AMBIGUOUS
    assert stored.local_minute == "2026-10-20T07:00"


def test_index_exposes_existing_keys_and_blocked_conflicts(tmp_path):
    store, _, _ = open_store(tmp_path)
    conflict = ConflictRecord("dev-a", "2026-10-20T07:30", RecordType.HISTORIC, 140, 141)
    store.apply_import(
        plan([reading(0, 140), reading(1, 99, RecordType.SCAN)], conflicts=[conflict])
    )

    index = store.index()

    # claves: (dispositivo, minuto local, fold[, valor | tipo])
    assert index.historic == {("dev-a", "2026-10-20T07:00", 0): 140}
    assert index.scans == {("dev-a", "2026-10-20T07:15", 0, 99)}
    assert index.blocked == {("dev-a", "2026-10-20T07:30", 0, 0)}


def test_import_trace_and_file_hash_lookup(tmp_path):
    store, _, _ = open_store(tmp_path)
    store.apply_import(plan([reading(0)], sha="f" * 64, name="e.csv", repeated=3))

    assert store.has_file_hash("f" * 64) and not store.has_file_hash("0" * 64)
    (record,) = store.imports()
    assert (record.file_name, record.file_sha256, record.file_bytes) == ("e.csv", "f" * 64, 1234)
    assert (record.inserted, record.repeated, record.invalid, record.conflicts) == (1, 3, 0, 0)
    assert record.imported_at_utc == NOW


def test_device_ids_are_stable_distinct_and_hide_the_serial(tmp_path):
    store, _, backend = open_store(tmp_path)
    first = store.device_id_for("FreeStyle LibreLink", "SERIE-123")
    assert first == store.device_id_for("FreeStyle LibreLink", "SERIE-123")
    assert first != store.device_id_for("FreeStyle LibreLink", "SERIE-124")
    assert "SERIE-123" not in first and len(first) == 32
    assert first == open_store(tmp_path, backend)[0].device_id_for(
        "FreeStyle LibreLink", "SERIE-123"
    )
    other_key = open_store(tmp_path, FakeKeyring())[0]
    assert first != other_key.device_id_for("FreeStyle LibreLink", "SERIE-123")


def test_stats_period_uses_original_local_minutes(tmp_path):
    store, _, _ = open_store(tmp_path)
    store.apply_import(plan([reading(0), reading(5)]))
    stats = store.stats()
    assert (stats.period_start, stats.period_end) == ("2026-10-20T07:00", "2026-10-20T08:15")


def test_reading_order_is_deterministic_regardless_of_insertion_order(tmp_path):
    # Escaneos del mismo minuto con valores distintos y un historial del mismo instante.
    batch = [
        reading(0, 101, RecordType.SCAN),
        reading(0, 100, RecordType.SCAN),
        reading(0, 130, RecordType.HISTORIC),
        reading(0, 120, RecordType.SCAN, device="dev-b"),
    ]
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"
    first_dir.mkdir(), second_dir.mkdir()
    one, _, _ = open_store(first_dir)
    two, _, _ = open_store(second_dir)

    one.apply_import(plan(batch))
    two.apply_import(plan(list(reversed(batch))))

    keys = lambda s: [  # noqa: E731
        (r.device_id, int(r.record_type), r.glucose_mg_dl) for r in s.readings()
    ]
    assert keys(one) == keys(two)
