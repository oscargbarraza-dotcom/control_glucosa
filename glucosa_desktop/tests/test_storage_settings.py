"""Almacenamiento cifrado local y ajustes por usuario (altura, rango objetivo)."""

import pytest

from glucosa.errors import SecureStoreError
from glucosa.settings.user_settings import SettingsRepository, UserSettings
from glucosa.storage.secure_store import EncryptedJsonStore, KeyringKeyProvider
from tests.fakes import FakeKeyring


def make_store(tmp_path, backend=None) -> EncryptedJsonStore:
    provider = KeyringKeyProvider(backend=backend or FakeKeyring())
    return EncryptedJsonStore(tmp_path / "datos.enc", provider)


def test_round_trip_and_ciphertext_is_not_plaintext(tmp_path):
    store = make_store(tmp_path)
    store.write({"height_cm": 172.5, "nota": "dato de salud"})

    assert store.read() == {"height_cm": 172.5, "nota": "dato de salud"}
    raw = (tmp_path / "datos.enc").read_bytes()
    assert b"dato de salud" not in raw
    assert b"172.5" not in raw


def test_read_of_missing_file_returns_none(tmp_path):
    assert make_store(tmp_path).read() is None


def test_key_is_generated_once_and_reused_from_keyring(tmp_path):
    backend = FakeKeyring()
    make_store(tmp_path, backend).write({"a": 1})
    assert make_store(tmp_path, backend).read() == {"a": 1}


def test_wrong_key_or_tampered_file_raises_instead_of_returning_garbage(tmp_path):
    make_store(tmp_path).write({"a": 1})  # otra clave (otro keyring)
    with pytest.raises(SecureStoreError):
        make_store(tmp_path, FakeKeyring()).read()

    (tmp_path / "datos.enc").write_bytes(b"basura")
    with pytest.raises(SecureStoreError):
        make_store(tmp_path).read()


def test_write_leaves_no_temporary_files(tmp_path):
    make_store(tmp_path).write({"a": 1})
    assert [p.name for p in tmp_path.iterdir()] == ["datos.enc"]


# ---------------- ajustes de usuario
def repo(tmp_path, backend=None) -> SettingsRepository:
    return SettingsRepository(tmp_path, KeyringKeyProvider(backend=backend or FakeKeyring()))


def test_defaults_when_nothing_saved(tmp_path):
    settings = repo(tmp_path).load("uidA0000000000")
    assert settings == UserSettings(target_low=70, target_high=180, height_cm=None)


def test_save_and_load_per_user_are_isolated(tmp_path):
    backend = FakeKeyring()
    r = repo(tmp_path, backend)
    r.save("uidA0000000000", UserSettings(target_low=80, target_high=160, height_cm=170.0))

    assert r.load("uidA0000000000").height_cm == 170.0
    assert r.load("uidB0000000000").height_cm is None


def test_uid_never_appears_in_the_file_system_path(tmp_path):
    r = repo(tmp_path)
    r.save("uidSecreto123456", UserSettings())
    assert all("uidSecreto123456" not in str(p) for p in tmp_path.rglob("*"))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_low": 10},
        {"target_high": 700},
        {"target_low": 180, "target_high": 70},
        {"target_low": 100, "target_high": 100},
        {"height_cm": 20.0},
        {"height_cm": 300.0},
    ],
)
def test_invalid_settings_are_rejected(kwargs):
    with pytest.raises(ValueError):
        UserSettings(**kwargs)
