"""W2-10: the quick checks that stay in the gate while the dry run runs by hand (DEC-W2-10-ROUND3). They build no
made-up release and call no model: the dry run's switch, the items-file rule of G12, the documented copy_as_is with
the 'Left out' rule of G6, and that every dry-run case names a rule of the gate."""
import json
import os
import re
import subprocess
import sys
from fractions import Fraction

import made_up
import release_common as rc
import release_gate as gate
import test_dry_run

ITEM = lambda kind: json.dumps({"result": {"failure_kind": kind}}).encode()


def test_the_dry_run_is_skipped_without_w2_10_dry_run_1():
    """In a fresh test process without the variable, every dry-run test is skipped with its reason. That it runs with
    W2_10_DRY_RUN=1 is shown by the by-hand run committed as evidence before the freeze."""
    env = {key: value for key, value in os.environ.items() if key != "W2_10_DRY_RUN"}
    done = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider",
                           "tests/w2_10_release_runs/test_dry_run.py"], cwd=rc.REPO, env=env, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0 and re.search(r"\b\d+ skipped\b", done.stdout), done.stdout
    assert " passed" not in done.stdout, done.stdout
    assert "the dry run runs only with W2_10_DRY_RUN=1, by hand just before the freeze" in done.stdout


def test_the_items_rule_counts_every_whole_record():
    refusal, plain = ITEM("model_refusal"), ITEM(None)
    # review round 3, R3-1: a whole last record without its newline counts in an unfinished run
    assert gate._share(refusal, False) == (Fraction(1), None)
    assert gate._share(plain + b"\n" + refusal, False) == (Fraction(1, 2), None)
    # cut off by a crash: not counted, and no problem
    assert gate._share(plain + b"\n" + refusal[:20], False) == (Fraction(0), None)
    assert gate._share(b"", False) == (Fraction(0), None)
    # a completed run's file ends with a newline; any whole line that is not an item record is a problem
    assert gate._share(refusal, True)[1]
    assert gate._share(plain + b"\n" + refusal + b"\n", True) == (Fraction(1, 2), None)
    assert "line 1" in gate._share(b"{not json\n" + plain + b"\n", False)[1]


def test_copy_as_is_leaves_out_what_git_may_not_hold_and_the_log_must_name_it(tmp_path):
    """The documented copy_as_is, run as written, on a run-output folder whose index a crash cut off: the run folder
    and sets/ are copied and verified, the index and its .tmp are left out, and it prints one 'Left out' line for
    each. G6 needs the index's line in the log (review round 3, R3-2)."""
    out, clone = tmp_path.joinpath("out"), tmp_path.joinpath("clone")
    run = out.joinpath("20261117T000000000000Z-deadbeef")
    run.mkdir(parents=True)
    run.joinpath("audit.jsonl").write_bytes(b"{}\n")
    out.joinpath("sets").mkdir()
    out.joinpath("sets", "a.json").write_bytes(b"{}\n")
    out.joinpath("index.json").write_bytes(b'{"runs": [')
    out.joinpath("index.json.tmp").write_bytes(b"{")
    printed = made_up.copy_as_is(clone, out, "frozen")
    folder = clone.joinpath("release", "frozen")
    assert sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()) == \
        ["20261117T000000000000Z-deadbeef/audit.jsonl", "SHA256SUMS", "sets/a.json"]
    lines = [line for line in printed.splitlines() if line.startswith("- Left out:")]
    assert lines == [f"- Left out: `{name}`, SHA-256 `{rc.records.sha256(out.joinpath(name).read_bytes())}`"
                     for name in ("index.json", "index.json.tmp")]
    log = "## Frozen world\n| # |\n|---|\n\n{}\n\n## Fresh world\n"
    assert gate.left_out(log.format("\n".join(lines)), "frozen", folder) == \
        ({name: line.split("`")[3] for name, line in zip(("index.json", "index.json.tmp"), lines)}, [])
    assert "no 'Left out' entry" in gate.left_out(log.format(lines[1]), "frozen", folder)[1][0]
    assert "is not one 'Left out' entry" in gate.left_out(log.format("- Left out: `index.json`, SHA-256 `x`"),
                                                          "frozen", folder)[1][0]


def test_every_dry_run_case_names_a_rule_of_the_gate():
    rules = {f"G{n}" for n in range(1, 13)}
    for name, (_, check, text) in {**test_dry_run.BREAKS, **test_dry_run.VARIANTS}.items():
        assert check in rules and text, name
