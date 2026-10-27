"""Validación y transformación de comidas, medicamentos y biometría."""

import pytest

from glucosa.data.parsing import parse_biometrics, parse_intakes, parse_meals
from glucosa.models.records import DoseUnit, MealType
from tests.conftest import make_doc


# ---------- Comidas ----------
def meal_fields(**overrides):
    base = {
        "uuid": "m-1",
        "type": "breakfast",
        "eatenAt": "2026-08-19T08:15:00.000",
        "comment": None,
        "items": [
            {"foodName": "Pan", "quantity": "2 rebanadas"},
            {"foodName": "Huevo", "quantity": "1 unidad"},
        ],
    }
    base.update(overrides)
    return base


def test_meal_maps_items_with_free_text_quantity():
    result = parse_meals([make_doc("m-1", **meal_fields())])
    (meal,) = result.records
    assert meal.type is MealType.BREAKFAST
    assert [(i.food_name, i.quantity) for i in meal.items] == [
        ("Pan", "2 rebanadas"),
        ("Huevo", "1 unidad"),
    ]
    assert result.issues == ()


def test_meal_without_items_field_has_no_items():
    fields = {k: v for k, v in meal_fields().items() if k != "items"}
    (meal,) = parse_meals([make_doc("m-1", **fields)]).records
    assert meal.items == ()


def test_meal_with_unknown_type_keeps_none_and_warns():
    result = parse_meals([make_doc("m-1", **meal_fields(type="brunch"))])
    assert result.records[0].type is None
    assert result.issues[0].severity == "warning"


def test_meal_with_invalid_date_is_rejected():
    result = parse_meals([make_doc("m-1", **meal_fields(eatenAt=""))])
    assert result.records == ()
    assert result.issues[0].severity == "error"


def test_meal_item_without_name_is_skipped_with_warning():
    items = [{"quantity": "1"}, {"foodName": "Pan", "quantity": "1"}]
    result = parse_meals([make_doc("m-1", **meal_fields(items=items))])
    assert [i.food_name for i in result.records[0].items] == ["Pan"]
    assert result.issues[0].severity == "warning"


# ---------- Medicamentos ----------
def intake_fields(**overrides):
    base = {
        "uuid": "t-1",
        "takenAt": "2026-08-19T08:00:00.000",
        "comment": None,
        "items": [
            {
                "medicationName": "Metformina",
                "defaultUnit": "milligram",
                "quantity": 500,
                "unit": "milligram",
                "customUnitLabel": None,
            },
            {
                "medicationName": "Parche X",
                "defaultUnit": "other",
                "quantity": 1.5,
                "unit": "other",
                "customUnitLabel": "parche",
            },
        ],
    }
    base.update(overrides)
    return base


def test_intake_maps_dose_quantity_and_unit_labels():
    (intake,) = parse_intakes([make_doc("t-1", **intake_fields())]).records
    first, second = intake.items
    assert (first.medication_name, first.quantity, first.unit) == (
        "Metformina",
        500.0,
        DoseUnit.MILLIGRAM,
    )
    assert first.unit_label == "mg"
    assert second.unit_label == "parche"  # unidad "other" usa la etiqueta propia


def test_intake_item_with_unknown_unit_or_missing_quantity_is_skipped_with_warning():
    items = [
        {"medicationName": "A", "quantity": 1, "unit": "cucharada"},
        {"medicationName": "B", "unit": "milligram"},
        {"medicationName": "C", "quantity": 2, "unit": "tablet"},
    ]
    result = parse_intakes([make_doc("t-1", **intake_fields(items=items))])
    assert [i.medication_name for i in result.records[0].items] == ["C"]
    assert len([i for i in result.issues if i.severity == "warning"]) == 2


def test_intake_with_invalid_date_is_rejected():
    result = parse_intakes([make_doc("t-1", **intake_fields(takenAt="x"))])
    assert result.records == ()


# ---------- Biometría ----------
def bio_fields(**overrides):
    base = {
        "uuid": "b-1",
        "weightKg": 82.4,
        "systolicPressure": 128,
        "diastolicPressure": 82,
        "heartRateBpm": 70,
        "measuredAt": "2026-08-19T07:30:00.000",
        "comment": None,
    }
    base.update(overrides)
    return base


def test_biometric_maps_all_fields():
    result = parse_biometrics([make_doc("b-1", **bio_fields())])
    (record,) = result.records
    assert (record.weight_kg, record.systolic, record.diastolic, record.heart_rate_bpm) == (
        82.4,
        128,
        82,
        70,
    )
    assert result.issues == ()


def test_biometric_integer_weight_is_accepted_as_float():
    (record,) = parse_biometrics([make_doc("b-1", **bio_fields(weightKg=80))]).records
    assert record.weight_kg == 80.0


def test_biometric_optional_fields_stay_none_not_zero():
    fields = bio_fields(systolicPressure=None, diastolicPressure=None, heartRateBpm=None)
    (record,) = parse_biometrics([make_doc("b-1", **fields)]).records
    assert (record.systolic, record.diastolic, record.heart_rate_bpm) == (None, None, None)


def test_biometric_missing_weight_is_rejected():
    fields = {k: v for k, v in bio_fields().items() if k != "weightKg"}
    result = parse_biometrics([make_doc("b-1", **fields)])
    assert result.records == ()
    assert result.issues[0].severity == "error"


@pytest.mark.parametrize("bad_weight", [float("nan"), float("inf")])
def test_biometric_non_finite_weight_is_rejected(bad_weight):
    result = parse_biometrics([make_doc("b-1", **bio_fields(weightKg=bad_weight))])
    assert result.records == ()
    assert result.issues[0].severity == "error"


def test_intake_non_finite_dose_is_skipped_with_warning():
    items = [
        {"medicationName": "A", "quantity": float("nan"), "unit": "tablet"},
        {"medicationName": "B", "quantity": float("inf"), "unit": "tablet"},
    ]
    result = parse_intakes([make_doc("t-1", **intake_fields(items=items))])
    assert result.records[0].items == ()
    assert len(result.issues) == 2


@pytest.mark.parametrize("bad_items", ["texto", {"a": 1}, 5])
def test_items_of_unexpected_type_produce_one_warning_not_one_per_character(bad_items):
    meal = parse_meals([make_doc("m-1", **meal_fields(items=bad_items))])
    intake = parse_intakes([make_doc("t-1", **intake_fields(items=bad_items))])
    assert meal.records[0].items == () and len(meal.issues) == 1
    assert intake.records[0].items == () and len(intake.issues) == 1


def test_biometric_half_pressure_pair_and_out_of_range_warn_but_keep():
    result = parse_biometrics(
        [
            make_doc("b-1", **bio_fields(uuid="b-1", diastolicPressure=None)),
            make_doc("b-2", **bio_fields(uuid="b-2", weightKg=500.0)),
        ]
    )
    assert len(result.records) == 2
    assert {i.doc_id for i in result.issues if i.severity == "warning"} == {"b-1", "b-2"}
