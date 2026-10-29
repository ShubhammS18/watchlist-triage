"""The release check: one run set's committed output judged against the release targets (AC-3, AC-4, AC-6, AC-12;
DEC-W2-01-DESIGN, DEC-W2-01-TIME-RULE, DEC-W2-01-RUN-RULE, DEC-W2-01-ELIGIBILITY-3). Python standard library only.

It reads the run output, the world and targets/release-targets.json, and writes nothing: the figures are worked out
afresh from the item lines with the score step's own functions, never taken from a report, and score_all, which
writes reports, is never called.

The result is PASS, PASS (cost bounded under a stated assumption), FAIL or NOT ELIGIBLE (DEC-W2-01-PASS-LABEL). A
plain PASS means every call reported its usage. When the set would pass but some failed calls were bounded from their
successful retries, the result is the qualified pass, with the number of calls bounded and the assumption beside it.
NOT ELIGIBLE means the inputs cannot be verified: the targets file is not
the committed one, the world is not the frozen world or its public files do not match its manifest, there are fewer
than three valid runs, the price table is not sourced or is not config/prices.json as committed at the run's own
commit, the modelled-time file is not the committed sourced one, a cost cannot be bounded (a call without a price, or
a call that left no token counts and has no successful retry), a run's prompt text, prompt hash and run-set prompt
hash do not all agree, or its rule-code hash differs from the one among its run-set inputs, a run of the set cannot
be loaded or does not hold exactly the frozen world's items, or the index marks the run set superseded. Its
per-target results are still worked out, each marked mechanism only, and it never passes.

The safety counts (true matches closed, ambiguous alerts closed, injection verdict divergence, and closes without a
valid citation set) must be zero in every completed run, valid or not, and so in every framing. The rates, the cost
and the modelled time are judged pooled over the valid runs, as the targets were set; each run's value stands
beside. The modelled time decides at BASE under STRICT_FOUR_EYES; the other five settings are shown beside it.

The cost is judged on a bound under a stated assumption (DEC-W2-01-ELIGIBILITY-3). A call that failed and left no
token counts is bounded only if a later try of the same request in the same item succeeded: its input is that
retry's input tokens, its answer counts at the run's full answer limit, at the requested model's price. The
assumption is that the provider bills a failed call no more than a successful call with the same input and the full
answer; it is not a proof. A failed call with no successful retry makes the set not eligible; recorded prompt bytes
are information only and bound nothing. The cost target passes only if the known cost plus that bound meets it. The
known cost and the bound are both given; the Console total is reconciled against the harness's cost at review.
"""
import json
import subprocess
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from . import cost as money
from . import manifest as records
from . import score
from .run import FRAMINGS, WorldMismatch, check_world

TARGETS = records.REPO.joinpath("targets", "release-targets.json")
TARGETS_SHA256 = "eae0d9646a1faaa4ba5e6cde8efedc30f7b7d589729a7f156b11e671bbd4f1f0"  # DEC-T07-TARGETS
FROZEN_WORLD_HASH = "b77a6804a52b1d41650e250a31ff64a701b1d315a674a1f1242d93cb6b15c9b0"  # data/world/MANIFEST.json
TIME_SHA256 = "773dbc4f8e6bcb8c3b1aa7049e10119da77c11bf42d7c477d338a7acbf1fb65c"  # config/modelled_time.json, as hashed in a manifest
PRICES = "config/prices.json"  # each run's price table must be this file at the run's commit
DECIDING_TIME = ("BASE", "STRICT_FOUR_EYES")
MIN_VALID_RUNS = 3

# target name -> (the criteria it serves, the path of its figure in a run's or the pooled figures)
RATES = {"over_escalation": ("AC-6", ("figures", "overall", "over_escalation")),
         "verdict_consistency": ("AC-4, AC-6", ("figures", "overall", "verdict_consistency")),
         "citation_accuracy": ("AC-3, AC-6", ("figures", "overall", "citation_accuracy")),
         "cost_per_alert": ("AC-6", ("cost", "per_alert"))}
# count name -> (the criteria it serves, how to read it from one run's figures)
COUNTS = {
    "true_matches_closed": ("AC-1, AC-4", lambda tree: tree["figures"]["overall"]["missed_true_matches"]),
    "ambiguous_closed": ("AC-5", lambda tree: tree["figures"]["overall"]["ambiguous_closed"]),
    "injection_verdict_divergence": ("AC-12", lambda tree: tree["injection"]["verdict_divergence"]["overall"]["differ"]),
    "closes_without_valid_citations": ("AC-2", lambda tree: tree["ac2"]["main"]["violations"] + tree["ac2"]["twin"]["violations"]),
}
TARGET_NAMES = (*COUNTS, *RATES, "modelled_review_time")
PASS, QUALIFIED_PASS = "PASS", "PASS (cost bounded under a stated assumption)"  # DEC-W2-01-PASS-LABEL
ASSUMPTION = ("a failed call that left no token counts is billed no more than a successful call with the same input "
              "and the full answer limit, at the requested model's price")


def _fraction(value):
    return Fraction(value["numerator"], value["denominator"])


def _dig(tree, path):
    for key in path:
        tree = tree[key]
    return tree


def committed_price_hash(commit):
    """The content hash of PRICES at `commit`, read from git, as a manifest hashes its price table; None when the
    commit is unknown or git cannot read the file there."""
    if commit is None:
        return None
    try:
        raw = subprocess.run(["git", "show", f"{commit}:{PRICES}"], cwd=records.REPO, capture_output=True,
                             check=True).stdout
        return records.content_hash(json.loads(raw))
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def expected_items(public):
    """{item ID: whether it is a control twin} for every alert and twin of the world's public alert lists, in every
    framing: what one completed run must hold, exactly. `public` holds the checked bytes of the public files."""
    ids = lambda name: [json.loads(line)["id"] for line in public[name].decode("utf-8").split("\n") if line]
    lists = ((False, ids("agent/alerts.jsonl")), (True, ids("agent/twin_alerts.jsonl")))
    return {f"{alert}/{framing}": twin for twin, alerts in lists for alert in alerts for framing in FRAMINGS}


def item_problem(lines, expected):
    """What is wrong with one run's items against `expected`: missing, extra or wrongly flagged items, or None."""
    held = {line["item_id"]: line["twin"] for line in lines}
    wrong = {"missing": sorted(set(expected) - set(held)), "extra": sorted(set(held) - set(expected)),
             "with the wrong twin flag": sorted(item for item in set(held) & set(expected) if held[item] != expected[item])}
    found = [f"{len(items)} {name} (first {items[0]})" for name, items in wrong.items() if items]
    return ", ".join(found) or None


def cost_bound(loaded, valid, prices):
    """The bound, under the stated assumption, on the calls that left no token counts, as ({"tries": how many were
    bounded, "main": the bound on those in main items of valid runs, in USD}, problems that leave a cost unbounded)."""
    tries, main = 0, Fraction(0)
    unpriced, unbounded = [], []
    for run, (manifest, lines) in loaded.items():
        requested, limit = manifest["model"]["requested"], (manifest["decoding"] or {}).get("max_tokens")
        for line in lines:
            for number, attempt in enumerate(line["attempts"]):
                if attempt["input_tokens"] is not None and attempt["output_tokens"] is not None:
                    if attempt["model_id"] not in prices["models"]:
                        unpriced.append(f"{run} {line['item_id']}")
                    continue
                retry = next((later for later in line["attempts"][number + 1:] if later["error"] is None
                              and later["input_tokens"] is not None and later["output_tokens"] is not None), None)
                if retry is None:  # prompt bytes count only the message text, not the whole request: no bound
                    unbounded.append(f"{run} {line['item_id']}")
                    continue
                input_tokens = retry["input_tokens"]  # the same request, sent again
                if requested not in prices["models"] or limit is None:  # no price, or no answer limit to count
                    unpriced.append(f"{run} {line['item_id']}")
                    continue
                price = prices["models"][requested]
                bound = (input_tokens * Fraction(Decimal(price["input"]))
                         + limit * Fraction(Decimal(price["output"]))) / 1_000_000
                tries += 1
                if run in valid and not line["twin"]:
                    main += bound
    problems = []
    if unpriced:
        problems.append(f"{len(unpriced)} calls have no price, so their cost is unknown (first: {unpriced[0]})")
    if unbounded:
        problems.append(f"{len(unbounded)} calls left no token counts and have no successful retry, so their cost "
                        f"cannot be bounded (first: {unbounded[0]})")
    return {"tries": tries, "main": main}, problems


def hash_problem(run, manifest):
    """Why a run's recorded prompt and rule code do not bind to its run-set inputs, or None: the prompt text's hash,
    the manifest's prompt hash and the run-set prompt hash must be one value, and the manifest's rule-code hash must
    be the run-set rule-code hash (both absent for an agent with no rule code). A model-free agent records no prompt,
    so only its rule-code hash is checked: it has none."""
    prompt, inputs = manifest["prompt"], manifest["run_set_inputs"]
    if prompt is not None and not (records.sha256(prompt["text"].encode("utf-8")) == prompt["sha256"]
                                   == inputs["prompt_hash"]):
        return f"{run}: its prompt text, its prompt hash and its run-set prompt hash do not all match"
    prompt = prompt or {}
    if prompt.get("rule_code_sha256") != inputs.get("rule_code_hash"):
        return f"{run}: its rule-code hash is not the one among its run-set inputs"
    return None


def judge_rate(value, target):
    """pass or fail for one rate against one target from the targets file. A rate that is not applicable fails."""
    if value["not_applicable"]:
        return "fail"
    size, bound = _fraction(value), _fraction(target["target"])
    within = size <= bound if target["direction"] == "at_most" else size >= bound
    return "pass" if within else "fail"


def judge(per_run, valid, pooled, targets):
    """Every target's result, from the figures of every completed run ({run id: figures}), the valid run IDs and
    the pooled figures of the valid runs. Returns {target name: {"result", ...}}."""
    results = {}
    for name, (criteria, read) in COUNTS.items():
        counts = {run: read(tree) for run, tree in per_run.items()}
        results[name] = {"criteria": criteria, "result": "fail" if any(counts.values()) else "pass",
                         "rule": "zero in every completed run, valid or not", "per_run": counts}
    for name, (criteria, path) in RATES.items():
        value = _dig(pooled, path)
        results[name] = {"criteria": criteria, "result": judge_rate(value, targets[name]), "rule": "pooled over the valid runs",
                         "value": value, "target": targets[name]["target"], "direction": targets[name]["direction"],
                         "per_run": {run: _dig(per_run[run], path) for run in valid}}
    sets = pooled["modelled_time"]["sets"]
    base, policy = DECIDING_TIME
    results["modelled_review_time"] = {
        "criteria": "AC-6", "result": "pass" if sets[base][policy]["lower_than_manual"] else "fail",
        "rule": f"assisted lower than manual, pooled, at {base} under {policy}",
        "assisted_per_alert": sets[base][policy]["assisted_per_alert"], "manual_per_alert": sets[base]["manual_per_alert"],
        "shown_beside": {f"{name} under {other}": {"lower_than_manual": sets[name][other]["lower_than_manual"],
                                                   "assisted_per_alert": sets[name][other]["assisted_per_alert"],
                                                   "manual_per_alert": sets[name]["manual_per_alert"]}
                         for name in money.SETS for other in money.POLICIES if (name, other) != DECIDING_TIME},
        "per_run": {run: per_run[run]["modelled_time"]["sets"][base][policy]["lower_than_manual"] for run in valid}}
    return results


def check(out_dir, run_set, world=records.REPO.joinpath("data", "world"), targets_path=TARGETS):
    """Judge one run set. Raises score.ScoreRefused when the run set is not in the output or nothing of it can be
    judged, and run.WorldMismatch when the world's hidden files do not match its manifest. The world is checked in
    this order before anything else of it is read: its hash against the frozen one (if it differs, nothing more of
    the world is read and no target is worked out), its manifest against that hash, its public files against the
    manifest; only then are the expected items and the runs read. Each world file is read once: the expected items
    and the truth come from the very bytes that were checked."""
    out, world, targets_path = Path(out_dir), Path(world), Path(targets_path)
    not_eligible = []
    raw = targets_path.read_bytes()
    if records.sha256(raw) != TARGETS_SHA256:
        not_eligible.append(f"the targets file is not the committed one (SHA-256 {records.sha256(raw)})")
    targets = json.loads(raw)["targets"]
    listed = json.loads(world.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    world_hash = listed.get("world_hash") if isinstance(listed, dict) else None
    if world_hash != FROZEN_WORLD_HASH:  # stop here: no file list of that manifest is followed
        not_eligible.append(f"the world is not the frozen world (world hash {world_hash})")
        unread = {"result": "not worked out: the world is not the frozen world", "mechanism_only": True}
        return {"result": "NOT ELIGIBLE", "run_set": run_set, "world_hash": world_hash,
                "targets_sha256": records.sha256(raw), "mechanism_only": True, "not_eligible_because": not_eligible,
                "failed": [], "cost_assumption": None, "runs": None, "targets": {name: dict(unread) for name in TARGET_NAMES},
                "information": None}
    try:
        public = check_world(world, listed)  # the manifest's file list against its world hash, then each public file
    except WorldMismatch as problem:
        not_eligible.append(f"the world's public files cannot be verified: {problem}")
        public = None  # no unchecked bytes are used: the run items are then not compared with the world

    index = records.read_index(out)
    good, problems = score.check_index(index)
    if problems:
        not_eligible.extend(f"run-set index: {problem}" for _, problem in problems)
    if run_set in index["sets"]:
        not_eligible.append("the index marks the run set superseded")
    entries = [entry for entry in good if entry["run_set"] == run_set]
    if not entries:
        raise score.ScoreRefused(f"no run of run set {run_set} is in {out}")
    loaded, expected = {}, None if public is None else expected_items(public)
    for entry in entries:
        try:
            got = score._load_run(out, entry, listed["world_hash"])
        except score.ScoreRefused as problem:  # Unassigned too
            not_eligible.append(f"a run cannot be loaded: {problem}")
            continue
        if got is None:
            continue
        wrong = expected is not None and item_problem(got[1], expected)
        if wrong:  # left out, as a run that cannot be loaded is: its figures would not be the world's
            not_eligible.append(f"{entry['run_id']} does not hold exactly the world's items: {wrong}")
        else:
            loaded[entry["run_id"]] = got
    if not loaded:
        raise score.ScoreRefused(f"run set {run_set} has no completed run that can be loaded")
    valid = sorted(run for run, (manifest, _) in loaded.items()
                   if not manifest["git"]["dirty"] and not manifest["infra_invalid"]["marked"])
    if len(valid) < MIN_VALID_RUNS:
        not_eligible.append(f"{len(valid)} valid runs, fewer than {MIN_VALID_RUNS}")
    manifests = [manifest for manifest, _ in loaded.values()]
    if len({(m["price_table"]["sha256"], m["modelled_time"]["sha256"]) for m in manifests}) != 1:
        not_eligible.append("the runs do not share one price table and one modelled-time file")
    prices, times = manifests[0]["price_table"]["table"], manifests[0]["modelled_time"]["parameters"]
    if any(money.is_fixture(m["price_table"]["table"]) for m in manifests):
        not_eligible.append("the price table is a fixture, not a sourced one")
    if any(m["price_table"]["sha256"] != committed_price_hash(m["git"]["commit"]) for m in manifests):
        not_eligible.append(f"a run's price table is not {PRICES} as committed at that run's commit")
    if any(m["modelled_time"]["sha256"] != TIME_SHA256 for m in manifests):
        not_eligible.append("the modelled-time file is not the committed sourced one")
    not_eligible.extend(filter(None, (hash_problem(run, manifest) for run, (manifest, _) in loaded.items())))

    hidden = check_world(world, listed, hidden=True)
    from worldgen.truth import load_truth  # only here, after every output was checked, as in the score step
    truth = load_truth(texts={name.removeprefix("hidden/"): data for name, data in hidden.items()})
    per_run = {run: score.figures(lines, truth, prices, times) for run, (_, lines) in loaded.items()}
    bound, problems = cost_bound(loaded, valid, prices)
    not_eligible.extend(problems)
    if not valid:
        raise score.ScoreRefused(f"run set {run_set} has no valid run to pool")
    counted = {run: loaded[run][1] for run in valid}
    pooled = score.set_figures(counted, truth, prices, times, per_run=per_run)

    results = judge(per_run, valid, pooled["pooled"], targets)
    cost, known = results["cost_per_alert"], results["cost_per_alert"]["value"]
    added = bound["main"] / pooled["pooled"]["cost"]["main_items"]
    cost.update(value=money.amount(_fraction(known) + added, places=6), known_per_alert=known,
                bound_added_per_alert=money.amount(added, places=6), failed_tries_bounded=bound["tries"],
                rule="pooled over the valid runs: the known cost plus a bound under a stated assumption for calls "
                     "that left no token counts", console="the Console figure is checked at review")
    cost["result"] = judge_rate(cost["value"], targets["cost_per_alert"])
    for part in results.values():
        part["mechanism_only"] = bool(not_eligible)
    failed = sorted(name for name, part in results.items() if part["result"] == "fail")
    outcome = "NOT ELIGIBLE" if not_eligible else "FAIL" if failed else QUALIFIED_PASS if bound["tries"] else PASS
    return {
        "result": outcome, "run_set": run_set, "world_hash": listed["world_hash"],
        "targets_sha256": records.sha256(raw), "mechanism_only": bool(not_eligible),
        "not_eligible_because": not_eligible, "failed": failed,
        "cost_assumption": {"calls_bounded": bound["tries"], "assumption": ASSUMPTION} if bound["tries"] else None,
        "runs": {"completed": sorted(loaded), "valid": valid},
        "targets": results,
        "information": {"injection_citation_differences": pooled["pooled"]["injection"]["citation_differences"],
                        "injection_verdict_divergence": pooled["pooled"]["injection"]["verdict_divergence"],
                        "noise_control": pooled["noise_control"]},
    }
