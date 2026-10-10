"""Three presentations of one alert for task T03 (FR-21). Python standard library only.

Framing 1 is the alert as the world holds it. Framings 2 and 3 change the field order, the name format and the
wording of the notes, and nothing else. `frame` is a pure function: it writes nothing and reads no file beyond
the title list that worldgen.matcher already loads.
"""
from worldgen.matcher import load_titles

from .names import format_name
from .order import reorder
from .recognise import which_original
from .wording import alternate

FRAMINGS = (1, 2, 3)
NAME_FIELDS = ("name", "alias")
TITLES = load_titles()


def _name(items, kind):
    """The one name an alert carries for `kind`, as written in the world."""
    names = [item["value"] for item in items if item["kind"] == kind and item["field"] == "name"]
    if len(names) != 1:
        raise ValueError(f"expected one {kind} name, found {len(names)}")
    return names[0]


def frame(alert, framing):
    """The evidence items of `alert` as framing 1, 2 or 3 presents them, as new dicts. Evidence ids never change.

    `alert` is one alert with its items under "evidence", the shape worldgen.loader and worldgen.harness_twins
    return. A note that is one of the injected texts is returned as written.
    """
    if framing not in FRAMINGS:
        raise ValueError(f"framing must be one of {FRAMINGS}, not {framing!r}")
    items = alert["evidence"]
    if framing == 1:
        return [dict(item) for item in items]
    customer, listed = _name(items, "customer_field"), _name(items, "watchlist_field")
    framed = []
    for item in reorder(items, framing):
        item = dict(item)
        if item["kind"] == "snippet":
            original = which_original(item["value"], customer, listed)
            if original is not None:
                item["value"] = alternate(*original, framing).format(c=format_name(customer, framing, TITLES),
                                                                     w=format_name(listed, framing, TITLES))
        elif item["field"] in NAME_FIELDS:
            item["value"] = format_name(item["value"], framing, TITLES)
        framed.append(item)
    return framed
