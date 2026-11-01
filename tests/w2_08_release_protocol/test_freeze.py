"""W2-08: the freeze check (DEC-W2-08-CHOICES; review round 1, finding 5). After the freeze, up to the commit that
publishes the release (HEAD), only the release's own files may change, each in the way allowed. Every commit is
checked, so a change made and undone in between is caught, and the history must be linear. The tree must be clean,
and every checkpoint added after the freeze must belong to a release run."""
from pathlib import Path

import pytest

import release_common as rc
from harness import release


def commit(clone, changes, message="Change (test)"):
    """One commit: {path: text to write, or None to delete}."""
    for path, text in changes.items():
        target = Path(clone, path)
        if text is None:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
    rc.git(clone, "add", "-A")
    rc.git(clone, "commit", "-q", "--allow-empty", "-m", message)


def problems(cloned):
    clone, freeze = cloned
    return release.freeze_problems(clone, freeze)


RUN = "20261101T090000123456Z-d427544d"
POINT = f"audit/checkpoints/{RUN}.json"


def test_the_release_files_may_change_in_their_allowed_ways(cloned, frozen_pool, tmp_path):
    clone, freeze = cloned
    out, _ = rc.assemble(frozen_pool, ["valid1", "valid2", "valid3"], tmp_path)
    rc.publish(clone, freeze, {"frozen": out}, generation={"v": 1})
    commit(clone, {"release/check-frozen.json": "{}\n", "docs/release-log.md": "# Release log\n"})
    commit(clone, {"release/check-frozen.json": "{\"x\": 1}\n", "docs/release-log.md": "# Release log\n\nMore.\n",
                   "release/frozen/SHA256SUMS": Path(clone, "release/frozen/SHA256SUMS").read_text() + "\n"})
    assert problems(cloned) == []


@pytest.mark.parametrize("path", ["harness/release_check.py", "triage_agent/record.py", "config/prices.json",
                                  "targets/release-targets.json", "data/world/MANIFEST.json", "README.md",
                                  "tools/new_tool.py", "release/frozen/run.py", "release/notes.md",
                                  f"release/frozen/{RUN}/extra.py", "audit/checkpoints/notes.md"])
def test_any_other_change_after_the_freeze_is_caught(cloned, path):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    old = Path(clone, path).read_text(encoding="utf-8") if Path(clone, path).exists() else ""
    commit(clone, {path: old + "\n# changed\n"})
    assert any(path in problem for problem in problems(cloned)), problems(cloned)


def test_a_change_made_and_undone_after_the_freeze_is_caught(cloned):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    path = "triage_agent/record.py"
    old = Path(clone, path).read_text(encoding="utf-8")
    commit(clone, {path: old + "\n# changed for a run\n"})
    commit(clone, {path: old})
    assert rc.git(clone, "diff", "--name-only", freeze, "HEAD") == ""  # the end points alone show nothing
    found = problems(cloned)
    assert len(found) == 2 and all(path in problem for problem in found), found


def test_a_checkpoint_or_the_generation_record_may_only_be_added(cloned):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    Path(clone, "release", "frozen", RUN).mkdir(parents=True)  # a run folder, so the checkpoint is not an orphan
    commit(clone, {POINT: "{}\n", f"release/frozen/{RUN}/audit.jsonl": "", release.GENERATION: "{}\n"})
    commit(clone, {POINT: "{\"changed\": true}\n", release.GENERATION: "{\"changed\": true}\n"})
    commit(clone, {POINT: None})
    found = problems(cloned)
    assert any(POINT in p and "changed after the freeze" in p for p in found), found
    assert any(release.GENERATION in p for p in found), found
    assert any(POINT in p and "deleted" in p for p in found), found


def test_a_run_file_may_not_be_changed_once_added(cloned):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    commit(clone, {f"release/frozen/{RUN}/items.jsonl": "{}\n"})
    commit(clone, {f"release/frozen/{RUN}/items.jsonl": "{\"x\": 1}\n"})
    assert any("items.jsonl" in p for p in problems(cloned))


def test_a_checkpoint_without_its_release_run_is_caught(cloned):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    commit(clone, {POINT: "{}\n"})
    assert any("no practice run" in p for p in problems(cloned))


def test_the_tree_must_be_clean(cloned):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    Path(clone, "untracked.txt").write_text("x")
    assert any("not clean" in p for p in problems(cloned))
    rc.reset(clone, freeze)
    Path(clone, "README.md").write_text("changed, not committed\n")
    assert any("not clean" in p for p in problems(cloned))


def test_the_freeze_must_be_an_ancestor_of_head(cloned):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    rc.git(clone, "checkout", "-q", "--detach", f"{freeze}~1")
    commit(clone, {"docs/release-log.md": "# Release log\n"})
    assert problems(cloned) == [f"the freeze commit {freeze} is not an ancestor of HEAD"]


def test_a_merge_after_the_freeze_is_caught(cloned):
    clone, freeze = cloned
    rc.reset(clone, freeze)
    rc.git(clone, "checkout", "-q", "-B", "side", freeze)
    commit(clone, {"docs/release-log.md": "# Release log\n"})
    rc.git(clone, "checkout", "-q", "-B", "main-test", freeze)
    commit(clone, {"release/check-frozen.json": "{}\n"})
    rc.git(clone, "merge", "-q", "--no-ff", "-m", "Merge (test)", "side")
    assert any("is a merge" in p for p in problems(cloned))


def test_the_release_mode_reports_the_freeze_problems_but_still_counts_safety(cloned, frozen_pool, judge, tmp_path):
    clone, freeze = cloned
    out, _ = rc.assemble(frozen_pool, ["valid1", "valid2", "valid3", "aborted_unsafe"], tmp_path)
    rc.publish(clone, freeze, {"frozen": out}, before_commit=lambda c: Path(c, "README.md").write_text("changed\n"))
    result = judge("frozen")
    assert result["result"] == "NOT ELIGIBLE"
    assert any("README.md" in p for p in result["not_eligible_because"])
    assert result["targets"]["true_matches_closed"]["result"] == "fail"
