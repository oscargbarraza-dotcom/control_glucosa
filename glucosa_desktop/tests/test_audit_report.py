"""Ensamblado y presentación del informe de auditoría."""

from datetime import UTC, datetime

from glucosa.audit.report import render_report, run_audit
from tests.conftest import make_doc

NOW = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
U1 = "3f2b8c1e-9d4a-4b7e-8a6c-1d2e3f4a5b6c"
U2 = "7a1c9e22-0b3d-4c5f-9e8a-2b3c4d5e6f70"
U3 = "11111111-2222-4333-8444-555555555555"
U4 = "66666666-7777-4888-9999-aaaaaaaaaaaa"
CREATED = "2026-10-20T15:00:05Z"


def sample_data():
    return {
        "glucose_measurements": [
            make_doc(
                U1,
                CREATED,
                uuid=U1,
                value=130,
                moment="afterLunch",
                measuredAt="2026-10-20T14:30:00.000000",
                comment="COMENTARIO-PRIVADO",
            )
        ],
        "meals": [
            make_doc(
                U2,
                CREATED,
                uuid=U2,
                type="lunch",
                eatenAt="2026-10-20T13:00:00.000000",
                comment=None,
                items=[{"foodName": "ALIMENTO-PRIVADO", "quantity": "2 porciones"}],
            )
        ],
        "medication_intakes": [
            make_doc(
                U3,
                CREATED,
                uuid=U3,
                takenAt="2026-10-20T08:00:00.000000",
                comment=None,
                items=[
                    {
                        "medicationName": "MEDICAMENTO-PRIVADO",
                        "defaultUnit": "tablet",
                        "quantity": 1.0,
                        "unit": "tablet",
                        "customUnitLabel": None,
                    }
                ],
            )
        ],
        "biometric_measurements": [
            make_doc(
                U4,
                CREATED,
                uuid=U4,
                weightKg=80.5,
                systolicPressure=120,
                diastolicPressure=80,
                heartRateBpm=70,
                measuredAt="2026-10-20T07:00:00.000000",
                comment=None,
            )
        ],
    }


def test_run_audit_assembles_every_section():
    report = run_audit(sample_data(), NOW)

    assert set(report.structure) == set(sample_data())
    assert set(report.dates) == set(sample_data())
    assert report.glucose.total == 1 and report.meals.total == 1
    assert report.intakes.total == 1 and report.biometrics.total == 1
    assert report.meal_coverage.with_post == 1
    assert report.moment.checked == 1 and report.moment.consistent == 1
    assert report.continuity.continuous_series_available is False
    assert all(p.total_documents == 1 for p in report.parse.values())
    assert all(p.issues == () for p in report.parse.values())


def test_rendered_report_has_sections_and_never_contains_private_text():
    text = render_report(run_audit(sample_data(), NOW))

    for heading in ("ESTRUCTURA", "FECHAS", "GLUCOSA", "ALIMENTACIÓN", "MEDICAMENTOS", "BIOMETRÍA"):
        assert heading in text
    assert "RELACIONES" in text
    for private in ("COMENTARIO-PRIVADO", "ALIMENTO-PRIVADO", "MEDICAMENTO-PRIVADO"):
        assert private not in text


def test_rejected_documents_are_counted_not_silently_dropped():
    data = sample_data()
    data["glucose_measurements"].append(
        make_doc(
            "malo",
            CREATED,
            uuid="malo",
            value="no-es-entero",
            measuredAt="2026-10-20T09:00:00.000000",
        )
    )
    report = run_audit(data, NOW)
    assert report.parse["glucose_measurements"].total_documents == 2
    assert len(report.parse["glucose_measurements"].records) == 1
    assert any(i.severity == "error" for i in report.parse["glucose_measurements"].issues)
    assert "rechazados" in render_report(report).lower()
