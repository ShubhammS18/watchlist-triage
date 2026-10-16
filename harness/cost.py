"""Model cost and modelled review time (FR-22, NFR-6, DEC-T06-COST, DEC-T06-MODELLED-TIME). Python standard
library only. Every sum here is in exact fractions; a float is never used.

An amount is {"numerator", "denominator", "not_applicable", "decimal", "rounded"}: the exact value as a fraction,
and a decimal string that is exact unless `rounded` says it was cut to six places.
"""
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from fractions import Fraction

UNIT_PRICE = "per million tokens"
UNIT_TIME = "minutes"
SETS = ("LOW", "BASE", "HIGH")
PARAMETERS = ("manual_clearing", "proposal_review", "l2", "second_review")
POLICIES = ("STRICT_FOUR_EYES", "none")  # every close second-reviewed, or none: QA_SAMPLING comes with FR-13
KINDS = ("fixture", "sourced")
NOTE_LIMIT = 500  # characters in the optional note of a price table or a modelled-time file  # a fixture holds made-up test values; a sourced file says where each value is from


class TableError(ValueError):
    """A price table or a modelled-time parameter file has the wrong shape."""


def _number(value, name):
    try:
        number = Decimal(value) if isinstance(value, str) else None
    except InvalidOperation:
        number = None
    if number is None or not number.is_finite() or number < 0:
        raise TableError(f"{name} must be a decimal string of 0 or more, not {value!r}")
    return Fraction(number)


def _keys(value, required, name):
    """Every file says what kind it is. A sourced file must also hold "sources"; a fixture must not."""
    if not isinstance(value, dict) or value.get("kind") not in KINDS:
        raise TableError(f"{name} must say its kind: one of {list(KINDS)}")
    wanted = {*required, "kind"} | ({"sources"} if value["kind"] == "sourced" else set())
    if not wanted <= set(value) or set(value) - wanted - {"note"}:
        raise TableError(f"{name} of kind {value['kind']!r} must have exactly the keys {sorted(wanted)}, and may have a note")
    note = value.get("note")
    if not (note is None or (isinstance(note, str) and len(note) <= NOTE_LIMIT)):
        raise TableError(f"{name}'s note must be text of at most {NOTE_LIMIT} characters, or null")


def _sources(value, shape, name):
    """A sourced file names a source for every value: the same keys as the values, each with text."""
    if value["kind"] != "sourced":
        return
    sources = value["sources"]
    if not isinstance(sources, dict) or set(sources) != set(shape):
        raise TableError(f"{name}: sources must cover exactly {sorted(shape)}")
    for group, keys in shape.items():
        if not isinstance(sources[group], dict) or set(sources[group]) != set(keys):
            raise TableError(f"{name}: the sources of {group!r} must cover exactly {sorted(keys)}")
        for key in keys:
            if not isinstance(sources[group][key], str) or not sources[group][key].strip():
                raise TableError(f"{name}: the source of {key} of {group!r} must be text")


def is_fixture(value):
    """Results worked out from a fixture file show that the mechanism works, and nothing else."""
    return value["kind"] == "fixture"


def check_prices(table):
    """Refuse a price table that is not: its kind, source, date, currency, the unit, and per model an input and
    an output price as decimal strings; and, if it is sourced, a source for each price."""
    _keys(table, ("source", "date", "currency", "unit", "models"), "the price table")
    for key in ("source", "currency"):
        if not isinstance(table[key], str) or not table[key].strip():
            raise TableError(f"the price table's {key} must be text")
    try:
        date.fromisoformat(table["date"])
    except (TypeError, ValueError):
        raise TableError("the price table's date must be a calendar date written YYYY-MM-DD") from None
    if table["unit"] != UNIT_PRICE:
        raise TableError(f"the price table's unit must be {UNIT_PRICE!r}")
    if not isinstance(table["models"], dict) or not table["models"]:
        raise TableError("the price table must price at least one model")
    for model, prices in table["models"].items():
        if not isinstance(prices, dict) or set(prices) != {"input", "output"}:
            raise TableError(f"the prices of {model!r} must be exactly input and output")
        for side in ("input", "output"):
            _number(prices[side], f"the {side} price of {model!r}")
    _sources(table, {model: ("input", "output") for model in table["models"]}, "the price table")


def check_times(parameters):
    """Refuse a modelled-time file that is not: its kind, the unit minutes, and the sets LOW, BASE and HIGH,
    each with the four parameters of the Metrics section as decimal strings; and, if it is sourced, a source
    for each parameter of each set."""
    _keys(parameters, ("unit", "sets"), "the modelled-time file")
    if parameters["unit"] != UNIT_TIME:
        raise TableError(f"the modelled-time unit must be {UNIT_TIME!r}")
    if not isinstance(parameters["sets"], dict) or set(parameters["sets"]) != set(SETS):
        raise TableError(f"the modelled-time file must hold exactly the sets {list(SETS)}")
    for name in SETS:
        values = parameters["sets"][name]
        if not isinstance(values, dict) or set(values) != set(PARAMETERS):
            raise TableError(f"the set {name} must hold exactly {list(PARAMETERS)}")
        for parameter in PARAMETERS:
            _number(values[parameter], f"{parameter} of the set {name}")
    _sources(parameters, dict.fromkeys(SETS, PARAMETERS), "the modelled-time file")


def amount(value, places=None):
    """An exact fraction as an amount. With `places` the decimal is rounded and says so; without, it is exact,
    which every sum of token counts times prices per million is."""
    value = Fraction(value)
    with localcontext() as context:
        context.prec = 60
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
        if places is None:
            if Fraction(decimal) != value:
                raise ValueError(f"{value} has no exact decimal form")
            decimal = decimal.normalize()
        else:
            decimal = decimal.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
    return {"numerator": value.numerator, "denominator": value.denominator, "not_applicable": False,
            "decimal": format(decimal, "f"), "rounded": places is not None}


def cost(attempts, table):
    """The known cost of these model calls. A call has a cost only if it reported both token counts and its
    reported model has a price; the others are counted, and make the cost a lower bound. Unknown is never 0."""
    return priced(tally(attempts, table), table)


def tally(attempts, table):
    """What the cost of these calls is made of, before pricing: the token counts summed by reported model, and the
    calls without token counts or without a price. Tallies of several groups add up with `combined`, so that each
    call is counted once however many groups it is in."""
    tokens, no_counts, no_price = {}, 0, 0
    for attempt in attempts:
        if attempt["input_tokens"] is None or attempt["output_tokens"] is None:
            no_counts += 1
        elif attempt["model_id"] not in table["models"]:
            no_price += 1
        else:
            pair = tokens.setdefault(attempt["model_id"], [0, 0])
            pair[0] += attempt["input_tokens"]
            pair[1] += attempt["output_tokens"]
    return {"tokens": tokens, "attempts": len(attempts), "no_counts": no_counts, "no_price": no_price}


def combined(tallies):
    """The tally of the calls of several tallies together."""
    total = {"tokens": {}, "attempts": 0, "no_counts": 0, "no_price": 0}
    for one in tallies:
        for model, (input_tokens, output_tokens) in one["tokens"].items():
            pair = total["tokens"].setdefault(model, [0, 0])
            pair[0] += input_tokens
            pair[1] += output_tokens
        for key in ("attempts", "no_counts", "no_price"):
            total[key] += one[key]
    return total


def priced(counted, table):
    """The cost block of a tally: token counts times the prices per million, in exact fractions."""
    no_counts, no_price = counted["no_counts"], counted["no_price"]
    known = Fraction(0)
    for model, (input_tokens, output_tokens) in sorted(counted["tokens"].items()):
        prices = table["models"][model]
        known += (input_tokens * _number(prices["input"], "input")
                  + output_tokens * _number(prices["output"], "output")) / 1_000_000
    block = {"known_cost": amount(known), "currency": table["currency"], "attempts": counted["attempts"],
             "attempts_without_token_counts": no_counts, "attempts_without_price": no_price,
             "at_least": bool(no_counts or no_price)}
    gaps = [f"{no_counts} attempts without token counts"] * bool(no_counts) + [f"{no_price} without a price"] * bool(no_price)
    block["statement"] = (f"at least {block['known_cost']['decimal']} {table['currency']}; {', '.join(gaps)}" if gaps
                          else f"{block['known_cost']['decimal']} {table['currency']}")
    return block


def per_item(block, items):
    """Cost per alert-framing item, rounded to six places for reading. None when there is no item."""
    if not items:
        return None
    return amount(Fraction(block["known_cost"]["numerator"], block["known_cost"]["denominator"]) / items, places=6)


def modelled_time(parameters, cells, alerts, escalate_alerts):
    """Modelled review time per alert, as the Metrics section defines it, for each parameter set and each
    review policy, averaged over `cells`: {name: {"ESCALATE": n, "CLOSE": n}} for one run and framing each.

    Manual total: alerts x manual clearing + L2 x the alerts whose correct action is escalate.
    Assisted total: alerts x proposal review + L2 x ESCALATE recommendations + second review x the closes the
    policy sends to a second reviewer (all of them under STRICT_FOUR_EYES, none under "none").
    """
    sets = {}
    for name in SETS:
        manual, proposal, l2, second = (_number(parameters["sets"][name][key], key) for key in PARAMETERS)
        manual_per_alert = (alerts * manual + l2 * escalate_alerts) / alerts
        block = {"parameters": dict(parameters["sets"][name]), "manual_per_alert": amount(manual_per_alert, places=6),
                 # the report flags a set under which escalating everything would beat manual clearing
                 "always_escalate_beats_manual": proposal + (1 - Fraction(escalate_alerts, alerts)) * l2 < manual}
        for policy in POLICIES:
            share = second if policy == "STRICT_FOUR_EYES" else 0
            each = {cell: (alerts * proposal + l2 * counts["ESCALATE"] + share * counts["CLOSE"]) / alerts
                    for cell, counts in cells.items()}
            average = sum(each.values(), Fraction(0)) / len(each)
            block[policy] = {"assisted_per_alert": amount(average, places=6),
                             "by_cell": {cell: amount(value, places=6) for cell, value in each.items()},
                             "lower_than_manual": average < manual_per_alert}
        sets[name] = block
    return {"unit": parameters["unit"], "alerts": alerts, "escalate_alerts": escalate_alerts, "sets": sets}
