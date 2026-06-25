from __future__ import annotations

from typing import Any

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def validate_arg_types(args: dict[str, Any], parameters: dict[str, Any]) -> list[str]:
    """Return a list of type-mismatch error strings for args against a JSON Schema parameters block.

    Only validates properties that are both defined in the schema and present in args.
    Unknown extra args are ignored (caller decides whether to reject them).
    """
    errors: list[str] = []
    properties: dict[str, Any] = parameters.get("properties", {})
    for name, value in args.items():
        prop_schema = properties.get(name)
        if prop_schema is None:
            continue
        expected_type = prop_schema.get("type")
        if expected_type is None or expected_type not in _TYPE_MAP:
            continue
        py_type = _TYPE_MAP[expected_type]
        # bool is a subclass of int in Python; reject bool when integer is expected
        if expected_type == "integer" and isinstance(value, bool):
            errors.append(f"Arg '{name}' must be integer, got boolean")
        elif not isinstance(value, py_type):
            errors.append(
                f"Arg '{name}' must be {expected_type}, got {type(value).__name__}"
            )
    return errors
