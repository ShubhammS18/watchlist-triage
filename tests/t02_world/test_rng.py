"""Tests for worldgen.rng: the SHA-256 counter stream. They need no data files."""
import hashlib

import pytest

from worldgen.rng import Stream

SEED = 20260930

# Known answers, computed once from the implementation and cross-checked with hashlib below.
FIRST_WORDS_NAMES = [
    17673946207456259875,
    9519396433960150541,
    13367848335334308038,
    8866765921282778063,
    17033758343866399925,
    9233259091372434015,
]


def test_known_answer_words():
    s = Stream(SEED, "names")
    assert [s.next_u64() for _ in FIRST_WORDS_NAMES] == FIRST_WORDS_NAMES


def test_words_match_a_direct_sha256_calculation():
    """Block n of stream NAME is sha256("seed|NAME|n"), read as four big-endian 64-bit integers."""
    blocks = [hashlib.sha256(f"{SEED}|names|{n}".encode()).digest() for n in (0, 1)]
    expected = [int.from_bytes(b[k:k + 8], "big") for b in blocks for k in (0, 8, 16, 24)]
    s = Stream(SEED, "names")
    assert [s.next_u64() for _ in range(8)] == expected


def test_known_answer_ranges_and_shuffle():
    assert [Stream(SEED, "dob").below(100)] == [5]
    s = Stream(SEED, "dob")
    assert [s.below(100) for _ in range(10)] == [5, 62, 36, 66, 92, 52, 30, 60, 44, 84]
    s = Stream(SEED, "dob")
    assert [s.randint(5, 9) for _ in range(10)] == [5, 7, 6, 6, 7, 7, 5, 5, 9, 9]
    assert Stream(SEED, "shuffle").shuffle(list(range(10))) == [4, 0, 7, 6, 8, 9, 2, 3, 1, 5]
    s = Stream(SEED, "pick")
    assert [s.choice(list("abcde")) for _ in range(8)] == list("adcaeabd")


def test_same_seed_and_stream_repeat():
    a, b = Stream(SEED, "ids"), Stream(SEED, "ids")
    assert [a.next_u64() for _ in range(50)] == [b.next_u64() for _ in range(50)]


def test_different_streams_and_seeds_differ():
    assert Stream(SEED, "ids").next_u64() == 727055543210225717
    assert Stream(SEED, "ids").next_u64() != Stream(SEED, "names").next_u64()
    assert Stream(SEED + 1, "names").next_u64() == 466187231654486605
    assert Stream(SEED + 1, "names").next_u64() != Stream(SEED, "names").next_u64()


@pytest.mark.parametrize("n", [1, 2, 3, 7, 100, 1000, 2**32 + 1, 2**63 + 1])
def test_below_stays_in_range(n):
    s = Stream(SEED, "range")
    assert all(0 <= s.below(n) < n for _ in range(200))


def test_below_one_is_always_zero():
    s = Stream(SEED, "range")
    assert {s.below(1) for _ in range(50)} == {0}


def test_below_is_roughly_even():
    s = Stream(SEED, "even")
    counts = [0] * 6
    for _ in range(6000):
        counts[s.below(6)] += 1
    assert all(850 <= c <= 1150 for c in counts), counts


@pytest.mark.parametrize("bad", [0, -1])
def test_below_rejects_non_positive(bad):
    with pytest.raises(ValueError):
        Stream(SEED, "x").below(bad)


def test_randint_includes_both_ends_and_rejects_reversed_bounds():
    s = Stream(SEED, "ends")
    seen = {s.randint(3, 5) for _ in range(200)}
    assert seen == {3, 4, 5}
    assert Stream(SEED, "ends").randint(7, 7) == 7
    with pytest.raises(ValueError):
        Stream(SEED, "ends").randint(5, 3)


def test_rejection_sampling_discards_words_in_the_biased_tail():
    """For n=3 the usable limit is 2**64 - 1, so the word 2**64 - 1 must be rejected."""

    class Scripted(Stream):
        def __init__(self, words):
            super().__init__(0, "scripted")
            self._script = iter(words)

        def next_u64(self):
            return next(self._script)

    biased = 2**64 - 1                      # would give 0 if it were wrongly accepted
    s = Scripted([biased, 5])
    assert s.below(3) == 5 % 3
    assert Scripted([2**64 - 2]).below(3) == (2**64 - 2) % 3   # the last usable word is accepted


def test_shuffle_is_a_permutation_in_place_and_repeatable():
    items = list(range(50))
    result = Stream(SEED, "perm").shuffle(items)
    assert result is items
    assert sorted(items) == list(range(50))
    assert items != list(range(50))
    again = Stream(SEED, "perm").shuffle(list(range(50)))
    assert again == items


def test_shuffle_of_short_lists():
    assert Stream(SEED, "s").shuffle([]) == []
    assert Stream(SEED, "s").shuffle(["only"]) == ["only"]


def test_choice():
    s = Stream(SEED, "c")
    assert {s.choice(("x", "y", "z")) for _ in range(100)} == {"x", "y", "z"}
    with pytest.raises(ValueError):
        s.choice([])
