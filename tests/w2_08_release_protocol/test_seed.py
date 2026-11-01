"""W2-08: the documented seed function (FR-23, AC-19): its test vectors, as docs/w2-08-release-protocol.md gives
them, and its refusals."""
import pytest

from harness.release import fresh_seed

VECTORS = [("0" * 40, 0, 982426940076343), ("0" * 40, 9, 878779841415296),
           ("4bf3b82f8da96e2f4efbb81c7d65250d96f519b8", 0, 754401112843469),
           ("4bf3b82f8da96e2f4efbb81c7d65250d96f519b8", 1, 2342836009960206)]


@pytest.mark.parametrize("commit, counter, seed", VECTORS)
def test_the_documented_vectors(commit, counter, seed):
    assert fresh_seed(commit, counter) == seed


def test_the_vectors_are_the_ones_the_design_doc_gives():
    text = fresh_seed.__globals__["records"].REPO.joinpath("docs", "w2-08-release-protocol.md").read_text(encoding="utf-8")
    for commit, counter, seed in VECTORS:
        assert f"| `{commit}` | {counter} | {seed} |" in text


def test_every_seed_is_an_exact_json_integer_and_the_counters_differ():
    seeds = [fresh_seed("4bf3b82f8da96e2f4efbb81c7d65250d96f519b8", counter) for counter in range(10)]
    assert all(0 <= seed < 2 ** 52 for seed in seeds) and len(set(seeds)) == 10


@pytest.mark.parametrize("commit", ["4bf3b82", "4BF3B82F8DA96E2F4EFBB81C7D65250D96F519B8", "release-1-freeze",
                                    "4bf3b82f8da96e2f4efbb81c7d65250d96f519b8\n", None, 0])
def test_only_a_full_lowercase_commit_hash_is_taken(commit):
    with pytest.raises(ValueError, match="full 40-character"):
        fresh_seed(commit, 0)


@pytest.mark.parametrize("counter", [10, -1, True, "0", 1.0, None])
def test_only_a_counter_from_0_to_9_is_taken(counter):
    with pytest.raises(ValueError, match="from 0 to 9"):
        fresh_seed("0" * 40, counter)
