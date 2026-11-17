"""W2-10: the release gate's rules, G1 to G12 of docs/w2-10-release-runs.md (DEC-W2-10-CHOICES, DEC-W2-10-STOPS).

`problems(repo, reproduced)` reads a checkout of the publish commit, and git, and returns every problem it finds as a
list of text, [] when the published release is complete and consistent. It never asks whether the release passed: a
published FAIL, NOT ELIGIBLE or NO FRESH WORLD is fine when it is consistent. It calls no model and makes no network
request. `reproduce` runs the release check itself, as the release steps do."""
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

from harness import audit, release, release_check
from harness import manifest as records

PRACTICE_WORLD_HASH = "e2cbcb692714c1d334de63a0f6db184d51466029ac91cabdc60b89507026ecb8"  # seed 20261027
START_SPEND = Fraction(95, 100)  # wave-2 spend before the release log (docs/w2-02-attempts.md)
RUN_LIMIT, SPEND_LIMIT, REFUSAL_LIMIT = Fraction(30, 100), Fraction(2), Fraction(2, 100)  # the three stop rules
WORLDS = ("frozen", "fresh")
NO_RUN_SET = "0" * 64  # the run set the check is given when there is no fresh world
PUBLISH_TAG = "release-1"
REHEARSAL_DIR = "rehearsal"
# what may change between the rehearsal's commit and the freeze: no code, prompt, configuration, target or world
CODE_FREE = ("tests/w2_10_release_runs/", "docs/", ".genesis/", "audit/checkpoints/", f"{REHEARSAL_DIR}/")
HEADINGS = {"rehearsal": "Rehearsal", "frozen": "Frozen world", "fresh": "Fresh world"}
RUN_COLUMNS = ["#", "Run ID", "State", "Valid or replaced", "Reason", "Re-run cause", "Checkpoint committed",
               "Harness USD", "Console before", "Console after", "Spend USD", "Note"]
REHEARSAL_COLUMNS = ["Date", "Run ID", "Agent commit", "Run set", "State", "Key figures", "Harness USD",
                     "Console before", "Console after", "Spend USD", "Peak memory MB", "Note"]
RESULT_COLUMNS = ["World", "Run set", "Check output", "Result"]
# the run settings and agent a rehearsal must share with the release runs: every run-set input but commit and world
SAME = ("agent", "model_config", "prompt_hash", "rule_code_hash", "price_table", "modelled_time", "workers",
        "pacer_per_minute", "infra_invalid_threshold")
TOTAL = re.compile(r"Wave-2 spend: USD (\S+) \(before this log 0\.95 \+ rehearsal (\S+) \+ frozen (\S+) \+ fresh (\S+)\)")
RELEASE_CONFIG = "config/run-triage.json"  # the release candidate's configuration, which the freeze pins
# the run-set inputs but commit and world that a configuration gives, as harness.run.run makes them, worked out with
# the code of the checkout it runs in (review round 2, finding N1)
_INPUTS = r"""
import json, sys
from pathlib import Path
from harness import manifest as records
from harness.run import PROMPTS
path = Path(sys.argv[1]); raw = json.loads(path.read_text(encoding="utf-8"))
load = lambda key: json.loads(path.parent.joinpath(raw[key]).read_text(encoding="utf-8"))
inputs = {"agent": raw["agent"], "prompt_hash": PROMPTS.get(raw["agent"], PROMPTS["baseline"])["sha256"],
          "model_config": records.content_hash(load("model_config")), "workers": raw["workers"],
          "pacer_per_minute": raw["pacer_per_minute"], "infra_invalid_threshold": raw["infra_invalid_threshold"],
          "price_table": records.content_hash(load("price_table")),
          "modelled_time": records.content_hash(load("modelled_time"))}
rule_code = PROMPTS.get(raw["agent"], {}).get("rule_code_sha256")
if rule_code is not None:
    inputs["rule_code_hash"] = rule_code
print(json.dumps(inputs))
"""
_ANCHORS = {}  # {freeze commit: the run-set inputs its configuration gives}; a freeze's code never changes


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def output_text(result):
    """What `python -m harness acceptance` prints for a result."""
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def reproduce(repo, world, run_set, freeze):
    """The release check's output for one world, from the documented command run in `repo` with `repo`'s own code."""
    command = [sys.executable, "-B", "-m", "harness", "acceptance", f"release/{world}", run_set, "--release", freeze]
    done = subprocess.run(command + (["--fresh"] if world == "fresh" else []), cwd=repo, capture_output=True)
    return done.stdout


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _decimal(cell):
    try:
        value = Decimal(cell)
    except (InvalidOperation, TypeError):
        return None
    return value if value.is_finite() else None


def _cost(entry):
    known = (entry or {}).get("cost") and entry["cost"]["known_cost"]
    return Fraction(known["numerator"], known["denominator"]) if known else None


def _harness_cell(cell, cost):
    """Why a Harness USD cell does not state `cost` (a Fraction, or None for a run with no cost), or None."""
    if cost is None:
        return None if cell == "none" else f"its Harness USD is {cell!r}, not none: the run has no harness cost"
    written = _decimal(cell)
    exact = Decimal(cost.numerator) / Decimal(cost.denominator)
    if written is None or written != exact.quantize(written, rounding=ROUND_HALF_UP):
        return f"its Harness USD {cell!r} is not the run's own cost {exact}"
    return None


def _table(text, heading, columns):
    """(rows as {column: cell}, problem or None) of one release-log table."""
    header, rows = release._table(text, heading)
    if header != columns:
        return [], f"the release log's '{heading}' table does not have the columns {columns}"
    return [dict(zip(columns, row)) for row in rows], None


def _spend(row, where):
    """(spend, problem or None): Spend USD must be Console before minus Console after."""
    before, after, spend = (_decimal(row.get(k)) for k in ("Console before", "Console after", "Spend USD"))
    if None in (before, after, spend):
        return None, f"{where}: Console before, Console after and Spend USD must be amounts"
    if spend != before - after:
        return Fraction(spend), f"{where}: Spend USD {spend} is not Console before {before} minus after {after}"
    return Fraction(spend), None


def _refusals(run_dir):
    """(the share of a run's items the model refused, as the wrapper's refusal checkpoint counts it, or None; why the
    share cannot be read, or None). Every complete record counts, as the wrapper's `splitlines()` counts it. A run
    whose manifest does not say completed may end without a newline, as a crash while the harness writes the file
    leaves it: that last line counts if it is a whole item record (review round 3, R3-1), and is left out only if it
    is cut off. Any other line that is not an item record makes the share unreadable (review round 2, finding N2)."""
    items = Path(run_dir, "items.jsonl")
    if not items.is_file():
        return None, None
    data = items.read_bytes()
    manifest = _json(Path(run_dir, "manifest.json"))
    key = (records.sha256(data), isinstance(manifest, dict) and manifest.get("state") == "completed")
    if key not in _SHARES:  # the same bytes always give the same answer; the dry run asks about each file often
        _SHARES[key] = _share(data, key[1])
    return _SHARES[key]


_SHARES = {}


def _share(data, completed):
    *lines, tail = data.split(b"\n")  # tail is b"" when the file ends with a newline
    if tail and completed:
        return None, "its items file does not end with a newline, but its manifest says completed"
    kinds = []
    for number, line in enumerate(lines, 1):
        try:
            kinds.append(json.loads(line)["result"]["failure_kind"])
        except (ValueError, KeyError, TypeError):
            return None, f"line {number} of its items file is not an item record"
    if tail:  # an unfinished run's last line, without its newline
        try:
            kinds.append(json.loads(tail)["result"]["failure_kind"])
        except (ValueError, KeyError, TypeError):
            pass  # cut off by the crash: not a record, so not counted
    return (Fraction(kinds.count("model_refusal"), len(kinds)) if kinds else Fraction(0)), None


LEFT_OUT = re.compile(r"- Left out: `([^`]+)`, SHA-256 `([0-9a-f]{64})`")
LEFT_OUT_PATHS = ("index.json", "index.json.tmp")  # what copy_as_is leaves outside git (DEC-W2-10-LOST-INDEX)


def left_out(text, world, folder):
    """({path: SHA-256} of the "Left out" lines in the release log's section of `world`, problems). Every such line
    has the form copy_as_is prints, for a file it may leave out, once. A world whose run folders are committed
    without an index needs one for its index.json: the bytes stay outside git, so the log is the only committed
    trace of them (review round 3, R3-2; DEC-W2-10-ROUND3)."""
    heading = f"## {HEADINGS[world]}\n"
    section = text.split(heading, 1)[1].split("\n## ", 1)[0] if heading in text else ""
    found, problems = {}, []
    for line in section.splitlines():
        if not line.startswith("- Left out:"):
            continue
        match = LEFT_OUT.fullmatch(line.strip())
        if not match or match[1] not in LEFT_OUT_PATHS or match[1] in found:
            problems.append(f"G6: the {world} world's line {line.strip()!r} is not one 'Left out' entry, with a path "
                            f"copy_as_is may leave out ({', '.join(LEFT_OUT_PATHS)}) and its SHA-256")
            continue
        found[match[1]] = match[2]
    _, dirs = _runs(folder)
    if dirs and not Path(folder, "index.json").exists() and "index.json" not in found:
        problems.append(f"G6: the {world} world's run folders are committed with no index.json, and the log has no "
                        "'Left out' entry with its path and SHA-256")
    return found, problems


def _runs(folder):
    """{run ID: index entry} and the run folders of one run-output folder. An index that is missing, not JSON or not
    of the index's shape gives no entries."""
    index = _json(Path(folder, "index.json"))
    runs = index.get("runs") if isinstance(index, dict) else None
    runs = runs if isinstance(runs, list) else []
    entries = {entry["run_id"]: entry for entry in runs
               if isinstance(entry, dict) and isinstance(entry.get("run_id"), str)}
    dirs = {p.name for p in Path(folder).iterdir() if p.is_dir() and p.name != "sets"} if Path(folder).is_dir() else set()
    return entries, dirs


def _anchor(repo, freeze, broken):
    """The run-set inputs but commit and world that the freeze's own configuration gives with the freeze's own code,
    or None if they cannot be worked out. When the freeze is not broken, the checkout's code is the freeze's."""
    if freeze not in _ANCHORS:
        with tempfile.TemporaryDirectory() as scratch:
            where = Path(repo)
            if broken:
                where = Path(scratch, "freeze")
                git(repo, "worktree", "add", "-q", "--detach", str(where), freeze)
            try:
                done = subprocess.run([sys.executable, "-B", "-c", _INPUTS, RELEASE_CONFIG], cwd=where,
                                      capture_output=True, text=True)
            finally:
                if broken:
                    git(repo, "worktree", "remove", "--force", str(where))
        _ANCHORS[freeze] = json.loads(done.stdout) if done.returncode == 0 else None
    return _ANCHORS[freeze]


def _unsafe(repo, refs):
    """Every symbolic link or other non-regular file under rehearsal/, on disk or in the trees of `refs`, as text.
    Nothing under rehearsal/ is read while there is one (review round 2, finding N3)."""
    top, found = Path(repo, REHEARSAL_DIR), []
    if top.is_symlink():
        return [f"{REHEARSAL_DIR} is a symbolic link"]
    for root, dirs, files in os.walk(top):  # os.walk never enters a linked folder; it is listed and caught here
        for name in sorted(dirs + files):
            path = Path(root, name)
            mode = os.lstat(path).st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                kind = "a symbolic link" if stat.S_ISLNK(mode) else "not a regular file"
                found.append(f"{path.relative_to(repo).as_posix()} is {kind}")
    for ref in refs:
        for line in git(repo, "ls-tree", "-r", ref, "--", f"{REHEARSAL_DIR}/").splitlines():
            meta, path = line.split("\t", 1)
            mode = meta.split(" ")[0]
            if mode not in release.REGULAR:
                found.append(f"{path} is committed at {ref[:12]} with git mode {mode}, not as a regular file")
    return found


def _added_in(repo, freeze, path):
    """The commit after the freeze that added `path`, or None."""
    found = git(repo, "log", "--format=%H", "--diff-filter=A", f"{freeze}..HEAD", "--", path).split()
    return found[-1] if found else None


def problems(repo, reproduced=None):
    """Every way the published release in `repo` (a clean checkout of the publish commit) is incomplete or
    inconsistent. `reproduced` is {world: the check's own output bytes} (G5), or None to skip G5."""
    repo, found = Path(repo), []
    # G1: the freeze commit, read from the generation record, not from a tag name
    record = _json(repo.joinpath(release.GENERATION))
    if not isinstance(record, dict) or not re.fullmatch(r"[0-9a-f]{40}", str(record.get("freeze_commit"))):
        return [f"G1: {release.GENERATION} is missing or names no freeze commit"]
    freeze = record["freeze_commit"]
    try:
        git(repo, "cat-file", "-e", f"{freeze}^{{commit}}")
        git(repo, "merge-base", "--is-ancestor", freeze, "HEAD")
    except subprocess.CalledProcessError:
        return [f"G1: the freeze commit {freeze} is not a commit before the publish commit"]
    try:
        if git(repo, "rev-parse", f"{PUBLISH_TAG}^{{commit}}") != git(repo, "rev-parse", "HEAD"):
            found.append(f"G9: the tag {PUBLISH_TAG} is not the commit checked")
    except subprocess.CalledProcessError:
        found.append(f"G9: there is no tag {PUBLISH_TAG}")
    outputs = {world: _json(repo.joinpath("release", f"check-{world}.json")) for world in WORLDS}
    for world, output in outputs.items():
        if not isinstance(output, dict):
            found.append(f"G9: release/check-{world}.json is missing or is not JSON")
        elif (output.get("release") or {}).get("freeze_commit") != freeze:
            found.append(f"G1: release/check-{world}.json does not name the freeze commit {freeze}")
    log = repo.joinpath(release.RELEASE_LOG)
    text = log.read_text(encoding="utf-8") if log.is_file() and not log.is_symlink() else ""
    if not text:
        return found + [f"G6: {release.RELEASE_LOG} is missing"]
    if f"- Freeze commit: `{freeze}`" not in text:
        found.append(f"G1: the release log's freeze line does not name {freeze}")
    # G2: a broken freeze is reported, not hidden (DEC-W2-10-STOPS)
    broken = release.freeze_problems(repo, freeze)
    for world, output in outputs.items():
        if isinstance(output, dict) and broken:
            named = output.get("not_eligible_because") or []
            if output.get("result") != "NOT ELIGIBLE" or any(p not in named for p in broken):
                found.append(f"G2: the freeze is broken ({broken[0]}), but release/check-{world}.json does not say "
                             "NOT ELIGIBLE and name every freeze problem")
    # G3: every seed is the seed function's, with no counter skipped
    tries = list(record.get("tries") or []) + ([record["accepted"]] if record.get("accepted") else [])
    if [one.get("counter") for one in tries] != list(range(len(tries))):
        found.append("G3: the generation record's counters do not run 0, 1, ... with no gap")
    for one in tries:
        if isinstance(one.get("counter"), int) and one.get("seed") != release.fresh_seed(freeze, one["counter"]):
            found.append(f"G3: the seed of counter {one['counter']} is not the seed function's")
    # G4: one accepted generation means the committed record equals the check's own replay
    fresh = outputs["fresh"] if isinstance(outputs["fresh"], dict) else {}
    if ((fresh.get("release") or {}).get("generation") or {}).get("recorded_matches") is not True:
        found.append("G4: the fresh-world check does not show the generation record equal to its replay")
    # G5: the committed check output is what the check gives
    for world in WORLDS if reproduced is not None else ():
        committed = repo.joinpath("release", f"check-{world}.json")
        if not committed.is_file() or committed.read_bytes() != reproduced[world]:
            found.append(f"G5: release/check-{world}.json is not what the release check gives at the publish commit")
    # G6: every run is in the log, within five per world
    spends, ordered = {}, []
    for world in WORLDS:
        entries, dirs = _runs(repo.joinpath("release", world))
        rows, bad = _table(text, HEADINGS[world], RUN_COLUMNS)
        found += [f"G6: {bad}"] if bad else []
        logged = [row["Run ID"].strip("`") for row in rows]
        runs_found = dirs | set(entries)
        if set(logged) != runs_found or len(logged) != len(set(logged)):
            found.append(f"G6: the {world} world's log rows, and its index and run folders, do not name the same runs")
        if len(runs_found | set(logged)) > 5:
            found.append(f"G6: the {world} world has {len(runs_found | set(logged))} runs, above five")
        output = outputs[world] if isinstance(outputs[world], dict) else {}
        # an index lost in a crash is published as it is, and that world as NOT ELIGIBLE (DEC-W2-10-LOST-INDEX)
        if set(entries) != dirs and output.get("result") != "NOT ELIGIBLE":
            found.append(f"G6: the {world} world's index and run folders do not name the same runs, and it is not "
                         "published as NOT ELIGIBLE")
        found += left_out(text, world, repo.joinpath("release", world))[1]
        runs = ((output.get("release") or {}).get("runs")) or {"valid": [], "replaced": {}}
        run_set = output.get("run_set")
        if entries and {entry.get("run_set") for entry in entries.values()} != {run_set}:
            found.append(f"G6: the {world} world's runs are not all of the published run set")
        if world == "fresh" and output.get("result") == release.NO_FRESH_WORLD and (dirs or run_set != NO_RUN_SET):
            found.append("G6: NO FRESH WORLD is published, but there are fresh-world runs or another run set")
        logged_spend = {}
        for row in rows:
            run, where = row["Run ID"].strip("`"), f"the {world} world's row for {row['Run ID']}"
            entry = entries.get(run)
            wanted = ("valid", "") if run in runs["valid"] else ("replaced", runs["replaced"].get(run))
            if (row["Valid or replaced"], row["Reason"]) != wanted:  # a valid run's Reason is empty (round 2, N5)
                found.append(f"G6: {where}: valid or replaced and the reason are not the check's {wanted}")
            # a run the index does not list has no state, re-run cause or harness cost to state: each is none
            state, cause = (entry.get("state"), entry.get("rerun_cause") or "none") if entry else ("none", "none")
            if row["State"] != state:
                found.append(f"G6: {where}: state {row['State']!r} is not the index's {state!r}")
            if row["Re-run cause"] != cause:
                found.append(f"G6: {where}: the re-run cause is not the index's {cause!r}")
            bad = _harness_cell(row["Harness USD"], _cost(entry))
            found += [f"G6: {where}: {bad}"] if bad else []
            committed = repo.joinpath("audit", "checkpoints", f"{run}.json").is_file()
            if row["Checkpoint committed"] != ("yes" if committed else "no"):
                found.append(f"G6: {where}: Checkpoint committed must say {'yes' if committed else 'no'}")
            spend, bad = _spend(row, f"G6: {where}")
            found += [bad] if bad else []
            spends[world] = spends.get(world, 0) + (spend or 0)
            logged_spend[run] = spend
        # the stop rules read every run the committed output holds, logged or not
        for run in sorted(runs_found):
            share, bad = _refusals(repo.joinpath("release", world, run))
            found += [f"G12: {world} run {run}: {bad}, so its refusal share cannot be read"] if bad else []
            ordered.append((run, world, logged_spend.get(run), _cost(entries.get(run)), share))
    # G7: order in the history
    freeze_tree = set(git(repo, "ls-tree", "-r", "--name-only", freeze).splitlines())
    added = _added_in(repo, freeze, release.GENERATION)
    if release.GENERATION in freeze_tree or added is None:
        found.append(f"G7: {release.GENERATION} was not added after the freeze")
    for world in WORLDS:
        for run in _runs(repo.joinpath("release", world))[1]:
            path = f"audit/checkpoints/{run}.json"
            if path in freeze_tree:
                found.append(f"G7: the checkpoint of release run {run} was committed at or before the freeze")
            commit = _added_in(repo, freeze, path)
            if world == "fresh" and commit and added and subprocess.run(
                    ["git", "merge-base", "--is-ancestor", added, commit], cwd=repo).returncode != 0:
                found.append(f"G7: the checkpoint of fresh-world run {run} was committed before the generation record")
    # G8: a completed rehearsal of the frozen agent on the practice world came first, with its evidence frozen
    found += _rehearsal(repo, text, freeze, freeze_tree, spends, ordered, broken)
    # G9: published and consistent, with exactly one Results row for each world (review round 2, finding N5)
    rows, bad = _table(text, "Results", RESULT_COLUMNS)
    found += [f"G9: {bad}"] if bad else []
    found += [f"G9: the Results table has a row for {row['World']!r}, which is not a release world"
              for row in rows if row["World"] not in WORLDS]
    for world in WORLDS:
        output = outputs[world] if isinstance(outputs[world], dict) else {}
        wanted = [{"World": world, "Run set": f"`{str(output.get('run_set'))[:8]}`",
                   "Check output": f"`release/check-{world}.json`", "Result": output.get("result")}]
        if [row for row in rows if row["World"] == world] != wanted:
            found.append(f"G9: the Results row of the {world} world is not {wanted[0]}")
    total = TOTAL.search(text.split("## Running total", 1)[-1])
    parts = [_decimal(one) for one in total.groups()] if total else [None]
    sums = [START_SPEND + sum(spends.values()), spends.get("rehearsal", 0), spends.get("frozen", 0),
            spends.get("fresh", 0)]
    if None in parts or [Fraction(one) for one in parts] != sums:
        found.append("G9: the running total is not 0.95 plus the Spend USD of every row, by section")
    # G10: the Console sign-off a qualified frozen-world pass needs
    bad = release.signoff_problem(repo)
    found += [f"G10: {bad}"] if bad else []
    # G11: the push evidence holds the peeled line of a tag on the freeze commit
    push = text.split("## Freeze and push", 1)[-1].split("\n## ", 1)[0] if "## Freeze and push" in text else ""
    tags = re.findall(rf"^{freeze}\s+refs/tags/(\S+)\^\{{\}}\s*$", push, re.M)
    if not tags:
        found.append("G11: the 'Freeze and push' section has no peeled tag line for the freeze commit")
    for tag in tags:
        try:
            if git(repo, "rev-parse", f"{tag}^{{commit}}") != freeze:
                found.append(f"G11: the tag {tag} does not name the freeze commit")
        except subprocess.CalledProcessError:
            found.append(f"G11: the tag {tag} is not in the repository")
    # G12: the three stop rules (DEC-W2-10-CHOICES, DEC-W2-10-STOPS)
    found += _stops(ordered)
    return found


def _unit(folder, run, entry, manifest):
    """Why a completed rehearsal run's files do not hold together as one run, or None (review round 2, finding N1).
    Every file a completed run writes is there, with its run set's set report. The run ID, run set, run-set inputs
    and index entry agree, and so do the prompt and rule-code hashes. The items file is the one the manifest names.
    The report and the set report are this manifest's. The log, which has verified against its committed checkpoint,
    starts with this manifest's run and ends with these items. The log's input hashes are its own: the practice
    world is not committed, so they cannot be made again."""
    run_dir, run_set = folder.joinpath(run), manifest.get("run_set")
    missing = [name for name in release.RUN_FILES if not run_dir.joinpath(name).is_file()]
    missing += [] if folder.joinpath("sets", f"{run_set}.json").is_file() else [f"sets/{run_set}.json"]
    if missing:
        return f"{', '.join(missing)} missing"
    inputs, prompt, entry = manifest["run_set_inputs"], manifest["prompt"] or {}, entry or {}
    if not (manifest["run_id"] == run and run.endswith(f"-{run_set[:8]}") and records.content_hash(inputs) == run_set
            and entry.get("run_set") == run_set and entry.get("state") == "completed"):
        return "its run ID, run set, run-set inputs and index entry do not agree"
    if (inputs["commit"], inputs["world_hash"], inputs["agent"]) != \
            (manifest["git"]["commit"], manifest["world"]["world_hash"], manifest["agent"]):
        return "its manifest's commit, world and agent are not its run-set inputs'"
    bad = release_check.hash_problem(run, manifest)
    if bad:
        return bad
    data = run_dir.joinpath("items.jsonl").read_bytes()
    if records.sha256(data) != manifest["outputs"]["sha256"]:
        return "its items file is not the one its manifest names"
    report = _json(run_dir.joinpath("report.json"))
    validity = {"dirty": manifest["git"]["dirty"], "infra_invalid": manifest["infra_invalid"]["marked"]}
    validity["valid"] = not (validity["dirty"] or validity["infra_invalid"])
    if (report["run_id"], report["run_set"], report["manifest"], report["validity"]) != \
            (run, run_set, manifest, validity):
        return "its report is not its manifest's"
    listed = _json(folder.joinpath("sets", f"{run_set}.json"))
    if listed["run_set"] != run_set or not any(one["run_id"] == run and one["valid"] for one in listed["runs"]):
        return f"sets/{run_set}.json does not list it as a valid run of its run set"
    logged = [json.loads(line) for line in run_dir.joinpath(audit.LOG).read_bytes().split(b"\n") if line]
    wanted = {"event": "run_started", "run_set": run_set, "commit": manifest["git"]["commit"],
              "dirty": manifest["git"]["dirty"], "world_hash": inputs["world_hash"], "agent": manifest["agent"],
              "prompt_sha256": prompt.get("sha256"), "rule_code_sha256": inputs.get("rule_code_hash"),
              "config_sha256": manifest["config_sha256"], "framing_code_sha256": manifest["framing_code_sha256"]}
    if {key: logged[0].get(key) for key in wanted} != wanted:
        return "its log's start record is not its manifest's"
    hashes = {one["item_id"]: one["input_sha256"] for one in logged if one["event"] == "recommendation"}
    lines = [json.loads(line) for line in data.split(b"\n") if line]
    return release.items_problem(run, logged, lines, manifest, hashes)


def _rehearsal(repo, text, freeze, freeze_tree, spends, ordered, broken):
    """G8: a completed, clean rehearsal on the practice world, of the agent and settings the freeze's own
    configuration gives, whose files hold together as one run, committed by the freeze with nothing linked."""
    unsafe = _unsafe(repo, (freeze, "HEAD"))
    if unsafe:
        return [f"G8: {one}; nothing in {REHEARSAL_DIR}/ is read" for one in unsafe]
    found = []
    folder = repo.joinpath(REHEARSAL_DIR)
    listed = {}
    for line in (folder.joinpath("SHA256SUMS").read_text(encoding="utf-8").splitlines()
                 if folder.joinpath("SHA256SUMS").is_file() else []):
        digest, _, name = line.partition("  ")
        listed[name] = digest
    files = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p.name != "SHA256SUMS"}
    if not listed or set(listed) != files or any(records.sha256(folder.joinpath(name).read_bytes()) != digest
                                                 for name, digest in listed.items()):
        found.append(f"G8: {REHEARSAL_DIR}/ is missing, or its SHA256SUMS does not list its files with their hashes")
    if any(name not in freeze_tree for name in (f"{REHEARSAL_DIR}/{one}" for one in files)):
        found.append(f"G8: the rehearsal evidence in {REHEARSAL_DIR}/ was not all committed by the freeze")
    entries, dirs = _runs(folder)
    rows, bad = _table(text, HEADINGS["rehearsal"], REHEARSAL_COLUMNS)
    found += [f"G8: {bad}"] if bad else []
    if {row["Run ID"].strip("`") for row in rows} != set(entries) or set(entries) != dirs:
        found.append("G8: the rehearsal rows, its index and its run folders do not name the same runs")
    release_inputs = []
    for world in WORLDS:
        for run in _runs(repo.joinpath("release", world))[1]:
            manifest = _json(repo.joinpath("release", world, run, "manifest.json"))
            if manifest:
                release_inputs.append(manifest["run_set_inputs"])
    anchor = _anchor(repo, freeze, broken)  # binds the rehearsal even when there is no release run (round 2, N1)
    if anchor is None:
        found.append(f"G8: the run-set inputs that the freeze's {RELEASE_CONFIG} gives cannot be worked out")
    completed, logged_spend = False, {}
    for row in rows:
        run = row["Run ID"].strip("`")
        entry, manifest = entries.get(run), _json(folder.joinpath(run, "manifest.json"))
        if entry is not None:  # the State and Run set cells are the index's and the manifest's (round 3, R3-3)
            told = [entry] + ([manifest] if isinstance(manifest, dict) else [])
            states = {str(one.get("state")) for one in told}
            if states != {row["State"]}:
                found.append(f"G8: the rehearsal row for {run}: state {row['State']!r} is not its index's and "
                             f"manifest's {sorted(states)}")
            sets = {str(one.get("run_set")) for one in told}
            if len(sets) != 1 or row["Run set"] != f"`{next(iter(sets))[:8]}`":
                found.append(f"G8: the rehearsal row for {run}: run set {row['Run set']} is not its index's and "
                             "manifest's")
        bad = _harness_cell(row["Harness USD"], _cost(entry)) if entry else None
        found += [f"G8: the rehearsal row for {run}: {bad}"] if bad else []
        spend, bad = _spend(row, f"G8: the rehearsal row for {run}")
        found += [bad] if bad else []
        spends["rehearsal"] = spends.get("rehearsal", 0) + (spend or 0)
        logged_spend[run] = spend
        if manifest is None:
            continue
        point = f"audit/checkpoints/{run}.json"
        if manifest["state"] in ("completed", "aborted"):
            trusted = _json(repo.joinpath(point))
            log = folder.joinpath(run, audit.LOG)
            if point not in freeze_tree or trusted is None or not log.is_file() or audit.verify(log.read_bytes(), trusted):
                found.append(f"G8: rehearsal run {run}'s log does not verify against a checkpoint committed by the freeze")
                continue
        commit = manifest["git"]["commit"]
        if row["Agent commit"].strip("`") not in (commit, commit[:7], commit[:12]):
            found.append(f"G8: the rehearsal row for {run} does not name its commit {commit[:12]}")
        if subprocess.run(["git", "merge-base", "--is-ancestor", commit, freeze], cwd=repo).returncode != 0:
            found.append(f"G8: rehearsal run {run} was not made at a commit before the freeze")
            continue
        changed = git(repo, "diff", "--name-only", commit, freeze).splitlines()
        if any(not path.startswith(CODE_FREE) for path in changed):
            found.append(f"G8: between rehearsal run {run}'s commit and the freeze, more than tests, docs, records and "
                         f"evidence changed (first: {next(p for p in changed if not p.startswith(CODE_FREE))})")
            continue
        if manifest["state"] != "completed" or manifest["git"]["dirty"] or manifest["infra_invalid"]["marked"]:
            continue
        try:
            bad = _unit(folder, run, entries.get(run), manifest)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
            bad = f"its files are not of the shapes a run writes ({type(error).__name__})"
        if bad:
            found.append(f"G8: rehearsal run {run}'s files do not hold together as one run: {bad}")
            continue
        same = {k: manifest["run_set_inputs"].get(k) for k in SAME}
        if (manifest["world"]["world_hash"] == PRACTICE_WORLD_HASH and anchor is not None
                and same == {k: anchor.get(k) for k in SAME}
                and all({k: one.get(k) for k in SAME} == same for one in release_inputs)):
            completed = True
    for run in sorted(dirs | set(entries)):  # the stop rules read every rehearsal run, logged or not
        share, bad = _refusals(folder.joinpath(run))
        found += [f"G12: rehearsal run {run}: {bad}, so its refusal share cannot be read"] if bad else []
        ordered.append((run, "rehearsal", logged_spend.get(run), _cost(entries.get(run)), share))
    if not completed:
        found.append("G8: there is no completed, clean rehearsal on the practice world with the agent and settings of "
                     f"the freeze's {RELEASE_CONFIG} and of the release runs, made at a commit whose code the freeze "
                     "kept")
    return found


def _stops(ordered):
    """Stop before the next run when a run costs over USD 0.30, when its refusals pass the 2% checkpoint, or when
    the release's spend passes USD 2.00. A run's cost is the larger of its harness cost and its Console spend."""
    found, spent = [], Fraction(0)
    ordered = sorted(ordered)  # a run ID starts with its start time, so this is the order the runs were made in
    for at, (run, world, spend, cost, refused) in enumerate(ordered):
        if at == len(ordered) - 1:
            break
        later = ordered[at + 1][0]
        spent += spend or 0
        worst = max(spend or 0, cost or 0)
        if worst > RUN_LIMIT:
            found.append(f"G12: {world} run {run} cost {float(worst):.2f} USD, over 0.30, and run {later} came after it")
        if refused is not None and refused > REFUSAL_LIMIT:
            found.append(f"G12: {world} run {run} passed the 2% refusal checkpoint, and run {later} came after it")
        if spent > SPEND_LIMIT:
            found.append(f"G12: the release had spent {float(spent):.2f} USD by run {run}, over 2.00, and run {later} "
                         "came after it")
    return found
