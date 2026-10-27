"""Comando `python -m glucosa.libre_import` y resumen legible de la importación."""

import hashlib
from pathlib import Path

from glucosa import libre_import
from glucosa.paths import libre_db_path
from glucosa.storage.secure_store import KeyringKeyProvider
from tests.fakes import FakeKeyring
from tests.libre_fixtures import PATIENT, SERIAL_A, build_csv, minute_series, row


def make_csv(tmp_path: Path, rows=None, name="Paciente_glucose_23-10-2026.csv") -> Path:
    path = tmp_path / name
    path.write_bytes(
        build_csv(
            rows
            or [
                *minute_series("20-10-2026", 8, 6),
                row("scan", "20-10-2026 08:20", 593),
                row("food", "20-10-2026 08:30"),
                row("hist", "20-10-2026 10:00", "HI"),
            ]
        )
    )
    return path


def run(argv, backend):
    return libre_import.main(argv, key_provider=KeyringKeyProvider(backend=backend))


def test_default_database_lives_in_the_local_data_dir_outside_onedrive(tmp_path):
    path = libre_db_path(tmp_path)
    assert path == tmp_path / "data" / "libre.db.enc"


def test_import_prints_the_required_summary_without_values_or_personal_data(tmp_path, capsys):
    csv_path = make_csv(tmp_path)
    db = tmp_path / "libre.db.enc"

    code = run([str(csv_path), "--db", str(db)], FakeKeyring())

    out = capsys.readouterr().out
    assert code == 0 and db.exists()
    for label in (
        "Archivo",
        "Período",
        "Filas",
        "Lecturas históricas",
        "Escaneos",
        "Nuevos",
        "Repetidos",
        "Inválidos",
        "Conflictos",
        "Total consolidado",
        "Última importación",
    ):
        assert label in out
    assert "HI" in out  # el motivo de los registros no numéricos se informa
    assert PATIENT not in out and SERIAL_A not in out
    assert "Paciente_glucose" not in out  # el nombre se muestra recortado
    assert "593" not in out  # ningún valor individual de glucosa


def test_second_import_of_the_same_file_does_not_add_records(tmp_path, capsys):
    csv_path = make_csv(tmp_path)
    db, backend = tmp_path / "libre.db.enc", FakeKeyring()
    run([str(csv_path), "--db", str(db)], backend)
    first = capsys.readouterr().out

    run([str(csv_path), "--db", str(db)], backend)
    second = capsys.readouterr().out

    assert "Nuevos: 7" in first
    assert "Nuevos: 0" in second and "Repetidos: 7" in second
    assert "ya se había importado" in second
    total = lambda text: next(line for line in text.splitlines() if "Total consolidado" in line)  # noqa: E731
    assert total(first) == total(second)


def test_the_original_csv_is_never_modified(tmp_path):
    csv_path = make_csv(tmp_path)
    before = (hashlib.sha256(csv_path.read_bytes()).hexdigest(), csv_path.stat().st_mtime_ns)

    run([str(csv_path), "--db", str(tmp_path / "libre.db.enc")], FakeKeyring())

    assert (
        hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        csv_path.stat().st_mtime_ns,
    ) == before


def test_missing_file_and_bad_format_give_friendly_errors(tmp_path, capsys):
    db = str(tmp_path / "libre.db.enc")
    assert run([str(tmp_path / "no-existe.csv"), "--db", db], FakeKeyring()) == 1
    bad = tmp_path / "malo.csv"
    bad.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    assert run([str(bad), "--db", db], FakeKeyring()) == 1

    err = capsys.readouterr().err
    assert "[ERROR]" in err and "Traceback" not in err
    assert not Path(db).exists()  # nada se creó


def test_lost_key_prints_the_recovery_procedure(tmp_path, capsys):
    csv_path = make_csv(tmp_path)
    db = str(tmp_path / "libre.db.enc")
    run([str(csv_path), "--db", db], FakeKeyring())
    capsys.readouterr()

    code = run([str(csv_path), "--db", db], FakeKeyring())  # otra clave = clave perdida

    assert code == 1
    err = capsys.readouterr().err
    assert "vuelve a importar" in err and "libre.db.enc" in err
