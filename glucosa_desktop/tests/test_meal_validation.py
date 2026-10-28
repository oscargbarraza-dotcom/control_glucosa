"""Validaciones adicionales de comidas al leer Firestore (avisos; nunca se descartan registros por ellas)."""

from glucosa.data.parsing import parse_meals
from tests.conftest import make_doc


def doc(doc_id, **overrides):
    fields = {
        "uuid": doc_id,
        "type": "lunch",
        "eatenAt": "2026-10-20T13:30:00.000000",
        "comment": None,
        "items": [
            {"foodName": "Arroz", "quantity": "1 tz"},
            {"foodName": "Pollo", "quantity": "150 g"},
        ],
    }
    fields.update(overrides)
    return make_doc(doc_id, **fields)


def messages(result):
    return [issue.message for issue in result.issues]


def test_a_clean_meal_has_no_issues():
    result = parse_meals([doc("m-1")])

    assert result.issues == () and len(result.records) == 1


def test_a_meal_without_foods_is_kept_with_a_warning():
    result = parse_meals([doc("m-1", items=[])])

    assert len(result.records) == 1
    assert any("sin alimentos" in m.lower() for m in messages(result))
    assert {i.severity for i in result.issues} == {"warning"}


def test_a_meal_with_the_items_field_missing_is_also_flagged():
    fields = {
        "uuid": "m-1",
        "type": "lunch",
        "eatenAt": "2026-10-20T13:30:00.000000",
        "comment": None,
    }

    result = parse_meals([make_doc("m-1", **fields)])

    assert len(result.records) == 1 and any("sin alimentos" in m.lower() for m in messages(result))


def test_the_same_food_written_twice_in_one_meal_is_flagged_but_kept():
    items = [{"foodName": "Pan", "quantity": "1"}, {"foodName": " pan ", "quantity": "2"}]

    result = parse_meals([doc("m-1", items=items)])

    assert len(result.records[0].items) == 2  # no se fusiona ni se descarta nada
    assert any("repetido" in m.lower() for m in messages(result))


def test_different_foods_in_one_meal_are_not_flagged_as_repeated():
    result = parse_meals([doc("m-1")])

    assert not any("repetido" in m.lower() for m in messages(result))


def test_two_documents_with_same_time_type_and_foods_are_flagged_as_possible_duplicates():
    result = parse_meals([doc("m-1"), doc("m-2")])

    assert len(result.records) == 2  # ambos se conservan
    assert any("posible duplicado" in m.lower() for m in messages(result))
    assert any(i.doc_id == "m-2" for i in result.issues if "duplicado" in i.message.lower())


def test_the_duplicate_check_ignores_case_accents_and_item_order():
    first = doc(
        "m-1",
        items=[{"foodName": "Arroz", "quantity": "1"}, {"foodName": "Plátano", "quantity": "1"}],
    )
    second = doc(
        "m-2",
        items=[{"foodName": "platano", "quantity": "2"}, {"foodName": "ARROZ", "quantity": "1"}],
    )

    result = parse_meals([first, second])

    assert any("posible duplicado" in m.lower() for m in messages(result))


def test_meals_that_differ_in_time_type_or_foods_are_not_duplicates():
    different_time = doc("m-2", eatenAt="2026-10-20T13:31:00.000000")
    different_type = doc("m-3", type="dinner")
    different_food = doc("m-4", items=[{"foodName": "Pan", "quantity": "1"}])

    result = parse_meals([doc("m-1"), different_time, different_type, different_food])

    assert not any("duplicado" in m.lower() for m in messages(result))


def test_two_meals_without_foods_at_the_same_time_and_type_are_not_reported_as_duplicates():
    result = parse_meals([doc("m-1", items=[]), doc("m-2", items=[])])

    assert not any(
        "duplicado" in m.lower() for m in messages(result)
    )  # solo el aviso de «sin alimentos»


def test_issues_never_contain_food_names_or_comments():
    items = [
        {"foodName": "AlimentoSecreto", "quantity": "1"},
        {"foodName": "alimentosecreto", "quantity": "2"},
    ]

    result = parse_meals(
        [
            doc("m-1", items=items, comment="ObservaciónSecreta"),
            doc("m-2", items=items, comment="x"),
        ]
    )

    text = " ".join(messages(result))
    assert "secreto" not in text.lower() and "Observación" not in text


def test_the_new_checks_do_not_change_the_parsed_records():
    docs = [doc("m-1"), doc("m-2", items=[])]

    with_checks = parse_meals(docs)

    assert [r.uuid for r in with_checks.records] == ["m-1", "m-2"]
    assert with_checks.records[1].items == ()
