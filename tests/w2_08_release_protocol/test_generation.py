"""W2-08: the generation of the fresh world and its record (FR-23, AC-19, DEC-W2-RELEASE-RULES; review round 1,
finding 3). Counters 0 to 9 are tried with the freeze commit's own generator; the first world it accepts is the
fresh world; every rejected try is recorded beside it. The check replays every try and compares every field of the
record with the replay.

The real generator has never been seen to reject a world, so the rejection path is tested with test-only freeze
commits whose generator rejects its first N tries (it counts them in a file of the tree it runs from): that is the
freeze commit's own generator, so the check runs its real path."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

import release_common as rc
from harness import release, release_check

PATCH = '''def generate(seed=None):
    _calls = Path(__file__).resolve().parent.parent.joinpath("w2-08-test-calls")
    _n = int(_calls.read_text()) if _calls.exists() else 0
    _calls.write_text(str(_n + 1))
    if _n < {reject}:
        raise BuildError(f"test rejection {{_n}}")
    if {crash}:
        raise RuntimeError("test fault")
'''


def variant(folder, reject=0, crash=False):
    """A clone whose freeze commit's generator rejects its first `reject` tries, or faults: (clone, freeze)."""
    clone, _ = rc.new_clone(folder)
    path = clone.joinpath("worldgen", "build.py")
    text = path.read_text(encoding="utf-8")
    assert text.count("def generate(seed=None):\n") == 1
    path.write_text(text.replace("def generate(seed=None):\n", PATCH.format(reject=reject, crash=crash)), encoding="utf-8")
    rc.git(clone, "commit", "-q", "-am", "Freeze with a test generator")
    return clone, rc.git(clone, "rev-parse", "HEAD").strip()


@pytest.fixture(scope="module")
def three(tmp_path_factory):
    """A freeze commit whose generator rejects three tries: (clone, freeze, record, world folder)."""
    folder = tmp_path_factory.mktemp("three")
    clone, freeze = variant(folder.joinpath("repo"), reject=3)
    record = release.make_fresh_world(freeze, folder.joinpath("world"), folder.joinpath("record.json"), repo=clone)
    return clone, freeze, record, folder.joinpath("world")


@pytest.fixture(scope="module")
def replayed(three, tmp_path_factory):
    """The check's replay of that freeze commit's generation, made once and compared with each tampered record: the
    replay is deterministic, so one serves them all. (record the replay makes, the world it accepts)."""
    clone, freeze, _, _ = three
    return release.generation(clone, freeze, tmp_path_factory.mktemp("replay"))


def test_the_fresh_world_is_the_first_accepted_try_with_the_freeze_commits_generator(cloned, fresh):
    _, freeze = cloned
    world, record = fresh
    manifest = json.loads(world.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    assert record == {"v": 1, "freeze_commit": freeze, "seed_function": release.SEED_FUNCTION,
                      "python": record["python"], "generator_version": manifest["generator_version"], "tries": [],
                      "accepted": {"counter": 0, "seed": release.fresh_seed(freeze, 0),
                                   "world_hash": manifest["world_hash"]}}
    assert manifest["seed"] == release.fresh_seed(freeze, 0) and record["python"].startswith("3.12.")


def test_rejected_tries_are_recorded_beside_the_accepted_one(three):
    clone, freeze, record, world = three
    assert [one["counter"] for one in record["tries"]] == [0, 1, 2]
    assert record["tries"][1] == {"counter": 1, "seed": release.fresh_seed(freeze, 1), "outcome": "rejected",
                                  "error_type": "BuildError",
                                  "error_sha256": hashlib.sha256(b"test rejection 1").hexdigest()}
    assert record["accepted"]["counter"] == 3 and record["accepted"]["seed"] == release.fresh_seed(freeze, 3)
    assert json.loads(world.joinpath("MANIFEST.json").read_text())["world_hash"] == record["accepted"]["world_hash"]


def test_the_replay_gives_the_record_again(three, replayed):
    _, _, record, _ = three
    again, world = replayed
    assert release.generation_problems(record, again) == [] and world is not None


def tamper(record, path, value):
    changed = copy.deepcopy(record)
    *parents, last = path
    target = changed
    for key in parents:
        target = target[key]
    if value is DELETE:
        del target[last]
    else:
        target[last] = value
    return changed


DELETE = object()
TAMPERED = [
    (("v",), 2), (("freeze_commit",), "0" * 40), (("seed_function",), "sha256 of the commit"),
    (("python",), "3.11.9"), (("python",), 3.12), (("generator_version",), "2"),
    (("tries", 0, "error_type"), "ValueError"), (("tries", 1, "error_sha256"), "0" * 64),
    (("tries", 2, "seed"), 7), (("tries", 2, "counter"), 5), (("tries", 0, "outcome"), "accepted"),
    (("tries", 1, "note"), "extra"), (("tries", 2), DELETE), (("accepted", "counter"), 4),
    (("accepted", "seed"), 8), (("accepted", "world_hash"), "0" * 64), (("accepted",), None),
    (("extra",), "field"), (("generator_version",), DELETE),
]


@pytest.mark.parametrize("path, value", TAMPERED)
def test_every_field_of_the_record_is_checked_against_the_replay(three, replayed, path, value):
    _, _, record, _ = three
    assert release.generation_problems(tamper(record, path, value), replayed[0]), (path, value)


def test_only_the_python_patch_level_may_differ(three, replayed):
    _, _, record, _ = three
    assert release.generation_problems({**record, "python": "3.12.99"}, replayed[0]) == []


@pytest.fixture(scope="module")
def ten(tmp_path_factory):
    """A freeze commit whose generator rejects every try: (clone, freeze, the record the fresh-world step wrote)."""
    folder = tmp_path_factory.mktemp("ten")
    clone, freeze = variant(folder.joinpath("repo"), reject=10)
    record = release.make_fresh_world(freeze, folder.joinpath("world"), folder.joinpath("record.json"), repo=clone)
    assert not folder.joinpath("world").exists()
    assert json.loads(folder.joinpath("record.json").read_text()) == record
    return clone, freeze, record


def test_ten_rejections_give_a_record_of_all_ten_and_no_world(ten):
    _, _, record = ten
    assert [one["counter"] for one in record["tries"]] == list(range(10)) and record["accepted"] is None


def judged(clone, freeze, record, before_commit=None):
    """The release check of the fresh world, with `record` committed as the generation record (None: no record)."""
    rc.publish(clone, freeze, {}, generation=record, before_commit=before_commit)
    with rc.at(clone):
        return release_check.check(clone.joinpath("release", "fresh"), "0" * 64,
                                   release={"freeze": freeze, "fresh": True})


def test_ten_rejections_with_a_matching_record_give_no_fresh_world(ten):
    clone, freeze, record = ten
    result = judged(clone, freeze, record)
    assert (result["result"], result["not_eligible_because"]) == (release.NO_FRESH_WORLD, [])
    assert result["release"]["generation"] == {"replayed": result["release"]["generation"]["replayed"],
                                               "recorded_matches": True}
    assert len(result["release"]["generation"]["replayed"]["tries"]) == 10


@pytest.mark.parametrize("case", ["missing", "shortened", "freeze problem"])
def test_ten_rejections_with_any_other_problem_are_not_eligible_with_the_replay_kept(ten, case):
    """Review round 2, finding N1: NO FRESH WORLD only with a matching record and an otherwise eligible freeze."""
    clone, freeze, record = ten
    if case == "missing":
        result, expected = judged(clone, freeze, None), f"{release.GENERATION} is missing or is not JSON"
    elif case == "shortened":
        result = judged(clone, freeze, {**record, "tries": record["tries"][:9]})
        expected = "the generation record's tries is not what the replay gives"
    else:
        result = judged(clone, freeze, record, before_commit=lambda c: Path(c, "README.md").write_text("changed\n"))
        expected = "README.md: changed after the freeze, and it is not a file the release may change"
    assert result["result"] == "NOT ELIGIBLE"
    assert any(expected in problem for problem in result["not_eligible_because"]), result["not_eligible_because"]
    replayed = result["release"]["generation"]["replayed"]
    assert replayed["accepted"] is None and [one["counter"] for one in replayed["tries"]] == list(range(10))
    assert result["release"]["generation"]["recorded_matches"] is (case == "freeze problem")


def test_a_fault_in_the_generator_is_not_a_rejection_and_writes_nothing(tmp_path):
    clone, freeze = variant(tmp_path.joinpath("repo"), crash=True)
    with pytest.raises(release.ReleaseRefused, match="not a rejection"):
        release.make_fresh_world(freeze, tmp_path.joinpath("world"), tmp_path.joinpath("record.json"), repo=clone)
    assert not tmp_path.joinpath("record.json").exists() and not tmp_path.joinpath("world").exists()


def test_the_fresh_world_is_made_only_from_a_clean_checkout_of_the_freeze_and_outside_it(cloned, tmp_path):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    with pytest.raises(release.ReleaseRefused, match="inside the repository"):
        release.make_fresh_world(freeze, clone.joinpath("world"), tmp_path.joinpath("r.json"), repo=clone)
    Path(clone, "untracked.txt").write_text("x")
    with pytest.raises(release.ReleaseRefused, match="clean checkout"):
        release.make_fresh_world(freeze, tmp_path.joinpath("w"), tmp_path.joinpath("r.json"), repo=clone)
    rc.reset(clone, freeze)
    with pytest.raises(release.ReleaseRefused, match="clean checkout"):
        release.make_fresh_world(f"{freeze}~1", tmp_path.joinpath("w"), tmp_path.joinpath("r.json"), repo=clone)
