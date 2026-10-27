"""Almacén cifrado de bytes (contenedor de la base LibreView) y derivación de subclaves."""

import pytest

from glucosa.errors import SecureStoreError
from glucosa.storage.secure_store import EncryptedBytesStore, KeyringKeyProvider, derive_subkey
from tests.fakes import FakeKeyring


def make_store(tmp_path, backend=None, name="datos.bin") -> EncryptedBytesStore:
    return EncryptedBytesStore(
        tmp_path / name, KeyringKeyProvider(backend=backend or FakeKeyring())
    )


def test_round_trip_and_content_is_not_readable_on_disk(tmp_path):
    store = make_store(tmp_path)
    payload = b"SQLite format 3\x00 contenido de salud reservado"

    store.write(payload)

    assert store.read() == payload
    on_disk = (tmp_path / "datos.bin").read_bytes()
    assert b"SQLite format 3" not in on_disk
    assert b"contenido de salud" not in on_disk


def test_read_of_a_missing_file_returns_none(tmp_path):
    assert make_store(tmp_path).read() is None
    assert make_store(tmp_path).stamp() is None


def test_the_key_is_not_stored_next_to_the_data(tmp_path):
    backend = FakeKeyring()
    make_store(tmp_path, backend).write(b"x")
    key = KeyringKeyProvider(backend=backend).key()
    assert key not in (tmp_path / "datos.bin").read_bytes()
    assert [p.name for p in tmp_path.iterdir()] == ["datos.bin"]  # sin la clave ni temporales


def test_reopening_with_the_stored_key_recovers_the_data(tmp_path):
    backend = FakeKeyring()
    make_store(tmp_path, backend).write(b"persistido")
    assert make_store(tmp_path, backend).read() == b"persistido"


def test_wrong_key_or_tampering_raises_instead_of_returning_garbage(tmp_path):
    make_store(tmp_path).write(b"secreto")
    with pytest.raises(SecureStoreError):
        make_store(tmp_path, FakeKeyring()).read()  # otra clave

    path = tmp_path / "datos.bin"
    path.write_bytes(path.read_bytes()[:-5] + b"XXXXX")
    with pytest.raises(SecureStoreError):
        make_store(tmp_path, FakeKeyring()).read()


def test_stamp_changes_when_the_file_changes(tmp_path):
    store = make_store(tmp_path)
    store.write(b"uno")
    first = store.stamp()
    store.write(b"dos dos dos")
    assert store.stamp() != first


def test_write_failure_keeps_the_previous_content(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    store.write(b"original")

    def broken_replace(src, dst):
        raise OSError("disco lleno")

    monkeypatch.setattr("glucosa.storage.secure_store.os.replace", broken_replace)
    with pytest.raises(OSError):
        store.write(b"nuevo")
    monkeypatch.undo()

    assert store.read() == b"original"
    assert [p.name for p in tmp_path.iterdir()] == ["datos.bin"]  # temporal eliminado


def test_subkeys_are_deterministic_distinct_and_not_the_master_key():
    master = b"clave-maestra-de-prueba-0123456789="
    first = derive_subkey(master, "libre-device-id")
    assert first == derive_subkey(master, "libre-device-id")
    assert first != derive_subkey(master, "otra-etiqueta")
    assert first != derive_subkey(b"otra-clave-maestra-9876543210abcdef=", "libre-device-id")
    assert master not in first and len(first) == 32
