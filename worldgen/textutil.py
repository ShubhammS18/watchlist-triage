"""Edit distance and name normalisation. Latin script only (a stated limit of the world)."""
import re
import unicodedata


def edit_distance(a, b):
    """Levenshtein distance: fewest single-letter insertions, deletions or substitutions."""
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            row.append(min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = row
    return previous[-1]


def within_one_edit(a, b):
    """True when edit_distance(a, b) <= 1. Linear time, so the matcher stays fast."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1:] == b[i + 1:]
    return a[i:] == b[i + 1:]


def normalise(text):
    """Unicode NFC, lower case."""
    return unicodedata.normalize("NFC", text).lower()


def strip_diacritics(text):
    """Remove combining marks (accents). Letters with no decomposition, such as 'ø', stay."""
    decomposed = unicodedata.normalize("NFD", text)
    kept = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", kept)


def name_parts(name, titles=frozenset()):
    """A name as a tuple of normalised parts: split on spaces and hyphens, titles dropped.

    `titles` holds lower-case titles without accents or dots.
    """
    text = strip_diacritics(normalise(name))
    parts = (p.strip(".,") for p in re.split(r"[ \-]+", text))
    return tuple(p for p in parts if p and p not in titles)
