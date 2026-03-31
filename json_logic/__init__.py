"""
json-logic-py
~~~~~~~~~~~~~

A Python implementation of the JsonLogic rule engine.
See https://jsonlogic.com for the specification.
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["jsonLogic", "operations"]
__version__ = "1.0.0"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Data = dict[str, Any] | list[Any] | None
Rule = dict[str, Any] | list[Any] | str | int | float | bool | None


# ---------------------------------------------------------------------------
# Operator helpers
# ---------------------------------------------------------------------------


def if_(*args: Any) -> Any:
    """Implement the ``if`` operator with support for multiple elseif branches."""
    for i in range(0, len(args) - 1, 2):
        if args[i]:
            return args[i + 1]
    if len(args) % 2:
        return args[-1]
    return None


def soft_equals(a: Any, b: Any) -> bool:
    """Implement ``==`` with JS-style type coercion."""
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) is bool(b)
    return a == b  # type: ignore[no-any-return]


def hard_equals(a: Any, b: Any) -> bool:
    """Implement ``===`` (strict equality, no coercion)."""
    if type(a) is not type(b):
        return False
    return a == b  # type: ignore[no-any-return]


def less(a: Any, b: Any, *args: Any) -> bool:
    """Implement ``<`` with JS-style numeric coercion and optional between-form."""
    if {type(a), type(b)} & {float, int}:
        try:
            a, b = float(a), float(b)
        except (TypeError, ValueError):
            return False  # NaN-like behaviour
    return a < b and (not args or less(b, *args))


def less_or_equal(a: Any, b: Any, *args: Any) -> bool:
    """Implement ``<=`` with JS-style numeric coercion and optional between-form."""
    return (less(a, b) or soft_equals(a, b)) and (not args or less_or_equal(b, *args))


def to_numeric(arg: Any) -> int | float:
    """Convert *arg* to ``int`` or ``float``, preserving the distinction.

    ``"0"`` → ``0`` (int), ``"1.5"`` → ``1.5`` (float), numbers pass through.
    This mirrors JS unary ``+`` coercion used by the ``+`` operator.
    """
    if isinstance(arg, str):
        try:
            return int(arg)
        except ValueError:
            return float(arg)
    if isinstance(arg, (int, float)):
        return arg
    return int(arg)


def plus(*args: Any) -> int | float:
    """Sum all arguments, converting strings to numbers first."""
    result: int | float = 0
    for arg in args:
        result = result + to_numeric(arg)
    return result


def minus(*args: Any) -> int | float:
    """Subtract or negate, converting strings to numbers first."""
    if len(args) == 1:
        return -to_numeric(args[0])
    return to_numeric(args[0]) - to_numeric(args[1])


def multiply(*args: Any) -> float:
    """Multiply all arguments together, converting to float first."""
    result = 1.0
    for arg in args:
        result *= float(arg)
    return result


def merge(*args: Any) -> list[Any]:
    """Merge one or more lists (or scalars) into a single flat list."""
    result: list[Any] = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            result.extend(arg)
        else:
            result.append(arg)
    return result


def get_var(data: Any, var_name: Any = None, not_found: Any = None) -> Any:
    """Retrieve a value from *data* using dot-notation *var_name*.

    An empty string or ``None`` *var_name* returns the whole data object.
    """
    if var_name is None or var_name == "" or var_name == []:
        return data
    try:
        for key in str(var_name).split("."):
            try:
                data = data[key]
            except TypeError:
                data = data[int(key)]
    except (KeyError, TypeError, ValueError):
        return not_found
    return data


def missing(data: Any, *args: Any) -> list[Any]:
    """Return a list of keys from *args* that are absent in *data*."""
    sentinel = object()
    keys = args[0] if args and isinstance(args[0], list) else args
    return [key for key in keys if get_var(data, key, sentinel) is sentinel]


def missing_some(data: Any, min_required: int, args: list[Any]) -> list[Any]:
    """Return missing keys when fewer than *min_required* of *args* are present."""
    if min_required < 1:
        return []
    sentinel = object()
    found = 0
    absent: list[Any] = []
    for arg in args:
        if get_var(data, arg, sentinel) is sentinel:
            absent.append(arg)
        else:
            found += 1
            if found >= min_required:
                return []
    return absent


def substr(source: Any, start: Any, length: Any = None) -> str:
    """Implement ``substr`` matching JS String.prototype.substr semantics."""
    src: str = str(source)
    s: int = int(start)
    if s < 0:
        s = max(len(src) + s, 0)
    if length is None:
        return src[s:]
    n: int = int(length)
    if n < 0:
        return src[s : len(src) + n]
    return src[s : s + n]


def _log_and_return(a: Any) -> Any:
    """Log *a* at INFO level and return it unchanged."""
    logger.info(a)
    return a


# ---------------------------------------------------------------------------
# Operations registry
# ---------------------------------------------------------------------------

operations: dict[str, Any] = {
    "==": soft_equals,
    "===": hard_equals,
    "!=": lambda a, b: not soft_equals(a, b),
    "!==": lambda a, b: not hard_equals(a, b),
    ">": lambda a, b: less(b, a),
    ">=": lambda a, b: less(b, a) or soft_equals(a, b),
    "<": less,
    "<=": less_or_equal,
    "!": lambda a: not a,
    "!!": bool,
    "%": lambda a, b: a % b,
    "and": lambda *args: next((a for a in args if not a), args[-1] if args else True),
    "or": lambda *args: next((a for a in args if a), args[-1] if args else False),
    "?:": lambda a, b, c: b if a else c,
    "if": if_,
    "log": _log_and_return,
    "in": lambda a, b: a in b if hasattr(b, "__contains__") else False,
    "cat": lambda *args: "".join(str(arg) for arg in args),
    "+": plus,
    "*": multiply,
    "-": minus,
    "/": lambda a, b=None: a if b is None else float(a) / float(b),
    "min": lambda *args: min(args),
    "max": lambda *args: max(args),
    "merge": merge,
    "count": lambda *args: sum(1 for a in args if a),
    "substr": substr,
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def jsonLogic(tests: Rule, data: Data = None) -> Any:  # noqa: N802
    """
    Evaluate *tests* (a JsonLogic rule) against *data*.

    Parameters
    ----------
    tests:
        A JsonLogic rule encoded as a Python object (usually a ``dict``).
    data:
        The data context to evaluate the rule against.

    Returns
    -------
    Any
        The result of evaluating the rule.
    """
    # Primitive value – return as-is
    if tests is None or not isinstance(tests, (dict, list)):
        return tests

    # A plain list: evaluate each element and return the resulting list
    if isinstance(tests, list):
        return [jsonLogic(item, data) for item in tests]

    data = data or {}

    operator = next(iter(tests))
    values: Any = tests[operator]

    # Unary sugar: {"var": "x"} instead of {"var": ["x"]}
    if not isinstance(values, (list, tuple)):
        values = [values]

    # Special operators whose arguments must NOT be pre-evaluated
    match operator:
        case "var":
            return get_var(data, *[jsonLogic(v, data) for v in values])
        case "missing":
            return missing(data, *[jsonLogic(v, data) for v in values])
        case "missing_some":
            return missing_some(data, *[jsonLogic(v, data) for v in values])
        case "filter":
            arr = jsonLogic(values[0], data)
            sub_rule = values[1]
            return [item for item in (arr or []) if jsonLogic(sub_rule, item)]
        case "map":
            arr = jsonLogic(values[0], data)
            sub_rule = values[1]
            return [jsonLogic(sub_rule, item) for item in (arr or [])]
        case "reduce":
            arr = jsonLogic(values[0], data)
            sub_rule = values[1]
            initial = jsonLogic(values[2], data) if len(values) > 2 else None
            result = initial
            for item in (arr or []):
                result = jsonLogic(sub_rule, {"current": item, "accumulator": result})
            return result
        case "all":
            arr = jsonLogic(values[0], data)
            sub_rule = values[1]
            return bool(arr) and all(jsonLogic(sub_rule, item) for item in arr)
        case "none":
            arr = jsonLogic(values[0], data)
            sub_rule = values[1]
            return not any(jsonLogic(sub_rule, item) for item in (arr or []))
        case "some":
            arr = jsonLogic(values[0], data)
            sub_rule = values[1]
            return any(jsonLogic(sub_rule, item) for item in (arr or []))

    # Recursively evaluate all child rules before passing to the operator
    evaluated = [jsonLogic(v, data) for v in values]

    if operator not in operations:
        raise ValueError(f"Unrecognized operation: {operator!r}")

    return operations[operator](*evaluated)

