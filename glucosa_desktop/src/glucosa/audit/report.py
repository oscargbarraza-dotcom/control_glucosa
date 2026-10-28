"""Ensamblado y presentación (texto) del informe de auditoría de calidad de datos."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from glucosa.audit.dates import DateReport, audit_dates
from glucosa.audit.quality import (
    BiometricQuality,
    GlucoseQuality,
    IntakeQuality,
    MealQuality,
    audit_biometrics,
    audit_glucose,
    audit_intakes,
    audit_meals,
)
from glucosa.audit.relations import (
    ContinuityAssessment,
    DailyCoverage,
    IntakeGlucoseCoverage,
    MealGlucoseCoverage,
    MomentConsistency,
    assess_continuity,
    daily_coverage,
    intake_glucose_coverage,
    meal_glucose_coverage,
    moment_consistency,
)
from glucosa.audit.structure import DATE_FIELDS, StructureReport, audit_structure
from glucosa.data.firestore_decode import FirestoreDocument
from glucosa.data.parsing import (
    ParseResult,
    parse_biometrics,
    parse_glucose,
    parse_intakes,
    parse_meals,
)

_PARSERS = {
    "glucose_measurements": parse_glucose,
    "meals": parse_meals,
    "medication_intakes": parse_intakes,
    "biometric_measurements": parse_biometrics,
}


@dataclass(frozen=True)
class AuditReport:
    generated_at: datetime
    structure: Mapping[str, StructureReport]
    dates: Mapping[str, DateReport]
    parse: Mapping[str, ParseResult]
    glucose: GlucoseQuality
    meals: MealQuality
    intakes: IntakeQuality
    biometrics: BiometricQuality
    meal_coverage: MealGlucoseCoverage
    moment: MomentConsistency
    intake_coverage: IntakeGlucoseCoverage
    daily: DailyCoverage
    continuity: ContinuityAssessment


def run_audit(raw: Mapping[str, list[FirestoreDocument]], now: datetime) -> AuditReport:
    parsed = {name: _PARSERS[name](raw[name]) for name in _PARSERS}
    glucose = parsed["glucose_measurements"].records
    meals = parsed["meals"].records
    intakes = parsed["medication_intakes"].records
    biometrics = parsed["biometric_measurements"].records
    return AuditReport(
        generated_at=now,
        structure={name: audit_structure(name, raw[name]) for name in _PARSERS},
        dates={name: audit_dates(name, DATE_FIELDS[name], raw[name], now) for name in _PARSERS},
        parse=parsed,
        glucose=audit_glucose(glucose),
        meals=audit_meals(meals),
        intakes=audit_intakes(intakes),
        biometrics=audit_biometrics(biometrics),
        meal_coverage=meal_glucose_coverage(meals, glucose),
        moment=moment_consistency(glucose, meals),
        intake_coverage=intake_glucose_coverage(intakes, glucose),
        daily=daily_coverage(glucose, meals, intakes, biometrics),
        continuity=assess_continuity(glucose),
    )


# ------------------------------------------------------------------ texto
def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "n/d"


def _num(value: float | None, digits: int = 1) -> str:
    return "n/d" if value is None else f"{value:.{digits}f}"


def _structure_lines(report: AuditReport) -> list[str]:
    lines = ["== ESTRUCTURA Y TIPOS =="]
    for name, s in report.structure.items():
        p = report.parse[name]
        errors = sum(i.severity == "error" for i in p.issues)
        warnings = sum(i.severity == "warning" for i in p.issues)
        lines.append(f"{name}: {s.total} documentos")
        for f in s.fields:
            lines.append(f"  {f.name}: presente {f.present}, nulo {f.null}, tipos {dict(f.types)}")
        for f in s.item_fields:
            lines.append(
                f"  items.{f.name}: presente {f.present}, nulo {f.null}, tipos {dict(f.types)}"
            )
        lines.append(
            f"  inesperados {s.unexpected_fields or '-'}; faltantes {dict(s.missing_expected) or '-'}; "
            f"uuid≠id {s.uuid_mismatch}; id no UUIDv4 {s.invalid_uuid_format}"
        )
        lines.append(
            f"  validación: {len(p.records)} válidos, {errors} rechazados (error), "
            f"{warnings} avisos, {p.duplicate_uuids} UUID repetidos"
        )
    return lines


def _date_lines(report: AuditReport) -> list[str]:
    lines = ["== FECHAS Y ZONAS HORARIAS =="]
    for name, d in report.dates.items():
        first = d.earliest.date() if d.earliest else "n/d"
        last = d.latest.date() if d.latest else "n/d"
        lines.append(
            f"{name} [{d.field}]: formatos {dict(d.formats)}, decimales {dict(d.fraction_digits)}"
        )
        lines.append(
            f"  sin interpretar {d.unparseable}, hora ambigua {d.ambiguous}, inexistente "
            f"{d.nonexistent}, futuras {d.future}; rango {first} → {last}"
        )
        if d.lag:
            lag = d.lag
            lines.append(
                f"  desfase evento→nube: n={lag.count}, negativos {lag.negative}, >1 h {lag.over_1h}, "
                f">24 h {lag.over_24h}; mín {lag.min_minutes * 60:.0f} s, mediana "
                f"{lag.median_minutes * 60:.0f} s, p90 {lag.p90_minutes * 60:.0f} s, "
                f"máx {lag.max_minutes * 60:.0f} s"
            )
    return lines


def _glucose_lines(q: GlucoseQuality) -> list[str]:
    return [
        "== GLUCOSA ==",
        f"registros {q.total}: manuales {q.manual}, importados {q.imported}; "
        f"rango {q.min_value}–{q.max_value} mg/dL; fuera del rango de la app (20–600): {q.out_of_app_range}",
        f"<70: {q.below_70} ({_pct(q.below_70, q.total)}), 70–180: {q.in_70_180} "
        f"({_pct(q.in_70_180, q.total)}), >180: {q.above_180} ({_pct(q.above_180, q.total)})",
        f"días con datos {q.days_with_data}; mediciones/día {dict(q.per_day_buckets)} "
        f"(máx {q.max_per_day}); intervalo mediano entre mediciones {_num(q.median_gap_minutes)} min",
        f"momento: {dict(q.moment_distribution)}; sin momento {q.moment_missing}",
        f"duplicados: mismo instante y valor {q.same_instant_same_value}; mismo valor ≤2 min {q.near_duplicates}",
    ]


def _meal_lines(q: MealQuality) -> list[str]:
    return [
        "== ALIMENTACIÓN ==",
        f"comidas {q.total} (sin alimentos {q.empty_items}); alimentos registrados {q.items_total}; "
        f"tipos {dict(q.type_distribution)}; sin tipo {q.type_missing}",
        f"cantidades: con número inicial {q.quantity_numeric_leading}, texto libre "
        f"{q.quantity_free_text}, vacías {q.quantity_empty}",
        f"nombres distintos: {q.distinct_names_raw} (normalizados {q.distinct_names_normalized}); "
        f"posibles duplicados {q.possible_duplicates}; días con datos {q.days_with_data}",
    ]


def _intake_lines(q: IntakeQuality) -> list[str]:
    return [
        "== MEDICAMENTOS ==",
        f"tomas {q.total} (sin medicamentos {q.empty_items}); medicamentos registrados {q.items_total}; "
        f"distintos {q.distinct_medications_normalized}",
        f"unidades {dict(q.unit_distribution)}; con unidad propia {q.custom_unit_items}; "
        f"medicamentos con >1 unidad {q.medications_with_multiple_units}",
        f"posibles duplicados {q.possible_duplicates}; días con datos {q.days_with_data}",
    ]


def _biometric_lines(q: BiometricQuality) -> list[str]:
    return [
        "== BIOMETRÍA ==",
        f"registros {q.total}: con presión {q.with_blood_pressure} (incompleta "
        f"{q.blood_pressure_incomplete}), con frecuencia cardíaca {q.with_heart_rate}",
        f"peso {_num(q.weight_min)}–{_num(q.weight_max)} kg; saltos >3 kg en <24 h {q.large_weight_jumps}; "
        f"sistólica ≤ diastólica {q.systolic_not_above_diastolic}; mismo instante {q.same_instant}; "
        f"días con datos {q.measurement_days}",
    ]


def _relation_lines(r: AuditReport) -> list[str]:
    c, m, i, d, k = r.meal_coverage, r.moment, r.intake_coverage, r.daily, r.continuity
    return [
        "== RELACIONES ENTRE MÉTRICAS ==",
        f"comidas con glucosa 60 min antes: {c.with_pre}/{c.meals}; 30–180 min después: "
        f"{c.with_post}/{c.meals}; ambas: {c.with_both}/{c.meals}",
        f"«momento» alusivo a una comida: {m.checked} evaluados, coherentes {m.consistent}, "
        f"sin comida registrada cercana {m.no_matching_meal}",
        f"tomas con glucosa 60 min antes: {i.with_pre}/{i.intakes}; 30–240 min después: {i.with_post}/{i.intakes}",
        f"cobertura diaria: {d.first_day} → {d.last_day} ({d.calendar_days} días); glucosa {d.days_glucose}, "
        f"comidas {d.days_meals}, tomas {d.days_intakes}, biometría {d.days_biometrics}; "
        f"glucosa+comidas {d.days_glucose_and_meals}; los cuatro {d.days_all_four}",
        f"serie continua para tiempo en rango: {'sí' if k.continuous_series_available else 'no'} "
        f"(importadas {k.imported}). {k.reason}",
    ]


def render_report(report: AuditReport) -> str:
    sections = [
        [
            f"AUDITORÍA DE CALIDAD DE DATOS — {report.generated_at:%Y-%m-%d %H:%M} UTC (solo lectura)"
        ],
        _structure_lines(report),
        _date_lines(report),
        _glucose_lines(report.glucose),
        _meal_lines(report.meals),
        _intake_lines(report.intakes),
        _biometric_lines(report.biometrics),
        _relation_lines(report),
    ]
    return "\n".join("\n".join(lines) + "\n" for lines in sections)
