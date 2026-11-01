"""The customer-value match of DEC-W2-06-CHOICES, for the W2-06 tests. Test-only.

The values are every customer-record field value of the frozen world (data/world/agent/customers.jsonl): name,
address, date of birth, ID number, nationality and the customer ID. Left out are the as-of date, source and version,
which are the same on every world record of every kind.

A text is normalised (NFC, case folded) and split into words on anything that is not a letter or a digit. It matches
when it holds:
1. the whole of a value, as a run of consecutive words;
2. all the non-title words of a customer's name, in any order (the framings reorder names);
3. a word of four or more letters from a customer's name or address that is not a title or a common address word.
Titles never match alone. No value is removed and the rule is never loosened for one value.
"""
import json
import re
import unicodedata

from conftest import REPO, WORLD
from worldgen.build import SUFFIXES

FIELDS = ("name", "address", "date_of_birth", "id_number", "nationality", "id")
LEFT_OUT = ("as_of_date", "source", "version")
TITLES = frozenset(line.strip().casefold() for line in REPO.joinpath("worldgen", "names", "titles.txt").read_text(
    encoding="utf-8").split("\n") if line.strip())
ADDRESS_WORDS = frozenset(word.casefold() for word in SUFFIXES)
_WORD = re.compile(r"[^\W_]+")


def words(text):
    return tuple(_WORD.findall(unicodedata.normalize("NFC", text).casefold()))


def customers():
    return [json.loads(line) for line in WORLD.joinpath("agent", "customers.jsonl").read_text(encoding="utf-8").split("\n")
            if line]


class Matcher:
    def __init__(self, records):
        self.values = {words(record[field]): record[field] for record in records for field in FIELDS if field in record}
        self.longest = max(map(len, self.values))
        self.names = {frozenset(word for word in words(record["name"]) if word not in TITLES): record["name"]
                      for record in records}
        self.single = {word: record[field] for record in records for field in ("name", "address") if field in record
                       for word in words(record[field])
                       if len(word) >= 4 and word.isalpha() and word not in TITLES and word not in ADDRESS_WORDS}
        self.by_word = {}  # each name's word set, under each of its words, so a text is compared only with names it shares a word with
        for name_words in self.names:
            for word in name_words:
                self.by_word.setdefault(word, []).append(name_words)

    def match(self, text):
        """The customer value `text` holds, by the first rule that finds one, or None."""
        found = words(text)
        for size in range(1, self.longest + 1):
            for start in range(len(found) - size + 1):
                if found[start:start + size] in self.values:
                    return self.values[found[start:start + size]]
        held = set(found)
        for word in held & self.single.keys():
            return self.single[word]
        for word in held & self.by_word.keys():
            for name_words in self.by_word[word]:
                if name_words <= held:
                    return self.names[name_words]
        return None


MATCHER = Matcher(customers())


def leaves(value, path=""):
    """(path, text) for every object key and every text or number in `value`; booleans and null say nothing."""
    if isinstance(value, dict):
        for key, inner in value.items():
            yield f"{path}{{key}}", key
            yield from leaves(inner, f"{path}.{key}")
    elif isinstance(value, list):
        for inner in value:
            yield from leaves(inner, f"{path}[]")
    elif isinstance(value, str):
        yield path, value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield path, str(value)


def hits(value, free=()):
    """[(path, customer value)] for every structured leaf of `value` that holds a customer value. `free` names the
    paths of the disclosed free-text fields, which are left out."""
    return [(path, found) for path, text in leaves(value) if path not in free
            for found in [MATCHER.match(text)] if found is not None]


PLANTED_NAME = customers()[0]["name"]  # a customer's name, as the error-record tests plant it
