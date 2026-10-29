"""The run step: every alert and control twin of a world, in three framings, one bundle per call
(FR-20, NFR-3, DEC-T06-TWINS, DEC-T06-FAULTS, DEC-T06-COST). Python standard library only.

It writes items.jsonl, the manifest and the run-set index. It does no scoring: it never imports worldgen.truth
and never opens a world's hidden folder. An exception out of the agent call, a wrong log hand-over or a world
that does not match its manifest is a harness fault: the run is marked aborted and writes no items.
"""
import json
import platform
import queue
import threading
import time
from collections import Counter
from concurrent import futures
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

from baseline_agent import prompt
from baseline_agent.agent import RETRIED
from baseline_agent.recommend import recommend
from framings import FRAMINGS, frame
from model_interface import providers
from triage_agent.record import PROMPT as TRIAGE_PROMPT
from triage_agent.recommend import recommend as triage_recommend
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

from . import cost as money
from . import manifest as records
from .agents import always_close, always_escalate

RETRIES = 2  # T05's default, passed on and recorded; not a setting, because it would be one more run-set input
TRANSIENT = ("timeout", "provider_error")  # the failure kinds of the two errors T05 retries
REVIEW_POLICIES = ("STRICT_FOUR_EYES", "none")
CONFIG_KEYS = ("agent", "world", "model_config", "workers", "pacer_per_minute", "infra_invalid_threshold",
               "price_table", "modelled_time")


class ConfigError(ValueError):
    """The run configuration is missing, unreadable or wrong. No run starts."""


class HarnessFault(Exception):
    """The harness could not get a usable result for one item. The run is aborted."""

    def __init__(self, item_id, cause, attempts):
        super().__init__(f"{item_id}: {type(cause).__name__}: {cause}")
        self.item_id, self.cause, self.attempts = item_id, cause, attempts


class WorldMismatch(Exception):
    """A world file outside hidden/ does not match the world manifest, or the manifest contradicts itself."""


def baseline(items, model, settings, item_id):
    """The baseline agent for one bundle, in its guarded child process. Returns (result, sink list)."""
    sink = []
    return recommend(items, model, settings, sink=sink, retries=RETRIES, correlation_id=item_id), sink


def triage(items, model, settings, item_id):
    """The upgraded agent for one bundle: the rubric's rules here, or the baseline's guarded child process for an
    alert whose close turns on a snippet. Returns (result, sink list)."""
    sink = []
    return triage_recommend(items, model, settings, sink=sink, retries=RETRIES, correlation_id=item_id), sink


# Agent name -> a function (evidence items, model, settings, item id) -> (result, the log records it handed over).
AGENTS = {"baseline": baseline, "triage": triage, "always_escalate": always_escalate, "always_close": always_close}
# Agent name -> the prompt record its manifest names, as the agent's own package states it: the prompt text and its
# hash and, for an agent with rule code, that code's hash (DEC-W2-02-LAYOUT). Any other agent that calls a model is
# the baseline's code and names the baseline's prompt; the reference agents keep the baseline's prompt hash among
# their run-set inputs, as before, so their run-set IDs do not change.
PROMPTS = {"baseline": {"text": prompt.SYSTEM + "\n" + prompt.USER, "sha256": prompt.PROMPT_SHA256},
           "triage": TRIAGE_PROMPT}
MODEL_FREE = ("always_escalate", "always_close")  # the reference agents call no model
MAX_WORKERS = 64
NOT_REAL = frozenset(("stub",))  # providers that are no real model; a run with any other refuses fixture files


UNFINISHED = "Unfinished"  # the error name of a model call that had not returned when its item did


def _prompt_bytes(request):
    """The UTF-8 bytes of a request's messages, or None for anything that is not such a request."""
    try:
        return sum(len(message.content.encode("utf-8")) for message in request.messages)
    except (AttributeError, TypeError):
        return None


class Tokens:
    """Wraps the model for ONE item and notes every attempt, failed ones included (DEC-T06-COST).

    A call is noted when it STARTS, as unfinished, and filled in when it returns or raises. So a call that is
    still under way when its item returns, as after a child timeout, is counted as a call without token counts
    and makes the cost a lower bound. `snapshot` is what an item keeps: later changes do not reach it.
    Every call also notes `prompt_bytes`, the UTF-8 bytes of its messages, so that a call that left no token counts
    can still be bounded (DEC-W2-01-ELIGIBILITY-2); it is null for a request that carries no messages.
    """

    def __init__(self, model):
        self._model, self.attempts = model, []

    def __call__(self, request):
        attempt = {"error": UNFINISHED, "input_tokens": None, "output_tokens": None, "model_id": None,
                   "prompt_bytes": _prompt_bytes(request)}
        self.attempts.append(attempt)
        try:
            result = self._model(request)
        except BaseException as error:
            attempt["error"] = type(error).__name__
            raise
        attempt.update(error=None, input_tokens=getattr(result, "input_tokens", None),
                       output_tokens=getattr(result, "output_tokens", None), model_id=getattr(result, "model_id", None))
        return result

    def snapshot(self):
        return [dict(attempt) for attempt in self.attempts]


def _json(path, error=ConfigError):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        raise error(f"cannot read {str(path)!r}: {problem}") from problem


def load_config(path):
    """Read a run configuration. Paths in it are relative to its own folder."""
    path = Path(path).resolve()
    raw = _json(path)
    if not isinstance(raw, dict) or set(raw) != set(CONFIG_KEYS):
        keys = set(raw) if isinstance(raw, dict) else set()
        raise ConfigError(f"run configuration keys are wrong: missing {sorted(set(CONFIG_KEYS) - keys)}, "
                          f"unknown {sorted(keys - set(CONFIG_KEYS))}")
    if not isinstance(raw["agent"], str) or raw["agent"] not in AGENTS:
        raise ConfigError(f"unknown agent {raw['agent']!r}; known agents: {sorted(AGENTS)}")
    whole = lambda value: isinstance(value, int) and not isinstance(value, bool)
    if not whole(raw["workers"]) or not 1 <= raw["workers"] <= MAX_WORKERS:
        raise ConfigError(f"workers must be a whole number from 1 to {MAX_WORKERS}")
    if raw["pacer_per_minute"] is not None and (not whole(raw["pacer_per_minute"]) or raw["pacer_per_minute"] < 1):
        raise ConfigError("pacer_per_minute must be null, for no pacing, or a whole number of 1 or more")
    try:
        threshold = Decimal(raw["infra_invalid_threshold"]) if isinstance(raw["infra_invalid_threshold"], str) else None
    except InvalidOperation:
        threshold = None
    if threshold is None or not threshold.is_finite() or not 0 <= threshold <= 1:
        raise ConfigError("infra_invalid_threshold must be a decimal string from 0 to 1")
    for key in ("world", "model_config", "price_table"):
        if not isinstance(raw[key], str) or not raw[key]:
            raise ConfigError(f"{key} must be a path")
    model_config = _json(path.parent.joinpath(raw["model_config"]))
    try:
        model, settings = providers.load(path.parent.joinpath(raw["model_config"]))
    except providers.ConfigError as problem:
        raise ConfigError(str(problem)) from problem
    if not isinstance(raw["modelled_time"], str) or not raw["modelled_time"]:
        raise ConfigError("every run needs the modelled-time parameter file: modelled_time must be a path")
    price_table = _json(path.parent.joinpath(raw["price_table"]))
    modelled_time = _json(path.parent.joinpath(raw["modelled_time"]))
    try:
        money.check_prices(price_table)
        money.check_times(modelled_time)
    except money.TableError as problem:
        raise ConfigError(str(problem)) from problem
    fixtures = [name for name, value in (("price table", price_table), ("modelled-time file", modelled_time))
                if money.is_fixture(value)]
    if fixtures and model_config["provider"] not in NOT_REAL:
        raise ConfigError(f"a run with the real provider {model_config['provider']!r} refuses a fixture: "
                          f"the {' and the '.join(fixtures)} must be of kind \"sourced\"")
    return {"raw": raw, "agent": raw["agent"], "world": path.parent.joinpath(raw["world"]).resolve(),
            "model": model, "settings": settings, "model_config": model_config, "workers": raw["workers"],
            "pacer_per_minute": raw["pacer_per_minute"], "threshold": raw["infra_invalid_threshold"],
            "price_table": price_table, "modelled_time": modelled_time}


def check_world(world, listed, hidden=False):
    """Check a world against `listed`, its MANIFEST.json. By default this is the agent-side check of the run
    step: every file outside hidden/, and none inside it. With `hidden` it checks the hidden files instead,
    which only the score step and the check-hidden command do. Returns {name: bytes} of the files it checked, each
    read once, so that a caller can use the very bytes that were checked."""
    files = listed["files"]
    lines = "".join(f"{name}:{files[name]}\n" for name in sorted(files))
    if records.sha256(lines.encode("utf-8")) != listed["world_hash"]:
        raise WorldMismatch("the manifest's world_hash does not match its own file list")
    checked = {}
    for name in sorted(files):
        if name.startswith("hidden/") == hidden and \
                records.sha256(checked.setdefault(name, Path(world).joinpath(name).read_bytes())) != files[name]:
            raise WorldMismatch(f"{name} does not match the world manifest")
    return checked


def bundles(world):
    """Every item of one run: the alerts, then the control twins, each in every framing. One bundle per item."""
    agent_dir = Path(world).joinpath("agent")
    for twin, alerts in ((False, load_alerts(agent_dir)), (True, load_twins(agent_dir))):
        for alert in alerts:
            for framing in FRAMINGS:
                yield {"item_id": f"{alert['id']}/{framing}", "alert_id": alert["id"], "framing": framing,
                       "twin": twin, "evidence": frame(alert, framing)}


def _one(item, agent, model, settings, queue_s):
    """One item: (its line, None), or (None, the HarnessFault). It shares nothing with any other call: its own
    token wrapper, and whatever sink the agent makes for it. A Ctrl-C that lands in the call is returned as a
    fault too, with the model calls made so far; that can only happen on the sequential path."""
    tokens = Tokens(model)
    begun = time.monotonic()
    try:
        result, sink = agent(item["evidence"], tokens, settings, item["item_id"])
        wall_s = time.monotonic() - begun
        if sink != [result["log"]]:
            raise ValueError("the agent did not hand over exactly one log record equal to its result's log")
    except (Exception, KeyboardInterrupt) as error:
        return None, HarnessFault(item["item_id"], error, tokens.snapshot())
    return {"item_id": item["item_id"], "alert_id": item["alert_id"], "framing": item["framing"],
            "twin": item["twin"], "sent_ids": sorted(one["id"] for one in item["evidence"]),
            "result": result, "wall_s": wall_s, "queue_s": queue_s, "attempts": tokens.snapshot()}, None


def hand_off(items, agent, model, settings, done, workers=1, pacer_per_minute=None, clock=time.monotonic, wait=time.sleep):
    """Call `agent` once per item and append one line per item to `done`, in the order the calls finish
    (DEC-T06-PARALLEL). The caller sorts.

    With one worker the calls are made one after another in this thread, with no pool. With more, up to
    `workers` calls run at once, each in its own thread, and an item is handed off only when a worker is free.
    With a pacer an item is handed off no sooner than 60 / `pacer_per_minute` seconds after the hand-off before
    it. The time an item waits for a worker or for the pacer is its `queue_s`; it is not part of its `wall_s`.
    Only this thread touches `done`.

    Each call must hand over exactly one log record, equal to its result's log. Anything else, or any exception
    out of a call, is a harness fault: nothing more is handed off, the calls in flight are waited for, and the
    first fault is raised with the attempts of every faulted call. Ctrl-C does the same, as a fault with no
    item. With one worker it cuts the call in flight short; with more, a second Ctrl-C during the wait is not
    caught.
    """
    interval = None if pacer_per_minute is None else 60 / pacer_per_minute
    interrupted = lambda attempts: HarnessFault(None, KeyboardInterrupt("the run was interrupted"), attempts)
    next_at = None

    def paced(queued):
        """Wait for the pacer, if there is one, and return how long this item has been waiting."""
        nonlocal next_at
        if interval is not None:
            now = clock()
            if next_at is not None and now < next_at:
                wait(next_at - now)
            next_at = clock() + interval
        return clock() - queued

    if workers == 1:  # the sequential path
        try:
            for item in items:
                line, fault = _one(item, agent, model, settings, paced(clock()))
                if fault:
                    raise interrupted(fault.attempts) if isinstance(fault.cause, KeyboardInterrupt) else fault
                done.append(line)
        except KeyboardInterrupt:  # between two calls
            raise interrupted([]) from None
        return

    free, results, faults = threading.Semaphore(workers), queue.SimpleQueue(), []
    in_flight = 0

    def work(item, queue_s):
        try:
            outcome = _one(item, agent, model, settings, queue_s)
        except BaseException as error:  # so that a call always answers and its worker is always given back
            outcome = None, HarnessFault(item["item_id"], error, [])
        results.put(outcome)
        free.release()

    def collect(block):
        nonlocal in_flight
        while in_flight and (block or not results.empty()):
            line, fault = results.get()
            in_flight -= 1
            faults.append(fault) if fault else done.append(line)

    pool = futures.ThreadPoolExecutor(max_workers=workers)
    try:
        try:
            for item in items:
                queued = clock()
                free.acquire()  # hand off only when a worker is free
                collect(block=False)
                if faults:
                    break
                queue_s = paced(queued)
                collect(block=False)  # again: a call may have failed during the pacer wait
                if faults:
                    break
                pool.submit(work, item, queue_s)
                in_flight += 1
        except KeyboardInterrupt:
            faults.insert(0, interrupted([]))
        collect(block=True)  # the calls in flight, each bounded by its agent's own limit
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if faults:
        faults[0].attempts = [attempt for fault in faults for attempt in fault.attempts]
        raise faults[0]


def infra_invalid(transient, total, threshold):
    """Whether a run with `transient` transient failures among `total` items is infrastructure-invalid: its
    share is strictly above `threshold`, a decimal string. Exact fractions, never floats (DEC-T06-INFRA-INVALID)."""
    return Fraction(transient, total) > Fraction(Decimal(threshold))


def _calls(attempts):
    """Model calls and token totals. A total is only over the attempts that reported a count."""
    return {"attempts": len(attempts),
            "without_token_counts": sum(1 for one in attempts if one["input_tokens"] is None or one["output_tokens"] is None),
            "input_tokens": sum(one["input_tokens"] or 0 for one in attempts),
            "output_tokens": sum(one["output_tokens"] or 0 for one in attempts)}


def run(config_path, out_dir, rerun_cause=None):
    """One run. Returns its manifest, whose `state` is "completed" or "aborted".

    `out_dir` is required and, in T06, must lie outside the repository. A ConfigError means no run started.
    """
    out = Path(out_dir).resolve()
    if out.is_relative_to(records.REPO):
        raise ConfigError(f"the run-output folder must lie outside the repository, not {str(out)!r}")
    config = load_config(config_path)
    listed = _json(config["world"].joinpath("MANIFEST.json"))
    settings = config["settings"]
    started, begun = datetime.now(timezone.utc), time.monotonic()
    commit, dirty = records.git_state(records.REPO, out)
    price_hash = records.content_hash(config["price_table"])
    time_hash = records.content_hash(config["modelled_time"])
    inputs = {"agent": config["agent"], "commit": commit, "world_hash": listed["world_hash"],
              "prompt_hash": PROMPTS.get(config["agent"], PROMPTS["baseline"])["sha256"],
              "model_config": records.content_hash(config["model_config"]), "workers": config["workers"],
              "pacer_per_minute": config["pacer_per_minute"], "infra_invalid_threshold": config["threshold"],
              "price_table": price_hash, "modelled_time": time_hash}
    rule_code = PROMPTS.get(config["agent"], {}).get("rule_code_sha256")
    if rule_code is not None:  # only an agent with rule code: every other agent's run-set ID stays as it was
        inputs["rule_code_hash"] = rule_code
    run_set = records.content_hash(inputs)
    superseded = records.read_index(out)["sets"].get(run_set)
    if superseded:  # refused before any call (DEC-T06-FAULTS)
        raise ConfigError(f"run set {run_set[:8]} was superseded by {superseded['superseded_by'][:8]} "
                          f"({superseded['cause']}); no run is added to a superseded set")
    run_id = f"{started:%Y%m%dT%H%M%S%f}Z-{run_set[:8]}"
    run_dir = out.joinpath(run_id)
    run_dir.mkdir(parents=True)
    entry = {"run_id": run_id, "run_set": run_set, "state": "started", "dirty": dirty, "infra_invalid": None,
             "cause": None, "rerun_cause": rerun_cause, "calls": None, "cost": None,
             "started_at": started.isoformat()}
    records.index_update(out, entry)

    done, aborted, extra = [], None, []
    try:
        check_world(config["world"], listed)
        hand_off(bundles(config["world"]), AGENTS[config["agent"]], config["model"], settings, done,
                 workers=config["workers"], pacer_per_minute=config["pacer_per_minute"])
    except HarnessFault as fault:
        aborted = {"item_id": fault.item_id, "error_type": type(fault.cause).__name__, "message": str(fault.cause)}
        extra = fault.attempts
    except Exception as error:  # the world check, loading or framing
        aborted = {"item_id": None, "error_type": type(error).__name__, "message": str(error)}
    except KeyboardInterrupt:  # Ctrl-C before the first hand-off: the run is listed, so it is marked aborted
        aborted = {"item_id": None, "error_type": "KeyboardInterrupt", "message": "the run was interrupted"}

    uses_model = config["agent"] not in MODEL_FREE
    done.sort(key=lambda line: line["item_id"])
    attempts = [one for line in done for one in line["attempts"]] + extra
    transient = sum(1 for line in done if line["result"]["failure_kind"] in TRANSIENT)
    # over all items, main and twin; an aborted run is not judged
    marked = None if aborted or not done else infra_invalid(transient, len(done), config["threshold"])
    outputs = None
    if aborted is None:
        text = "".join(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n" for line in done)
        run_dir.joinpath("items.jsonl").write_text(text, encoding="utf-8")
        outputs = {"items_file": "items.jsonl", "sha256": records.sha256(text.encode("utf-8"))}
    twins = sum(1 for line in done if line["twin"])
    # The shape of this manifest, of the index entries and of the item rows is harness/schema.py, which the score
    # step checks them against: change both together (tests/t06_harness/test_schema.py fails otherwise).
    manifest = {
        "run_id": run_id, "run_set": run_set, "run_set_inputs": inputs,
        "state": "completed" if aborted is None else "aborted", "aborted": aborted, "rerun_cause": rerun_cause,
        "agent": config["agent"],
        "world": {key: listed[key] for key in ("world_hash", "generator_version", "rubric_version")},
        # an agent that calls no model has no model, prompt, decoding or retry policy to record
        "model": {"used": uses_model, "provider": config["model_config"]["provider"] if uses_model else None,
                  "requested": settings.model if uses_model else None,
                  "reported": dict(Counter(one["model_id"] for one in attempts if one["model_id"] is not None))},
        "prompt": dict(PROMPTS.get(config["agent"], PROMPTS["baseline"])) if uses_model else None,
        "decoding": {"temperature": settings.temperature, "max_tokens": settings.max_tokens} if uses_model else None,
        "retry_policy": {"retries": RETRIES, "timeout_s": settings.timeout_s, "retried_errors": list(RETRIED),
                         "backoff": None} if uses_model else None,
        "review_policies": list(REVIEW_POLICIES),
        "modelled_time": {"sha256": time_hash, "parameters": config["modelled_time"]},
        "price_table": {"sha256": price_hash, "table": config["price_table"]},
        "outputs": outputs,
        "git": {"commit": commit, "dirty": dirty},
        "config_sha256": records.content_hash(config["raw"]), "framing_code_sha256": records.framing_hash(),
        "python_version": platform.python_version(), "workers": config["workers"],
        "pacer_per_minute": config["pacer_per_minute"],
        "infra_invalid": {"threshold": config["threshold"], "transient_items": transient,
                          "transient_share": str(Decimal(transient) / Decimal(len(done))) if done else None,
                          "marked": marked},
        "started_at": started.isoformat(), "ended_at": datetime.now(timezone.utc).isoformat(),
        "timing": {"duration_s": time.monotonic() - begun, "queue_s": sum(line["queue_s"] for line in done)},
        "items": {"main": len(done) - twins, "twin": twins, "total": len(done)},
        "calls": _calls(attempts), "cost": money.cost(attempts, config["price_table"]),
    }
    records.write_json(run_dir.joinpath("manifest.json"), manifest)
    cause = None if aborted is None else f"{aborted['error_type']}: {aborted['message']}"
    records.index_update(out, {**entry, "state": manifest["state"], "infra_invalid": marked, "cause": cause,
                               "calls": manifest["calls"], "cost": manifest["cost"]})
    return manifest
