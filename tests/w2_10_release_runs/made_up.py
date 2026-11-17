"""W2-10 dry run: made-up releases, built the way docs/w2-10-release-runs.md says the real one is, in a shared clone
of the repository, never in it. No model is called: every run is made by W2-08's test candidate agent with the stub
provider (release_common), and the rehearsal's practice world is the real one, made from seed 20261027 by the
repository's own generator into a temporary folder."""
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import release_common as rc
import release_gate as gate
from test_generation import PATCH  # W2-08's test generator that rejects its first tries

from baseline_run.copy_step import copy_baseline
from harness import audit, release, release_check, score
from worldgen.truth import load_truth

# "cut": killed while the harness wrote its items file, which ends in a cut-off line (review round 2, finding N2)
BEHAVIOURS = {"valid": {}, "killed": {}, "cut": {}, "aborted": {"abort_after": 40},
              "unsafe": {"close_true_match": True}, "refusals": {"refusals": True}}
KILLED = ("killed", "cut")
FULL = ("valid", "killed", "aborted", "valid", "valid")  # three valid runs, one killed and one aborted, replaced
SPEND, KILLED_SPEND, BALANCE = Decimal("0.10"), Decimal("0.05"), Decimal("4.56")
# the made-up release candidate's configuration, committed as the freeze's config/run-triage.json: the settings
# release_common.make_runs gives every run, so the rehearsal and the release runs are of the configured agent
CONFIG = {"agent": "candidate", "world": "../data/world", "model_config": "model-stub.json", "workers": 1,
          "pacer_per_minute": None, "infra_invalid_threshold": "0.05", "price_table": "prices.json",
          "modelled_time": "modelled_time.json"}
DOC = rc.REPO.joinpath("docs", "w2-10-release-runs.md")


def copy_as_is(clone, out, world):
    """The documented copy of a run-output folder whose index is lost (DEC-W2-10-LOST-INDEX), run as written: the
    `copy_as_is` function of the release steps, in bash. Returns what it prints."""
    lines = DOC.read_text(encoding="utf-8").splitlines()
    start = next(n for n, line in enumerate(lines) if line.startswith("copy_as_is() {"))
    function = "\n".join(lines[start:lines.index("}", start) + 1])
    script = f'REPO={clone}; PY={sys.executable}\n{function}\ncopy_as_is {out} {world}\n'
    return subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True).stdout


def practice_world(folder):
    """The practice world (seed 20261027), made by the repository's generator outside the repository."""
    world = Path(folder, "practice")
    subprocess.run([sys.executable, "-B", "-m", "worldgen", "--seed", "20261027", "--out", str(world)], cwd=rc.REPO,
                   check=True, capture_output=True)
    return world


class Release:
    """A made-up release: the clone, its freeze commit and the data its release log is written from."""

    def __init__(self, folder):
        self.folder, self.clone = Path(folder), Path(folder, "repo")
        self.outs, self.plans, self.spends = {}, {}, {}
        self.left_out = {}  # {world: what copy_as_is printed}

    def commit(self, message):
        rc.git(self.clone, "add", "-A")
        rc.git(self.clone, "commit", "-q", "--allow-empty", "-m", message)
        return rc.git(self.clone, "rev-parse", "HEAD").strip()

    def runs(self, at, world, plan, truth, name, workers=1):
        """Runs of `plan` on `world`, made with records.REPO at `at`, killed where the plan says. Returns the output."""
        with rc.at(at):
            out, ids = rc.make_runs(self.folder.joinpath(name), world, [BEHAVIOURS[p] for p in plan], truth, workers)
            if name == "rehearsal":  # run-and-score scores each run, so the rehearsal has its reports and set report
                score.score_all(out, world)
        for kind, run_id in zip(plan, ids):
            if kind in KILLED:
                items = out.joinpath(run_id, "items.jsonl").read_bytes()
                rc.kill(out, run_id)
                if kind == "cut":  # two whole records and half of the third
                    lines = items.split(b"\n")
                    out.joinpath(run_id, "items.jsonl").write_bytes(b"\n".join(lines[:2]) + b"\n" + lines[2][:40])
        self.outs[name], self.plans[name] = out, dict(zip(ids, plan))
        return out

    def checkpoints(self, name):
        """Copy the checkpoint of every run of `name` that wrote one into audit/checkpoints/."""
        for run_dir in sorted(p for p in self.outs[name].iterdir() if p.is_dir() and p.name != "sets"):
            if run_dir.joinpath(audit.CHECKPOINT).is_file():
                target = self.clone.joinpath("audit", "checkpoints", f"{run_dir.name}.json")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(run_dir.joinpath(audit.CHECKPOINT).read_bytes())

    def run_set(self, world):
        index = rc.records.read_index(self.clone.joinpath("release", world))
        return index["runs"][0]["run_set"] if index["runs"] else gate.NO_RUN_SET

    def check(self, world):
        """The release check's output for `world` at the clone's HEAD, as the command prints it."""
        with rc.at(self.clone):
            result = release_check.check(self.clone.joinpath("release", world), self.run_set(world),
                                         release={"freeze": self.freeze, "fresh": world == "fresh"})
        return gate.output_text(result).encode("utf-8")

    def log(self, spends=None, tag="release-1-freeze", tag_line=None):
        """The release log, written from the committed data. `spends` is {run ID: Spend USD}; by default 0.10 a run
        and 0.05 for a killed run."""
        spends = {**self.spends, **(spends or {})}
        balance, rows, totals = BALANCE, {}, {}
        ordered = sorted((run_id, name) for name in self.plans for run_id in self.plans[name])
        for run_id, name in ordered:
            spend = spends.get(run_id, KILLED_SPEND if self.plans[name][run_id] in KILLED else SPEND)
            rows[run_id] = (f"{balance}", f"{balance - spend}", f"{spend}")
            balance -= spend
            totals[name] = totals.get(name, Decimal(0)) + spend
        text = ["# Release 1 log", "", f"- Freeze commit: `{self.freeze}`, tag `{tag}`", "", "## Rehearsal",
                "| " + " | ".join(gate.REHEARSAL_COLUMNS) + " |", "|" + "---|" * len(gate.REHEARSAL_COLUMNS)]
        for entry in rc.records.read_index(self.outs["rehearsal"])["runs"]:
            manifest = gate._json(self.outs["rehearsal"].joinpath(entry["run_id"], "manifest.json"))
            commit = manifest["git"]["commit"][:12] if manifest else "unknown"
            text.append(f"| 2 Nov 2026 | `{entry['run_id']}` | `{commit}` | `{entry['run_set'][:8]}` | {entry['state']} | "
                        f"made up | {harness(entry)} | {' | '.join(rows[entry['run_id']])} | 1900 | test |")
        line = tag_line or f"{self.freeze}\trefs/tags/{tag}^{{}}"
        text += ["", "## Freeze and push", "", "```", "2026-11-02T12:00:00Z", line, "```", "", "## Generation", ""]
        outputs = {world: gate._json(self.clone.joinpath("release", f"check-{world}.json")) for world in gate.WORLDS}
        for world in gate.WORLDS:
            text += ["", f"## {gate.HEADINGS[world]}", "| " + " | ".join(gate.RUN_COLUMNS) + " |",
                     "|" + "---|" * len(gate.RUN_COLUMNS)]
            if outputs[world] is None:  # a variant built without check outputs
                continue
            runs = (outputs[world]["release"]["runs"] or {"valid": [], "replaced": {}})
            # a row for every run of the index and every run folder: a lost index lists none (DEC-W2-10-LOST-INDEX)
            entries, dirs = gate._runs(self.clone.joinpath("release", world))
            for n, run_id in enumerate(sorted(set(entries) | dirs), 1):
                entry = entries.get(run_id)
                valid = run_id in runs["valid"]
                point = self.clone.joinpath("audit", "checkpoints", f"{run_id}.json").is_file()
                state, cause = (entry["state"], entry["rerun_cause"] or "none") if entry else ("none", "none")
                text.append(f"| {n} | `{run_id}` | {state} | {'valid' if valid else 'replaced'} | "
                            f"{'' if valid else runs['replaced'][run_id]} | {cause} | "
                            f"{'yes' if point else 'no'} | {harness(entry)} | {' | '.join(rows[run_id])} | test |")
            # the owner pastes the 'Left out' lines copy_as_is prints under the world's table (round 3, R3-2)
            left = [line for line in self.left_out.get(world, "").splitlines() if line.startswith("- Left out:")]
            text += [""] + left if left else []
        text += ["", "## Results", "| " + " | ".join(gate.RESULT_COLUMNS) + " |", "|---|---|---|---|"]
        for world, output in outputs.items():
            if output is not None:
                text.append(f"| {world} | `{output['run_set'][:8]}` | `release/check-{world}.json` | {output['result']} |")
        text += ["", "## Console sign-off", "", "| Run set | Console USD | Harness USD | Sign-off |", "|---|---|---|---|",
                 "", "## Running total", "",
                 f"Wave-2 spend: USD {Decimal('0.95') + sum(totals.values())} (before this log 0.95 + rehearsal "
                 f"{totals.get('rehearsal', 0)} + frozen {totals.get('frozen', 0)} + fresh {totals.get('fresh', 0)})", ""]
        self.clone.joinpath(release.RELEASE_LOG).write_text("\n".join(text), encoding="utf-8")

    def amend(self, change, message="Variant (test)"):
        """Change the published release in a commit on top of it, and move the publish tag there."""
        change(self)
        self.commit(message)
        rc.git(self.clone, "tag", "-f", gate.PUBLISH_TAG)

    def restore(self):
        """Back to the published release as built."""
        rc.git(self.clone, "reset", "-q", "--hard", self.published)
        rc.git(self.clone, "clean", "-qfdx")
        rc.git(self.clone, "tag", "-f", gate.PUBLISH_TAG, self.published)
        for name, commit in self.tags.items():
            rc.git(self.clone, "tag", "-f", name, commit)
        for name in set(rc.git(self.clone, "tag").split()) - set(self.tags) - {gate.PUBLISH_TAG}:
            rc.git(self.clone, "tag", "-d", name)


def harness(entry):
    cost = gate._cost(entry)
    return "none" if cost is None else f"{Decimal(cost.numerator) / Decimal(cost.denominator):.4f}"


def build(folder, practice, frozen=FULL, fresh=("valid",) * 3, rehearsal=("valid",), reject=0, rehearsal_world=None,
          rehearsal_workers=1, before_freeze=None, rehearsal_after_freeze=False, checkpoints_before_generation=False,
          before_checks=None, checks=True, rehearsal_evidence=None, lost_index=()):
    """A made-up release, published and tagged. The keywords make the variants of the dry run: `rehearsal_evidence`
    changes the rehearsal evidence before it is committed, and each world of `lost_index` loses its index in a crash
    and is copied in as it is."""
    made = Release(folder)
    clone = made.clone
    subprocess.run(["git", "clone", "-q", "--shared", str(rc.REPO), str(clone)], check=True)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
        rc.git(clone, "config", key, value)
    clone.joinpath(gate.RELEASE_CONFIG).write_text(json.dumps(CONFIG, indent=2) + "\n", encoding="utf-8")
    clone.joinpath("config", CONFIG["model_config"]).write_text(json.dumps(rc.STUB) + "\n", encoding="utf-8")
    made.commit("The release candidate's configuration (test)")
    if reject:
        path = clone.joinpath("worldgen", "build.py")
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("def generate(seed=None):\n", PATCH.format(reject=reject, crash=False)),
                        encoding="utf-8")
        made.commit("A test generator (test)")

    def rehearse():
        world = rehearsal_world(clone) if rehearsal_world else practice
        made.runs(clone, world, rehearsal, rc.fresh_truth(world), "rehearsal", workers=rehearsal_workers)
        copy_baseline(made.outs["rehearsal"], clone.joinpath(gate.REHEARSAL_DIR))
        made.checkpoints("rehearsal")
        if rehearsal_evidence:
            rehearsal_evidence(made, clone.joinpath(gate.REHEARSAL_DIR))
        made.commit("W2-10: rehearsal evidence (test)")

    if not rehearsal_after_freeze:
        rehearse()
    if before_freeze:
        before_freeze(clone)
        made.commit("A change before the freeze (test)")
    clone.joinpath("docs").mkdir(exist_ok=True)
    clone.joinpath(release.RELEASE_LOG).write_text("# Release 1 log\n\n## Freeze and push\n", encoding="utf-8")
    made.freeze = made.commit("W2-10: freeze (test)")
    rc.git(clone, "tag", "-a", "-m", "freeze", "release-1-freeze")
    if rehearsal_after_freeze:
        rehearse()
    checkout = made.folder.joinpath("checkout")
    short = not fresh and not checks
    if frozen or not short:
        rc.git(clone, "worktree", "add", "-q", "--detach", str(checkout), made.freeze)
    if short:
        # a short build, with no fresh-world run and no check output, checks none of G3, G4 and G5: its generation
        # record only names the freeze, and no world is generated (a generation takes about 2 s)
        record = {"freeze_commit": made.freeze, "tries": [], "accepted": None}
        made.folder.joinpath("generation.json").write_text(json.dumps(record) + "\n", encoding="utf-8")
    else:  # the generation needs HEAD at the freeze, so a rehearsal made after the freeze uses the freeze's checkout
        record = release.make_fresh_world(made.freeze, made.folder.joinpath("fresh-world"),
                                          made.folder.joinpath("generation.json"),
                                          repo=checkout if rehearsal_after_freeze else clone)

    def generation():
        clone.joinpath("release").mkdir(exist_ok=True)
        clone.joinpath(release.GENERATION).write_bytes(made.folder.joinpath("generation.json").read_bytes())
        made.commit("Release 1: generation record (test)")

    if not checkpoints_before_generation:
        generation()
    if frozen:
        made.runs(checkout, checkout.joinpath("data", "world"), frozen, load_truth(), "frozen")
    if fresh and record["accepted"]:
        world = made.folder.joinpath("fresh-world")
        made.runs(checkout, world, fresh, rc.fresh_truth(world), "fresh")
    for name in ("frozen", "fresh"):
        if name in made.outs:
            made.checkpoints(name)
            made.commit(f"Release 1: {name} checkpoints (test)")
    if checkpoints_before_generation:
        generation()
    for name in ("frozen", "fresh"):
        if name in lost_index:  # a crash cut the index off mid-write: it is not JSON, and no snapshot covers it
            index = made.outs[name].joinpath("index.json")
            index.write_bytes(index.read_bytes()[:100])
            made.left_out[name] = copy_as_is(clone, made.outs[name], name)
        elif name in made.outs:
            copy_baseline(made.outs[name], clone.joinpath("release", name))
    made.commit("Release 1: run output (test)")
    if checkout.exists():
        rc.git(clone, "worktree", "remove", "--force", str(checkout))
    if before_checks:
        before_checks(clone)
        made.commit("A change after the freeze (test)")
    # both outputs are made from the clean tree first, then copied in: an output written into the tree before the
    # other world's check would make that check see an untracked file (review round 1)
    outputs = {world: made.check(world) for world in (gate.WORLDS if checks else ())}
    for world, output in outputs.items():
        clone.joinpath("release", f"check-{world}.json").write_bytes(output)
    made.commit("Release 1: check outputs (test)")
    made.log()
    made.published = made.commit("Release 1: publish (test)")
    rc.git(clone, "tag", gate.PUBLISH_TAG)
    made.tags = {name: rc.git(clone, "rev-parse", name).strip() for name in rc.git(clone, "tag").split()
                 if name != gate.PUBLISH_TAG}
    return made
