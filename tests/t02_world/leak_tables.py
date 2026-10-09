"""Leak tables: how free-choice features are distributed across labels in the committed world.

Run as a script to print the tables:  .venv/bin/python tests/t02_world/leak_tables.py
The tests in test_leaks.py import the same functions.
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from worldgen.matcher import load_titles, parts_match  # noqa: E402
from worldgen.snippets import INJECTED_TEXTS  # noqa: E402
from worldgen.textutil import name_parts  # noqa: E402

LABELS = ("TRUE_MATCH", "AMBIGUOUS_BY_DESIGN", "CLEAR_FALSE_POSITIVE")
ADDRESS = ("both present, equal", "both present, different", "one side missing", "both missing")
NAME_FORMS = ("exact", "via alias", "word order", "spelling edit", "diacritics or title")
NATIONALITY = ("agree", "conflict", "unavailable")
GROUP_SIZES = ("1 (alone)", "2", "3", "4 or more")
SNIPPET_COUNTS = ("0", "1", "2 or more")
DIRECTIONS = ("close-directed", "other-directed", "no injected text")
KIND_OF = {text: kind for kind, text in INJECTED_TEXTS}
TITLES = load_titles()


def read(world_dir, relative):
    text = Path(world_dir).joinpath(*relative.split("/")).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]


def address_relation(customer, entry):
    c, w = customer.get("address"), entry.get("address")
    if c is None and w is None:
        return ADDRESS[3]
    if c is None or w is None:
        return ADDRESS[2]
    return ADDRESS[0] if c == w else ADDRESS[1]


def name_form(customer, entry):
    """One form per alert. When several apply the first of alias, spelling, order, diacritics/title wins."""
    c, w = name_parts(customer["name"], TITLES), name_parts(entry["name"], TITLES)
    if not parts_match(c, w):
        return NAME_FORMS[1]
    if sorted(c) != sorted(w):
        return NAME_FORMS[3]
    if c != w:
        return NAME_FORMS[2]
    return NAME_FORMS[0] if customer["name"] == entry["name"] else NAME_FORMS[4]


def nationality_relation(customer, entry):
    c, w = customer.get("nationality"), entry.get("nationality")
    if c is None or w is None:
        return NATIONALITY[2]
    return NATIONALITY[0] if c == w else NATIONALITY[1]


def tables(world_dir):
    """{feature: {label: Counter}} plus per-label evidence stats, computed from the files on disk."""
    customers = {r["id"]: r for r in read(world_dir, "agent/customers.jsonl")}
    entries = {r["id"]: r for r in read(world_dir, "agent/watchlist.jsonl")}
    evidence = {r["id"]: r for r in read(world_dir, "agent/evidence.jsonl")}
    labels = {r["alert_id"]: r for r in read(world_dir, "hidden/labels.jsonl")}
    tags = {r["evidence_item_id"]: r["tag"] for r in read(world_dir, "hidden/snippet_tags.jsonl")}
    alerts = read(world_dir, "agent/alerts.jsonl")
    shared = Counter(a["watchlist_entry_id"] for a in alerts)
    out = {"address": {}, "name_form": {}, "nationality": {}, "name_form_by_family": {}, "stats": {},
           "group_size": {}, "snippet_count": {}, "injection_direction": {}, "injection_positions": []}
    items, with_snippet, count = Counter(), Counter(), Counter()
    for alert in alerts:
        row = labels[alert["id"]]
        size = shared[alert["watchlist_entry_id"]]
        out["group_size"].setdefault(row["label"], Counter())[GROUP_SIZES[min(size, 4) - 1]] += 1
        snippets = [i for i in alert["evidence_item_ids"] if evidence[i]["kind"] == "snippet"]
        out["snippet_count"].setdefault(row["label"], Counter())[SNIPPET_COUNTS[min(len(snippets), 2)]] += 1
        injected = [i for i in snippets if tags.get(i) == "injection"]
        direction = DIRECTIONS[2]
        if injected:
            direction = DIRECTIONS[0] if KIND_OF[evidence[injected[0]]["value"]] == "close" else DIRECTIONS[1]
            index = alert["evidence_item_ids"].index(injected[0])
            out["injection_positions"].append((alert["id"], row["label"], index, len(alert["evidence_item_ids"])))
        out["injection_direction"].setdefault(row["label"], Counter())[direction] += 1
        label, family = row["label"], row["primary_family"] or "plain"
        customer, entry = customers[alert["customer_id"]], entries[alert["watchlist_entry_id"]]
        out["address"].setdefault(label, Counter())[address_relation(customer, entry)] += 1
        out["name_form"].setdefault(label, Counter())[name_form(customer, entry)] += 1
        out["nationality"].setdefault(label, Counter())[nationality_relation(customer, entry)] += 1
        out["name_form_by_family"].setdefault((label, family), Counter())[name_form(customer, entry)] += 1
        count[label] += 1
        items[label] += len(alert["evidence_item_ids"])
        with_snippet[label] += any(evidence[i]["kind"] == "snippet" for i in alert["evidence_item_ids"])
    for label in LABELS:
        out["stats"][label] = {"alerts": count[label], "evidence_items": items[label], "with_snippet": with_snippet[label]}
    return out


def percent(counter, category):
    """Share of one category in tenths of a percentage point (an integer, so no rounding surprises)."""
    return counter[category] * 1000 // sum(counter.values())


def largest_gap(table, categories):
    """Largest difference between any two labels, over all categories, in tenths of a percentage point."""
    return max(max(percent(table[l], c) for l in LABELS) - min(percent(table[l], c) for l in LABELS) for c in categories)


def show(title, table, categories, keys=LABELS):
    print(f"\n{title}")
    print(f"{'':<34}" + "".join(f"{str(k)[:24]:>26}" for k in keys))
    for category in categories:
        cells = []
        for key in keys:
            counter = table.get(key, Counter())
            total = sum(counter.values()) or 1
            share = counter[category] * 1000 // total
            cells.append(f"{counter[category]:>4} of {total:<3} ({share // 10:>2}.{share % 10}%)")
        print(f"{category:<34}" + "".join(f"{c:>26}" for c in cells))


def main(world_dir=None):
    world_dir = world_dir or REPO.joinpath("data", "world")
    t = tables(world_dir)
    show("ADDRESS RELATION by label", t["address"], ADDRESS)
    gap = largest_gap(t["address"], ADDRESS)
    print(f"largest gap between two labels: {gap // 10}.{gap % 10} percentage points")
    show("NAME FORM by label", t["name_form"], NAME_FORMS)
    gap = largest_gap(t["name_form"], NAME_FORMS)
    print(f"largest gap between two labels: {gap // 10}.{gap % 10} percentage points")
    show("NATIONALITY RELATION by label (the rubric uses nationality, so this may differ)", t["nationality"], NATIONALITY)
    show("WATCHLIST GROUP SIZE by label (how many alerts share the alert's watchlist entry)", t["group_size"], GROUP_SIZES)
    gap = largest_gap(t["group_size"], GROUP_SIZES)
    print(f"largest gap between two labels: {gap // 10}.{gap % 10} percentage points")
    show("SNIPPETS PER ALERT by label", t["snippet_count"], SNIPPET_COUNTS)
    gap = largest_gap(t["snippet_count"], SNIPPET_COUNTS)
    print(f"largest gap between two labels: {gap // 10}.{gap % 10} percentage points")
    show("INJECTED TEXT DIRECTION by label", t["injection_direction"], DIRECTIONS)
    print("\nINJECTED ITEM POSITION (index among the alert's evidence items, counted from 0)")
    for alert_id, label, index, length in sorted(t["injection_positions"]):
        print(f"  {alert_id}  {label:<22} position {index:>2} of {length:>2} items   ({length - 1 - index} from the end)")
    positions = [index for _, _, index, _ in t["injection_positions"]]
    last = sum(1 for _, _, index, length in t["injection_positions"] if index == length - 1)
    print(f"  distinct positions: {len(set(positions))}; first: {positions.count(0)}; last: {last}; of {len(positions)}")
    print("\nEVIDENCE by label")
    for label in LABELS:
        s = t["stats"][label]
        mean = s["evidence_items"] * 10 // s["alerts"]
        share = s["with_snippet"] * 1000 // s["alerts"]
        print(f"  {label:<22} mean evidence items {mean // 10}.{mean % 10}   with at least one snippet "
              f"{s['with_snippet']} of {s['alerts']} ({share // 10}.{share % 10}%)")
    print("\nNAME FORM by label and primary family (counts)")
    for key in sorted(t["name_form_by_family"]):
        counter = t["name_form_by_family"][key]
        print(f"  {key[0]:<22} {key[1]:<24} " + "  ".join(f"{f}={counter[f]}" for f in NAME_FORMS if counter[f]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
