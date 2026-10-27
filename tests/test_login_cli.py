"""CLI de inicio de sesión: salida segura (datos enmascarados) y errores amigables."""

from datetime import UTC, datetime

from glucosa import login
from glucosa.auth.session import AuthSession
from glucosa.config import AppConfig


def test_email_is_masked():
    assert login.mask_email("persona@gmail.com") == "p***@gmail.com"
    assert login.mask_email(None) == "(sin correo)"
    assert login.mask_email("sin-arroba") == "(correo no válido)"


def test_uid_is_masked_keeping_only_the_ends():
    assert login.mask_uid("AbCdEf1234567890UidFirebase") == "AbCd…base"


class FakeReader:
    def __init__(self):
        self.calls = []

    def count_collection(self, uid, collection, id_token):
        self.calls.append((uid, collection, id_token))
        return len(collection)


def test_counts_are_read_for_the_four_collections_with_the_session_token():
    session = AuthSession("UidAbc123", None, "TOKEN", datetime(2030, 1, 1, tzinfo=UTC))
    reader = FakeReader()

    counts = login.read_counts(reader, session)

    assert [label for label, _ in counts] == ["Glucosa", "Comidas", "Medicamentos", "Biometría"]
    assert [c[1] for c in reader.calls] == [
        "glucose_measurements",
        "meals",
        "medication_intakes",
        "biometric_measurements",
    ]
    assert all(c[2] == "TOKEN" for c in reader.calls)


def test_incomplete_configuration_prints_a_friendly_error_not_a_traceback(monkeypatch, capsys):
    monkeypatch.setattr(login, "config_from_environment", lambda: AppConfig("seguimiento-glucosa"))

    exit_code = login.main(["status"])

    out = capsys.readouterr()
    assert exit_code == 1
    assert "GLUCOSA_FIREBASE_API_KEY" in out.out + out.err
    assert "Traceback" not in out.out + out.err


def test_unexpected_errors_print_only_the_exception_type(monkeypatch, capsys):
    def boom(command, config):
        raise OSError("detalle-interno-secreto")

    monkeypatch.setattr(login, "config_from_environment", lambda: AppConfig("p"))
    monkeypatch.setattr(login, "_run", boom)

    assert login.main(["status"]) == 1
    out = capsys.readouterr()
    assert "OSError" in out.err
    assert "detalle-interno-secreto" not in out.out + out.err


# ------------------------------------------------ comparar el uid con Firebase Console
from glucosa.auth.token_store import StoredLogin  # noqa: E402

SESSION_UID = "c1otFULLUIDdeLaSesionABCdtm2"


class FakeStore:
    def __init__(self, login=None):
        self._login = login

    def load(self):
        return self._login


def run_compare(monkeypatch, capsys, stored, argument):
    monkeypatch.setattr(login, "KeyringTokenStore", lambda: FakeStore(stored))
    code = login.main(["compare-uid", argument] if argument is not None else ["compare-uid"])
    out = capsys.readouterr()
    return code, out.out + out.err


def test_matching_uid_is_reported_without_printing_the_full_value(monkeypatch, capsys):
    stored = StoredLogin(uid=SESSION_UID, refresh_token="R")
    code, text = run_compare(monkeypatch, capsys, stored, f"  {SESSION_UID}  ")
    assert code == 0
    assert "COINCIDE" in text and "NO COINCIDE" not in text
    assert SESSION_UID not in text


def test_different_uid_is_reported_with_only_masked_values(monkeypatch, capsys):
    stored = StoredLogin(uid=SESSION_UID, refresh_token="R")
    other = "zzzzOTROUIDcompletoDistinto9999"
    code, text = run_compare(monkeypatch, capsys, stored, other)
    assert code == 1
    assert "NO COINCIDE" in text
    assert SESSION_UID not in text and other not in text


def test_without_a_stored_session_there_is_nothing_to_compare(monkeypatch, capsys):
    code, text = run_compare(monkeypatch, capsys, None, SESSION_UID)
    assert code == 1
    assert "sesión guardada" in text


def test_malformed_uid_input_is_rejected(monkeypatch, capsys):
    stored = StoredLogin(uid=SESSION_UID, refresh_token="R")
    code, text = run_compare(monkeypatch, capsys, stored, "../no-es-un-uid")
    assert code == 1
    assert "formato" in text.lower()


def test_missing_argument_without_a_terminal_asks_for_it(monkeypatch, capsys):
    stored = StoredLogin(uid=SESSION_UID, refresh_token="R")
    monkeypatch.setattr(login.sys.stdin, "isatty", lambda: False)
    code, text = run_compare(monkeypatch, capsys, stored, None)
    assert code == 1
    assert "compare-uid" in text


def test_empty_stdin_on_a_terminal_asks_for_the_argument_instead_of_crashing(monkeypatch, capsys):
    stored = StoredLogin(uid=SESSION_UID, refresh_token="R")
    monkeypatch.setattr(login.sys.stdin, "isatty", lambda: True)

    def eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    code, text = run_compare(monkeypatch, capsys, stored, None)
    assert code == 1
    assert "compare-uid <UID" in text
