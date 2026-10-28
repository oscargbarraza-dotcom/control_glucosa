"""Normalización básica de nombres de alimentos (solo para AGRUPAR; el texto original no se toca)."""

import pytest

from glucosa.models.foods import normalize_food_name


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("Pan", "pan"),
        ("PAN", "pan"),
        ("  pan  integral ", "pan integral"),
        ("pan \tintegral\n", "pan integral"),  # espacio duro, tabulación y salto de línea
        ("Plátano", "platano"),
        ("Café con   leche", "cafe con leche"),
        ("Güisqui", "guisqui"),
        ("ÁÉÍÓÚ", "aeiou"),
        ("ﬁambre", "fiambre"),  # ligadura tipográfica
    ],
)
def test_case_accents_and_spaces_are_normalized(original, expected):
    assert normalize_food_name(original) == expected


def test_the_letter_enie_is_kept_because_it_is_a_different_letter():
    assert normalize_food_name("Piña") == "piña"
    assert normalize_food_name("Piña") != normalize_food_name("Pina")
    assert normalize_food_name("AÑO") == "año"


def test_normalization_is_idempotent():
    for text in ("  Plátano   MADURO ", "Piña", "pan"):
        once = normalize_food_name(text)
        assert normalize_food_name(once) == once


def test_synonyms_plurals_and_punctuation_are_not_merged():
    assert normalize_food_name("huevo") != normalize_food_name("huevos")
    assert normalize_food_name("palta") != normalize_food_name("aguacate")
    assert normalize_food_name("Pan.") == "pan."  # solo mayúsculas, tildes y espacios


def test_text_with_nothing_left_normalizes_to_empty_text():
    assert normalize_food_name("   ") == ""
    assert normalize_food_name("") == ""


def test_the_original_string_is_never_modified():
    original = "  Plátano "
    normalize_food_name(original)
    assert original == "  Plátano "
