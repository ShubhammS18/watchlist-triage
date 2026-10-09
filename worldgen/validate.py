"""A small validator for worldgen/schema/world.schema.json. Standard library only.

Supports just what the schema file uses: type (string, integer, boolean, array, object), required, properties,
pattern, minLength, format "date" (a real calendar date written YYYY-MM-DD), format "date-or-empty" (the same,
or an empty string) and notAfter (the date may not be later than the named date field of the same record).
Extra fields are allowed. An evidence item (a record with `field` and `value`) has its value checked against
the rule of the field it names, so a date shown to the agent is held to the same rule as the record's date.
"""
import json
import re
from datetime import date

from . import ROOT

_TYPES = {"string": str, "integer": int, "boolean": bool, "array": list, "object": dict}


def load_schema():
    return json.loads(ROOT.joinpath("schema", "world.schema.json").read_text(encoding="utf-8"))


def _type_ok(value, name):
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[name])


def _problems(value, rule):
    if "type" in rule and not _type_ok(value, rule["type"]):
        return [f"expected {rule['type']}"]
    found = []
    if "minLength" in rule and len(value) < rule["minLength"]:
        found.append(f"shorter than {rule['minLength']}")
    if "pattern" in rule and not re.search(rule["pattern"], value):
        found.append(f"does not match {rule['pattern']}")
    if rule.get("format") in ("date", "date-or-empty") and not (value == "" and rule["format"] == "date-or-empty"):
        if _as_date(value) is None:
            found.append("not a calendar date written YYYY-MM-DD")
    return found


def _as_date(value):
    """The date a YYYY-MM-DD string names, or None if it is not exactly that form or not a real calendar date."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate(record, schema=None):
    """Return a list of problems; an empty list means the record is valid."""
    schema = schema or load_schema()
    if not _type_ok(record, schema.get("type", "object")):
        return ["record is not an object"]
    errors = [f"missing field: {key}" for key in schema.get("required", []) if key not in record]
    properties = schema.get("properties", {})
    checked = [(key, key, record[key]) for key in properties if key in record]
    if isinstance(record.get("field"), str) and record["field"] in properties and "value" in record:
        checked.append((record["field"], "value", record["value"]))          # an evidence item showing that field
    for key, shown_as, value in checked:
        rule = properties[key]
        errors.extend(f"{shown_as}: {message}" for message in _problems(value, rule))
        limit = _as_date(record.get(rule.get("notAfter", "")))
        if limit and (_as_date(value) or limit) > limit:
            errors.append(f"{shown_as}: later than {rule['notAfter']}")
    return errors
