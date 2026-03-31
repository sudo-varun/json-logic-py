"""
Tests for jsonLogic.
"""

import json
from urllib.request import urlopen

import pytest

from json_logic import jsonLogic

# ---------------------------------------------------------------------------
# Local unit tests
# ---------------------------------------------------------------------------


class TestVar:
    """Retrieve data from the provided data object."""

    def test_simple_key(self) -> None:
        assert jsonLogic({"var": ["a"]}, {"a": 1, "b": 2}) == 1

    def test_sugar_single_value(self) -> None:
        assert jsonLogic({"var": "a"}, {"a": 1, "b": 2}) == 1

    def test_default_value(self) -> None:
        assert jsonLogic({"var": ["z", 26]}, {"a": 1, "b": 2}) == 26

    def test_dot_notation(self) -> None:
        assert (
            jsonLogic(
                {"var": "champ.name"},
                {
                    "champ": {"name": "Fezzig", "height": 223},
                    "challenger": {"name": "Dread Pirate Roberts", "height": 183},
                },
            )
            == "Fezzig"
        )

    def test_array_index(self) -> None:
        assert jsonLogic({"var": 1}, ["apple", "banana", "carrot"]) == "banana"

    def test_complex_rule(self) -> None:
        assert jsonLogic(
            {"and": [
                {"<": [{"var": "temp"}, 110]},
                {"==": [{"var": "pie.filling"}, "apple"]},
            ]},
            {"temp": 100, "pie": {"filling": "apple"}},
        )


class TestMissing:
    """missing operator."""

    def test_one_missing(self) -> None:
        assert jsonLogic({"missing": ["a", "b"]}, {"a": "apple", "c": "carrot"}) == ["b"]

    def test_none_missing(self) -> None:
        assert jsonLogic({"missing": ["a", "b"]}, {"a": "apple", "b": "banana"}) == []

    def test_with_if(self) -> None:
        assert (
            jsonLogic(
                {"if": [{"missing": ["a", "b"]}, "Not enough fruit", "OK to proceed"]},
                {"a": "apple", "b": "banana"},
            )
            == "OK to proceed"
        )


class TestMissingSome:
    """missing_some operator."""

    def test_minimum_met(self) -> None:
        assert jsonLogic({"missing_some": [1, ["a", "b", "c"]]}, {"a": "apple"}) == []

    def test_minimum_not_met(self) -> None:
        assert jsonLogic({"missing_some": [2, ["a", "b", "c"]]}, {"a": "apple"}) == ["b", "c"]

    def test_complex_with_merge(self) -> None:
        rule = {
            "if": [
                {"merge": [
                    {"missing": ["first_name", "last_name"]},
                    {"missing_some": [1, ["cell_phone", "home_phone"]]},
                ]},
                "We require first name, last name, and one phone number.",
                "OK to proceed",
            ]
        }
        assert (
            jsonLogic(rule, {"first_name": "Bruce", "last_name": "Wayne"})
            == "We require first name, last name, and one phone number."
        )


class TestIf:
    """if operator."""

    def test_true_branch(self) -> None:
        assert jsonLogic({"if": [True, "yes", "no"]}) == "yes"

    def test_false_branch(self) -> None:
        assert jsonLogic({"if": [False, "yes", "no"]}) == "no"

    def test_multi_branch(self) -> None:
        assert (
            jsonLogic(
                {"if": [
                    {"<": [{"var": "temp"}, 0]}, "freezing",
                    {"<": [{"var": "temp"}, 100]}, "liquid",
                    "gas",
                ]},
                {"temp": 200},
            )
            == "gas"
        )


class TestEquality:
    def test_soft_equal_numbers(self) -> None:
        assert jsonLogic({"==": [1, 1]})

    def test_soft_equal_coercion(self) -> None:
        assert jsonLogic({"==": [1, "1"]})

    def test_soft_equal_bool(self) -> None:
        assert jsonLogic({"==": [0, False]})

    def test_strict_equal(self) -> None:
        assert jsonLogic({"===": [1, 1]})

    def test_strict_equal_no_coercion(self) -> None:
        assert not jsonLogic({"===": [1, "1"]})

    def test_not_equal(self) -> None:
        assert jsonLogic({"!=": [1, 2]})
        assert not jsonLogic({"!=": [1, "1"]})

    def test_strict_not_equal(self) -> None:
        assert jsonLogic({"!==": [1, 2]})
        assert jsonLogic({"!==": [1, "1"]})


class TestLogical:
    def test_not_array(self) -> None:
        assert not jsonLogic({"!": [True]})

    def test_not_scalar(self) -> None:
        assert not jsonLogic({"!": True})

    def test_or_true(self) -> None:
        assert jsonLogic({"or": [True, False]})
        assert jsonLogic({"or": [False, True]})

    def test_or_first_truthy(self) -> None:
        assert jsonLogic({"or": [False, "apple"]}) == "apple"
        assert jsonLogic({"or": [False, None, "apple"]}) == "apple"

    def test_and_all_true(self) -> None:
        assert jsonLogic({"and": [True, True]})

    def test_and_short_circuit(self) -> None:
        assert not jsonLogic({"and": [True, True, True, False]})
        assert not jsonLogic({"and": [True, "apple", False]})

    def test_and_last_value(self) -> None:
        assert jsonLogic({"and": [True, "apple", 3.14]}) == 3.14


class TestComparisons:
    def test_greater_than(self) -> None:
        assert jsonLogic({">": [2, 1]})

    def test_greater_or_equal(self) -> None:
        assert jsonLogic({">=": [1, 1]})

    def test_less_than(self) -> None:
        assert jsonLogic({"<": [1, 2]})

    def test_less_or_equal(self) -> None:
        assert jsonLogic({"<=": [1, 1]})

    def test_between_exclusive(self) -> None:
        assert jsonLogic({"<": [1, 2, 3]})
        assert not jsonLogic({"<": [1, 1, 3]})
        assert not jsonLogic({"<": [1, 4, 3]})

    def test_between_inclusive(self) -> None:
        assert jsonLogic({"<=": [1, 2, 3]})
        assert jsonLogic({"<=": [1, 1, 3]})
        assert not jsonLogic({"<=": [1, 4, 3]})

    def test_between_with_var(self) -> None:
        assert jsonLogic({"<": [0, {"var": "temp"}, 100]}, {"temp": 37})


class TestArithmetic:
    def test_add(self) -> None:
        assert jsonLogic({"+": [1, 1]}) == 2

    def test_multiply(self) -> None:
        assert jsonLogic({"*": [2, 3]}) == 6

    def test_subtract(self) -> None:
        assert jsonLogic({"-": [3, 2]}) == 1

    def test_divide(self) -> None:
        assert jsonLogic({"/": [2, 4]}) == 0.5

    def test_add_many(self) -> None:
        assert jsonLogic({"+": [1, 1, 1, 1, 1]}) == 5

    def test_multiply_many(self) -> None:
        assert jsonLogic({"*": [2, 2, 2, 2, 2]}) == 32

    def test_negate(self) -> None:
        assert jsonLogic({"-": [2]}) == -2
        assert jsonLogic({"-": [-2]}) == 2

    def test_cast_to_number(self) -> None:
        assert jsonLogic({"+": "0"}) == 0

    def test_max_min(self) -> None:
        assert jsonLogic({"max": [1, 2, 3]}) == 3
        assert jsonLogic({"min": [1, 2, 3]}) == 1

    def test_modulo(self) -> None:
        assert jsonLogic({"%": [101, 2]}) == 1


class TestStringOps:
    def test_in_substring(self) -> None:
        assert jsonLogic({"in": ["Spring", "Springfield"]})

    def test_cat(self) -> None:
        assert jsonLogic({"cat": ["I love", " pie"]}) == "I love pie"

    def test_cat_with_var(self) -> None:
        assert (
            jsonLogic(
                {"cat": ["I love ", {"var": "filling"}, " pie"]},
                {"filling": "apple", "temp": 110},
            )
            == "I love apple pie"
        )


class TestMerge:
    def test_arrays(self) -> None:
        assert jsonLogic({"merge": [[1, 2], [3, 4]]}) == [1, 2, 3, 4]

    def test_scalars_and_array(self) -> None:
        assert jsonLogic({"merge": [1, 2, [3, 4]]}) == [1, 2, 3, 4]

    def test_with_missing(self) -> None:
        rule = {
            "missing": {
                "merge": [
                    "vin",
                    {"if": [{"var": "financing"}, ["apr", "term"], []]},
                ]
            }
        }
        assert jsonLogic(rule, {"financing": True}) == ["vin", "apr", "term"]
        assert jsonLogic(rule, {"financing": False}) == ["vin"]


class TestLog:
    def test_passthrough(self) -> None:
        assert jsonLogic({"log": "apple"}) == "apple"


class TestUnknownOperator:
    def test_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized operation"):
            jsonLogic({"bogus": [1, 2]})


# ---------------------------------------------------------------------------
# Shared tests from jsonlogic.com/tests.json
# ---------------------------------------------------------------------------

def _load_shared_tests() -> list[tuple[object, object, object]]:
    try:
        raw = urlopen("http://jsonlogic.com/tests.json", timeout=10).read().decode()
        return [tuple(item) for item in json.loads(raw) if isinstance(item, list)]  # type: ignore[return-value]
    except Exception:
        return []


_SHARED = _load_shared_tests()


@pytest.mark.parametrize("logic,data,expected", _SHARED)
def test_shared(logic: object, data: object, expected: object) -> None:
    assert jsonLogic(logic, data) == expected  # type: ignore[arg-type]

