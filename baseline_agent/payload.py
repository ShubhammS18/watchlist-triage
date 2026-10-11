"""What the agent is given for one alert (DEC-T05-PAYLOAD, AC-21). Python standard library only.

The payload is built from an allowlist: four named fields of each evidence item, one review date and the number
of items. Anything else on an item is left out, whatever it is called.
"""
SCHEMA_VERSION = "1"
ITEM_KEYS = ("id", "kind", "field", "value")


class PayloadError(ValueError):
    """The evidence items cannot be made into a payload."""


def build_payload(items):
    """The payload for one alert, from its evidence items as worldgen.loader or framings.frame returns them.

    `item_count` lets the receiving side notice a payload that lost items on the way.
    """
    items = list(items)
    if not items:
        raise PayloadError("an alert with no evidence items cannot be made into a payload")
    dates = sorted({item["as_of_date"] for item in items})
    if len(dates) != 1:
        raise PayloadError(f"the evidence items of one alert must share one as_of_date, found {dates}")
    return {"schema_version": SCHEMA_VERSION, "as_of_date": dates[0], "item_count": len(items),
            "items": [{key: item[key] for key in ITEM_KEYS} for item in items]}
