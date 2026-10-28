"""Endurecimiento de la Etapa B tras la revisión de seguridad."""

import pytest

from glucosa import libre_import
from glucosa.errors import LibreFormatError, LibreStoreError, SecureStoreError
from glucosa.sources.libre import csv_format
from glucosa.sources.libre.csv_parser import parse_libre_csv
from glucosa.sources.libre.importer import display_name
from glucosa.sources.libre.store import LibreStore
from glucosa.storage.filelock import exclusive_lock
from glucosa.storage.secure_store import EncryptedBytesStore, KeyringKeyProvider
from tests.fakes import FakeKeyring
from tests.libre_fixtures import build_csv, minute_series, row
from tests.test_libre_store import plan, reading

SHA = "ab12cd34" + "0" * 56


# ----------------------------------------------------- nombre del archivo
def test_display_name_never_reveals_the_original_file_name():
    assert display_name("Perez_Juan_23-10-2026.csv", SHA) == "exportación del 23-10-2026 [ab12cd34]"
    assert display_name("Perez Juan.csv", SHA) == "exportación [ab12cd34]"
    for private in ("Perez", "Juan"):
        assert private not in display_name("Perez_Juan_23-10-2026.csv", SHA)


def test_missing_file_error_does_not_echo_the_file_name(tmp_path, capsys):
    code = libre_import.main([str(tmp_path / "Nombre Privado.csv")], key_provider=None)
    assert code == 1
    assert "Privado" not in capsys.readouterr().err


# ------------------------------------------------------------------- OneDrive
def test_store_refuses_a_database_path_inside_onedrive(tmp_path, monkeypatch):
    onedrive = tmp_path / "OneDrive - X"
    monkeypatch.setenv("OneDrive", str(onedrive))
    with pytest.raises(LibreStoreError, match="OneDrive"):
        LibreStore.open(
            onedrive / "proyecto" / "libre.db.enc", KeyringKeyProvider(backend=FakeKeyring())
        )
    assert not onedrive.exists()


def test_cli_refuses_db_inside_onedrive_even_when_given_explicitly(tmp_path, monkeypatch, capsys):
    onedrive = tmp_path / "OneDrive - X"
    onedrive.mkdir()
    monkeypatch.setenv("OneDrive", str(onedrive))
    csv_path = tmp_path / "e.csv"
    csv_path.write_bytes(build_csv(minute_series("20-10-2026", 8, 3)))

    code = libre_import.main(
        [str(csv_path), "--db", str(onedrive / "libre.db.enc")],
        key_provider=KeyringKeyProvider(backend=FakeKeyring()),
    )

    assert code == 1
    assert "OneDrive" in capsys.readouterr().err
    assert not (onedrive / "libre.db.enc").exists()


# ------------------------------------------------------ actualización perdida
def test_persisting_is_serialized_by_an_os_level_file_lock(tmp_path):
    backend = FakeKeyring()
    path = tmp_path / "libre.db.enc"
    store = LibreStore.open(path, KeyringKeyProvider(backend=backend), lock_timeout=0.3)
    store.apply_import(plan([reading(0)], sha="1" * 64))

    lock_path = path.with_name(path.name + ".lock")
    with (
        exclusive_lock(lock_path, timeout=1),
        pytest.raises(SecureStoreError, match="otra importación"),
    ):
        store.apply_import(plan([reading(1)], sha="2" * 64))

    assert store.stats().total == 1  # nada a medias en memoria ni en disco
    store.apply_import(plan([reading(1)], sha="2" * 64))  # liberado el bloqueo, funciona
    assert store.stats().total == 2


def test_lock_can_be_taken_again_after_release_and_times_out_while_held(tmp_path):
    lock = tmp_path / "x.lock"
    with (
        exclusive_lock(lock, timeout=1),
        pytest.raises(SecureStoreError),
        exclusive_lock(lock, timeout=0.2),
    ):
        pass
    with exclusive_lock(lock, timeout=1):
        pass


# --------------------------------------------------------------- CSV hostil
def test_flood_of_invalid_rows_is_counted_exactly_but_stored_only_up_to_a_limit():
    bad = [row("hist", "20-10-2026 08:00", "abc")] * 2500
    parsed = parse_libre_csv(build_csv(bad))
    assert parsed.invalid_total == 2500
    assert dict(parsed.invalid_by_reason) == {"valor_no_numerico": 2500}
    assert len(parsed.invalid) == csv_format.MAX_STORED_INVALID_ROWS == 1000


def test_flood_of_blank_lines_is_ignored_without_building_rows():
    content = build_csv(minute_series("20-10-2026", 8, 2)) + b"\r\n" * 300_000
    parsed = parse_libre_csv(content)
    assert parsed.rows_total == 2 and len(parsed.readings) == 2


def test_too_many_data_rows_are_rejected(monkeypatch):
    monkeypatch.setattr(csv_format, "MAX_DATA_ROWS", 5)
    with pytest.raises(LibreFormatError, match="filas"):
        parse_libre_csv(build_csv(minute_series("20-10-2026", 8, 6)))


@pytest.mark.parametrize("extreme", ["31-12-9999 23:59", "01-01-0001 00:00"])
def test_extreme_dates_are_invalid_rows_not_crashes(extreme):
    parsed = parse_libre_csv(
        build_csv([row("hist", extreme, 100), row("hist", "20-10-2026 08:00", 101)])
    )
    assert [r.glucose_mg_dl for r in parsed.readings] == [101]
    assert [i.reason for i in parsed.invalid] == ["fecha_invalida"]


def test_file_size_limit_is_realistic():
    assert csv_format.MAX_FILE_BYTES == 25 * 1024 * 1024


# --------------------------------------------------------------- claves
def test_reading_an_existing_file_never_creates_a_new_key(tmp_path):
    path = tmp_path / "datos.bin"
    EncryptedBytesStore(path, KeyringKeyProvider(backend=FakeKeyring())).write(b"x")

    lost = FakeKeyring()  # la clave se perdió (o el backend falló de forma transitoria)
    with pytest.raises(SecureStoreError):
        EncryptedBytesStore(path, KeyringKeyProvider(backend=lost)).read()

    assert lost.store == {}  # no se generó ni se sobrescribió ninguna clave


def test_key_provider_can_refuse_to_create_a_key():
    backend = FakeKeyring()
    with pytest.raises(SecureStoreError):
        KeyringKeyProvider(backend=backend).key(create=False)
    assert backend.store == {}


def test_corrupt_stored_key_is_a_clear_error():
    backend = FakeKeyring()
    backend.set_password("glucosa", "data-key", "clave-con-ñ-no-ascii")
    with pytest.raises(SecureStoreError):
        KeyringKeyProvider(backend=backend).key()
