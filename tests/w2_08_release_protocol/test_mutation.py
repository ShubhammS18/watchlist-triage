"""W2-08: the mutation proofs of the release protocol. Eight deliberate breakages, each applied to its own shared clone
of the repository with the uncommitted work laid over it, must each make its named guard test fail, while the same
test passes on an untouched clone; the real files are not changed. The proof machinery is T06's
(tests/t06_harness/mutations.py), with W2-01's kind of copy (tests/w2_01_acceptance/test_mutation.py)."""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].joinpath("t06_harness")))
import mutations  # noqa: E402

REPO = mutations.REPO
OVERLAID = ("harness", "worldgen", "triage_agent", "docs", "tests/w2_08_release_protocol")  # the uncommitted work
W = "tests/w2_08_release_protocol/"
ASSERTS = mutations.ASSERTS

# (what is broken, file, the text as it is, the text as broken, the test that must catch it, how it must fail)
BREAKAGES = (
    ("the answers of runs without scored items are not counted", "harness/release_check.py",
     'counted_runs = {**per_run, **{run: protocol.safety(lines, truth) for run, lines in state["log_lines"].items()}}',
     "counted_runs = per_run",
     W + "test_runs.py::test_an_unsafe_answer_in_an_aborted_run_fails_the_set", ASSERTS),
    ("only the last commit after the freeze is checked", "harness/release.py",
     "    for commit in commits:\n", "    for commit in commits[-1:]:\n",
     W + "test_freeze.py::test_a_change_made_and_undone_after_the_freeze_is_caught", ASSERTS),
    ("the generation record is trusted", "harness/release.py",
     '            state["problems"] += generation_problems(recorded, replayed)\n', "            pass\n",
     W + "test_fresh.py::test_a_generation_record_that_differs_from_the_replay_is_not_eligible", ASSERTS),
    ("a run folder the index does not list is let through", "harness/release.py",
     'problems += [f"{name} is a run folder that the index does not list" for name in folders if name not in indexed]',
     "problems += []",
     W + "test_logs.py::test_an_unlisted_run_folder_is_not_eligible_and_its_answers_count", ASSERTS),
    ("a finished run's checkpoint is not required", "harness/release.py",
     "        if finished:\n            problems.append(f\"{run_id}: its checkpoint is not committed",
     "        if False:\n            problems.append(f\"{run_id}: its checkpoint is not committed",
     W + "test_logs.py::test_a_completed_run_without_its_committed_checkpoint_is_not_eligible", ASSERTS),
    ("a completed run's log is not compared with its items", "harness/release.py",
     "mismatch = items_problem(run, parsed, loaded[run][1], loaded[run][0]) if parsed else None", "mismatch = None",
     W + "test_logs.py::test_a_logged_answer_that_is_not_the_items_rows_is_not_eligible", ASSERTS),
    ("an unfinished log is not checked as a chain", "harness/release.py",
     "        found = audit.verify(b\"\".join(line + b\"\\n\" for line in lines),",
     "        found = None and audit.verify(b\"\".join(line + b\"\\n\" for line in lines),",
     W + "test_logs.py::test_a_malformed_record_in_a_killed_runs_log_is_not_eligible", ASSERTS),
    ("the release rules apply without --release", "harness/release_check.py",
     "    if release is None:\n        return _check(out_dir, run_set, world, targets_path)\n",
     "    if release is None:\n        release = {\"freeze\": \"HEAD\"}\n",
     W + "test_frozen_unchanged.py::test_the_committed_run_sets_give_byte_identical_output", ASSERTS),
)


def make_copy(folder, mutation=None):
    """A shared clone of the repository in `folder`, the work not yet committed laid over it, and one breakage
    applied if one is given."""
    subprocess.run(["git", "clone", "-q", "--shared", str(REPO), str(folder)], check=True)
    for name in OVERLAID:
        shutil.copytree(REPO.joinpath(name), Path(folder, name), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    if mutation is not None:
        _, name, old, new, *_ = mutation
        path = Path(folder, name)
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, (name, old)
        path.write_text(text.replace(old, new), encoding="utf-8")
    return Path(folder)


def test_every_breakage_names_a_guard_test_that_exists_and_a_text_that_occurs_once():
    assert len(BREAKAGES) == 8
    for what, name, old, new, guard, expected in BREAKAGES:
        path, test = guard.split("::")
        assert f"def {test}(" in REPO.joinpath(path).read_text(encoding="utf-8"), guard
        assert REPO.joinpath(name).read_text(encoding="utf-8").count(old) == 1, (name, old)
        assert old != new and what and expected


def test_every_breakage_is_caught_and_the_real_files_are_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(mutations, "COPIED", OVERLAID)  # the untracked work; git status covers the tracked files
    monkeypatch.setattr(mutations, "make_copy", make_copy)
    status = lambda: subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout
    before = mutations.real_files_digest(), status()
    rows = mutations.prove(tmp_path, BREAKAGES)
    assert (mutations.real_files_digest(), status()) == before
    for row in rows:
        print(*row, sep="  |  ")
    assert [row[3:] for row in rows] == [("passed", "failed")] * len(BREAKAGES), rows
