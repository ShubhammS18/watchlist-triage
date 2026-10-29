"""W2-01: the mutation proofs of the release check. Six deliberate breakages, each applied to its own temporary copy,
must each make its named guard test fail, while the same test passes on an untouched copy; the real files are not
changed. The proof machinery is T06's (tests/t06_harness/mutations.py). Only the copy differs: these tests need git
(run commits, the committed price table, the targets file at HEAD), so each copy is a shared clone of the repository
with the current harness/, worldgen/, triage_agent/ and tests/w2_01_acceptance/ laid over it. The clone only reads the
real repository.

They run in the gate: about 22 s on this machine, with the gate under 60 s."""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].joinpath("t06_harness")))
import mutations  # noqa: E402

REPO = mutations.REPO
OVERLAID = ("harness", "worldgen", "triage_agent", "tests/w2_01_acceptance")  # laid over the clone: work not yet committed
W = "tests/w2_01_acceptance/"
ASSERTS = mutations.ASSERTS

# (what is broken, file, the text as it is, the text as broken, the test that must catch it, how it must fail)
BREAKAGES = (
    ("equality no longer meets a target", "harness/release_check.py",
     'within = size <= bound if target["direction"] == "at_most" else size >= bound',
     'within = size < bound if target["direction"] == "at_most" else size > bound',
     W + "test_targets.py::test_a_rate_is_judged_as_an_exact_fraction_with_equality_passing", ASSERTS),
    ("the targets hash is not checked", "harness/release_check.py",
     "    if records.sha256(raw) != TARGETS_SHA256:\n", "    if False:\n",
     W + "test_eligibility.py::test_a_changed_targets_file", ASSERTS),
    ("invalid runs are pooled as valid", "harness/release_check.py",
     '    valid = sorted(run for run, (manifest, _) in loaded.items()\n'
     '                   if not manifest["git"]["dirty"] and not manifest["infra_invalid"]["marked"])',
     "    valid = sorted(loaded)",
     W + "test_oracle.py::test_the_oracle_run_set_passes", ASSERTS),
    ("the safety counts are taken on valid runs only", "harness/release_check.py",
     "counts = {run: read(tree) for run, tree in per_run.items()}", "counts = {run: read(per_run[run]) for run in valid}",
     W + "test_oracle.py::test_one_change_fails_exactly_one_named_target", ASSERTS),
    ("a failure is not counted as ESCALATE in the verdict divergence", "harness/score.py",
     "(verdicts, verdict(alert) != verdict(twin)),",
     '(verdicts, alert["result"]["recommendation"] != twin["result"]["recommendation"]),',
     W + "test_oracle.py::test_one_change_fails_exactly_one_named_target", ASSERTS),
    ("a call whose cost cannot be bounded is let through", "harness/release_check.py",
     "    if unbounded:\n", "    if False:\n",
     W + "test_eligibility.py::test_a_call_whose_cost_cannot_be_bounded", ASSERTS),
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
    assert len(BREAKAGES) == 6
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
