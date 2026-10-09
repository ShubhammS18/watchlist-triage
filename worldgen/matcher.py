"""The simple name matcher (FR-4). Names only.

Two names match when they have the same number of parts and the parts pair one-to-one,
in any order, each pair within one edit. Watchlist aliases are compared too.
Improving detection is out of scope: variants beyond this are deliberately not caught.
"""
from itertools import permutations

from . import load_names
from .textutil import name_parts, within_one_edit


def load_titles():
    return frozenset(t.lower() for t in load_names("titles.txt"))


def parts_match(a, b):
    """a and b are tuples of normalised parts (see textutil.name_parts)."""
    if not a or len(a) != len(b):
        return False
    return any(all(within_one_edit(x, y) for x, y in zip(a, order)) for order in permutations(b))


def names_match(name_a, name_b, titles=frozenset()):
    return parts_match(name_parts(name_a, titles), name_parts(name_b, titles))


def entry_matches(customer_name, entry, titles=frozenset()):
    """entry is a watchlist record: {"name": ..., "aliases": [...]}. Primary name and aliases count."""
    return any(names_match(customer_name, name, titles) for name in [entry["name"], *entry.get("aliases", [])])


def match_all(customers, watchlist, titles=frozenset()):
    """Every (customer id, watchlist id) pair that matches, sorted."""
    forms = [(e["id"], [name_parts(n, titles) for n in [e["name"], *e.get("aliases", [])]]) for e in watchlist]
    pairs = []
    for customer in customers:
        parts = name_parts(customer["name"], titles)
        pairs.extend((customer["id"], wid) for wid, names in forms if any(parts_match(parts, n) for n in names))
    return sorted(pairs)
