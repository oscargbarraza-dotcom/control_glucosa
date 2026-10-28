import pytest

from glucosa.analytics.bmi import BmiCategory, BmiResult, bmi_category, compute_bmi


def test_bmi_is_weight_over_height_squared_and_reports_the_height_used():
    result = compute_bmi(weight_kg=80.0, height_cm=180.0)
    assert result == BmiResult(value=pytest.approx(24.69, abs=0.01), height_cm_used=180.0)


@pytest.mark.parametrize(
    ("bmi", "category"),
    [
        (18.4, BmiCategory.UNDERWEIGHT),
        (18.5, BmiCategory.NORMAL),
        (24.9, BmiCategory.NORMAL),
        (25.0, BmiCategory.OVERWEIGHT),
        (29.9, BmiCategory.OVERWEIGHT),
        (30.0, BmiCategory.OBESE),
    ],
)
def test_who_adult_categories(bmi, category):
    assert bmi_category(bmi) is category


def test_no_height_means_no_bmi_instead_of_a_guess():
    assert compute_bmi(weight_kg=80.0, height_cm=None) is None


@pytest.mark.parametrize(("weight", "height"), [(0, 170.0), (-5, 170.0), (80.0, 0)])
def test_non_positive_inputs_are_rejected(weight, height):
    with pytest.raises(ValueError):
        compute_bmi(weight_kg=weight, height_cm=height)
