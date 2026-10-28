"""Calidad por módulo: rangos, completitud, unidades, duplicados y plausibilidad.

Opera sobre registros ya tipados. Los resultados son agregados: no incluyen
comentarios ni nombres de alimentos o medicamentos.
"""

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

from glucosa.data.parsing import GLUCOSE_RANGE
from glucosa.models.records import (
    BiometricRecord,
    GlucoseRecord,
    IntakeRecord,
    MealRecord,
    Origin,
)

LOW_MG_DL, HIGH_MG_DL = 70, 180  # rango objetivo por defecto (configurable en la app)
NEAR_DUPLICATE_SECONDS = 120
MEAL_DUPLICATE_SECONDS = 60
WEIGHT_JUMP_KG = 3.0
WEIGHT_JUMP_WINDOW_HOURS = 24.0
_NUMERIC_LEADING = re.compile(r"\s*\d+([.,]\d+)?(\s*/\s*\d+)?(\D|$)")


def normalize_name(name: str) -> str:
    """Minúsculas, sin acentos y con espacios colapsados (para detectar variantes)."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


def _bucket(count: int) -> str:
    if count >= 5:
        return "5+"
    return "3-4" if count >= 3 else str(count)


# --------------------------------------------------------------------- glucosa
@dataclass(frozen=True)
class GlucoseQuality:
    total: int
    manual: int
    imported: int
    moment_distribution: Mapping[str, int]
    moment_missing: int
    out_of_app_range: int
    below_70: int
    in_70_180: int
    above_180: int
    min_value: int | None
    max_value: int | None
    days_with_data: int
    per_day_buckets: Mapping[str, int]
    max_per_day: int
    same_instant_same_value: int
    near_duplicates: int
    median_gap_minutes: float | None


def audit_glucose(records: Sequence[GlucoseRecord]) -> GlucoseQuality:
    ordered = sorted(records, key=lambda r: r.measured_at)
    values = [r.value_mg_dl for r in ordered]
    per_day = Counter(r.measured_at.date() for r in ordered)
    gaps = [
        (b.measured_at - a.measured_at).total_seconds() / 60.0
        for a, b in zip(ordered, ordered[1:], strict=False)
    ]
    same_instant = near = 0
    for a, b in zip(ordered, ordered[1:], strict=False):
        seconds = (b.measured_at - a.measured_at).total_seconds()
        if a.value_mg_dl != b.value_mg_dl:
            continue
        if seconds == 0:
            same_instant += 1
        elif seconds <= NEAR_DUPLICATE_SECONDS:
            near += 1
    low, high = GLUCOSE_RANGE
    buckets = Counter(_bucket(n) for n in per_day.values())
    return GlucoseQuality(
        total=len(ordered),
        manual=sum(r.origin is Origin.MANUAL for r in ordered),
        imported=sum(r.origin is Origin.IMPORTED for r in ordered),
        moment_distribution=dict(Counter(r.moment.value for r in ordered if r.moment)),
        moment_missing=sum(r.moment is None for r in ordered),
        out_of_app_range=sum(not low <= v <= high for v in values),
        below_70=sum(v < LOW_MG_DL for v in values),
        in_70_180=sum(LOW_MG_DL <= v <= HIGH_MG_DL for v in values),
        above_180=sum(v > HIGH_MG_DL for v in values),
        min_value=min(values) if values else None,
        max_value=max(values) if values else None,
        days_with_data=len(per_day),
        per_day_buckets={key: buckets.get(key, 0) for key in ("1", "2", "3-4", "5+")},
        max_per_day=max(per_day.values(), default=0),
        same_instant_same_value=same_instant,
        near_duplicates=near,
        median_gap_minutes=median(gaps) if gaps else None,
    )


# ---------------------------------------------------------------------- comidas
@dataclass(frozen=True)
class MealQuality:
    total: int
    empty_items: int
    items_total: int
    type_distribution: Mapping[str, int]
    type_missing: int
    quantity_numeric_leading: int
    quantity_free_text: int
    quantity_empty: int
    distinct_names_raw: int
    distinct_names_normalized: int
    possible_duplicates: int
    days_with_data: int


def audit_meals(meals: Sequence[MealRecord]) -> MealQuality:
    items = [item for meal in meals for item in meal.items]
    quantities = [item.quantity for item in items]
    names = [item.food_name for item in items]
    ordered = sorted(meals, key=lambda m: m.eaten_at)
    duplicates = 0
    for index, meal in enumerate(ordered):
        signature = (meal.type, sorted(i.food_name for i in meal.items))
        for other in ordered[index + 1 :]:
            if (other.eaten_at - meal.eaten_at).total_seconds() > MEAL_DUPLICATE_SECONDS:
                break
            if signature == (other.type, sorted(i.food_name for i in other.items)):
                duplicates += 1
    return MealQuality(
        total=len(meals),
        empty_items=sum(not m.items for m in meals),
        items_total=len(items),
        type_distribution=dict(Counter(m.type.value for m in meals if m.type)),
        type_missing=sum(m.type is None for m in meals),
        quantity_numeric_leading=sum(bool(_NUMERIC_LEADING.match(q)) for q in quantities if q),
        quantity_free_text=sum(not _NUMERIC_LEADING.match(q) for q in quantities if q),
        quantity_empty=sum(not q for q in quantities),
        distinct_names_raw=len(set(names)),
        distinct_names_normalized=len({normalize_name(n) for n in names}),
        possible_duplicates=duplicates,
        days_with_data=len({m.eaten_at.date() for m in meals}),
    )


# ------------------------------------------------------------------ medicamentos
@dataclass(frozen=True)
class IntakeQuality:
    total: int
    empty_items: int
    items_total: int
    unit_distribution: Mapping[str, int]
    custom_unit_items: int
    distinct_medications_normalized: int
    medications_with_multiple_units: int
    possible_duplicates: int
    days_with_data: int


def audit_intakes(intakes: Sequence[IntakeRecord]) -> IntakeQuality:
    items = [item for intake in intakes for item in intake.items]
    units_by_med: dict[str, set[str]] = defaultdict(set)
    for item in items:
        units_by_med[normalize_name(item.medication_name)].add(item.unit.value)
    ordered = sorted(intakes, key=lambda i: i.taken_at)
    duplicates = 0
    for index, intake in enumerate(ordered):
        signature = sorted((i.medication_name, i.quantity, i.unit.value) for i in intake.items)
        for other in ordered[index + 1 :]:
            if (other.taken_at - intake.taken_at).total_seconds() > MEAL_DUPLICATE_SECONDS:
                break
            other_signature = sorted(
                (i.medication_name, i.quantity, i.unit.value) for i in other.items
            )
            duplicates += bool(signature) and signature == other_signature
    return IntakeQuality(
        total=len(intakes),
        empty_items=sum(not i.items for i in intakes),
        items_total=len(items),
        unit_distribution=dict(Counter(i.unit.value for i in items)),
        custom_unit_items=sum(bool(i.custom_unit_label) for i in items),
        distinct_medications_normalized=len(units_by_med),
        medications_with_multiple_units=sum(len(units) > 1 for units in units_by_med.values()),
        possible_duplicates=duplicates,
        days_with_data=len({i.taken_at.date() for i in intakes}),
    )


# --------------------------------------------------------------------- biometría
@dataclass(frozen=True)
class BiometricQuality:
    total: int
    with_blood_pressure: int
    blood_pressure_incomplete: int
    with_heart_rate: int
    systolic_not_above_diastolic: int
    weight_min: float | None
    weight_max: float | None
    large_weight_jumps: int
    same_instant: int
    measurement_days: int


def audit_biometrics(records: Sequence[BiometricRecord]) -> BiometricQuality:
    ordered = sorted(records, key=lambda r: r.measured_at)
    jumps = same_instant = 0
    for a, b in zip(ordered, ordered[1:], strict=False):
        hours = (b.measured_at - a.measured_at).total_seconds() / 3600.0
        same_instant += hours == 0
        jumps += (
            hours <= WEIGHT_JUMP_WINDOW_HOURS and abs(b.weight_kg - a.weight_kg) > WEIGHT_JUMP_KG
        )
    weights = [r.weight_kg for r in ordered]
    return BiometricQuality(
        total=len(ordered),
        with_blood_pressure=sum(r.has_blood_pressure for r in ordered),
        blood_pressure_incomplete=sum(
            (r.systolic is None) != (r.diastolic is None) for r in ordered
        ),
        with_heart_rate=sum(r.heart_rate_bpm is not None for r in ordered),
        systolic_not_above_diastolic=sum(
            r.has_blood_pressure and r.systolic <= r.diastolic for r in ordered
        ),
        weight_min=min(weights) if weights else None,
        weight_max=max(weights) if weights else None,
        large_weight_jumps=jumps,
        same_instant=same_instant,
        measurement_days=len({r.measured_at.date() for r in ordered}),
    )
