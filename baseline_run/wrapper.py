"""The run wrapper: the T07 baseline runs are started here; the harness's own run command still works without it
(DEC-T07-WRAPPER, DEC-T07-WRAPPER-CHECKS, DEC-T07-RUN-SETTINGS-2).

It refuses to start, naming the reason, unless every check below holds, in this order; only the last one uses
the network, so a run that fails an earlier check makes no network request (the tests check that none reaches the
fake server):

    a. the working tree is clean, untracked files included, and the output folder lies outside the repository
    b. the inputs the score step would refuse later are not there (harness known issue 3): a blank re-run cause,
       a model name of only spaces, a temperature or timeout that is not finite; and a written re-run cause is
       given when the last earlier run in the output folder was aborted, never finished or infra-invalid
    c. the run configuration is the recorded one, the agent is one of the model agents named here, and the model
       is asked at https://api.anthropic.com only
    d. the modelled-time file is sourced, LOW <= BASE <= HIGH for every parameter, and every value is above 0
    e. the price table is sourced and prices the configured model
    f. the API key is set and well formed, and one free token-counting request with it succeeds; that request
       never follows a redirect

Then it prints an upper bound on the run cost for one attempt per item that the agent sends to the model (retries
not counted; it assumes at most one token per prompt byte), asks the owner to type "yes", and runs the harness's
run-and-score through tools/timed_run.sh. After the run it prints the run's own report status and its refusal
share, and flags the run-1 refusal checkpoint (DEC-T07-REFUSALS).
"""
import http.client
import json
import math
import os
import subprocess
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlsplit

from baseline_agent import prompt
from baseline_agent.payload import build_payload
from harness import cost as money
from harness import manifest as records
from harness.run import bundles, load_config
from model_interface.anthropic_api import API_URL, KEY_VARIABLE, VERSION, Anthropic
from triage_agent.rules import decide

REPO = records.REPO
# The recorded run settings (DEC-T07-RUN-SETTINGS-2, DEC-T07-PROVIDER-2). A change needs a superseding record first.
RECORDED = {"provider": "anthropic", "temperature": 1, "thinking": "disabled", "max_tokens": 512, "timeout_s": 30,
            "workers": 4, "pacer_per_minute": 120, "infra_invalid_threshold": "0.02"}
# The agents a paid run may use, chosen by the run configuration's "agent" (DEC-W2-02-LAYOUT), and for each whether
# it sends an item to the model; the upgraded agent sends only the items its rules do not decide.
MODEL_AGENTS = {"baseline": lambda payload: True, "triage": lambda payload: decide(payload["items"]) is None}
ENV = {"MEMORY_GUARD_MAX_SECONDS": "7200", "BENCH_MAX_S": "0.82"}
CREDIT_MARGIN = Fraction(3, 2)
REFUSAL_CHECKPOINT = Fraction(2, 100)  # more than this share of run 1's items refused: stop and decide
KEY_CHECK_URL = API_URL  # where the key check is sent; only the tests point it at a fake server on this machine


class Refused(Exception):
    """A pre-run check failed. Nothing was started."""


def _read(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        raise Refused(f"cannot read the {what} {str(path)!r}: {problem}") from None


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def rerun_needed(out):
    """Whether the next run in `out` is a re-run: the last run started there was aborted, never finished, or
    completed but infra-invalid."""
    runs = sorted(records.read_index(out)["runs"], key=lambda run: run["started_at"])
    return bool(runs) and (runs[-1]["state"] != "completed" or runs[-1]["infra_invalid"] is True)


def check_clean(repo, out):
    """a."""
    done = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo, capture_output=True,
                          text=True)
    if done.returncode != 0:
        raise Refused("git cannot say whether the working tree is clean")
    if done.stdout:
        raise Refused("the working tree is not clean (untracked files included):\n" + done.stdout.rstrip())
    if Path(out).resolve().is_relative_to(REPO):
        raise Refused(f"the output folder must lie outside the repository, not {str(out)!r}")


def check_inputs(model_config, out, rerun_cause):
    """b."""
    if rerun_cause is not None and not rerun_cause.strip():
        raise Refused("the re-run cause is blank: write what went wrong with the run this one replaces")
    if not isinstance(model_config.get("model"), str) or not model_config["model"].strip():
        raise Refused("the model name is missing or made only of spaces")
    for key in ("temperature", "timeout_s"):
        if not _finite(model_config.get(key)):
            raise Refused(f"the model configuration's {key} is not a finite number: {model_config.get(key)!r}")
    if rerun_cause is None and rerun_needed(out):
        raise Refused("the last run in the output folder was aborted, never finished or infra-invalid: this run "
                      "is a re-run and needs --rerun-cause")


def check_settings(run_config, model_config):
    """c."""
    found = {"provider": model_config.get("provider"), "temperature": model_config.get("temperature"),
             "thinking": (model_config.get("options") or {}).get("thinking"),
             "max_tokens": model_config.get("max_tokens"), "timeout_s": model_config.get("timeout_s"),
             **{key: run_config.get(key) for key in ("workers", "pacer_per_minute", "infra_invalid_threshold")}}
    for key, wanted in RECORDED.items():
        value = found[key]
        if isinstance(value, bool) or value != wanted:  # True == 1 in Python, so a flag is refused first
            raise Refused(f"{key} is {value!r}, not the recorded {wanted!r}")
    if run_config.get("agent") not in MODEL_AGENTS:
        raise Refused(f"agent is {run_config.get('agent')!r}, not one of the model agents {sorted(MODEL_AGENTS)}")
    base_url = (model_config.get("options") or {}).get("base_url", API_URL)
    if base_url != API_URL:  # a paid run sends the key to Anthropic and nowhere else (review round 1, T07-01)
        raise Refused(f"the model configuration's base_url must be exactly {API_URL} (the default), not {base_url!r}")


def check_times(parameters):
    """d."""
    try:
        money.check_times(parameters)
    except money.TableError as problem:
        raise Refused(f"the modelled-time file: {problem}") from None
    if parameters["kind"] != "sourced":
        raise Refused('the modelled-time file must be of kind "sourced"')
    sets = parameters["sets"]
    for name in money.PARAMETERS:
        low, base, high = (Decimal(sets[s][name]) for s in money.SETS)
        if not 0 < low <= base <= high:
            raise Refused(f"modelled time {name}: LOW <= BASE <= HIGH and every value above 0 must hold, "
                          f"not {low} / {base} / {high}")


def check_prices(table, model):
    """e."""
    try:
        money.check_prices(table)
    except money.TableError as problem:
        raise Refused(f"the price table: {problem}") from None
    if table["kind"] != "sourced":
        raise Refused('the price table must be of kind "sourced"')
    if model not in table["models"]:
        raise Refused(f"the price table has no entry for the configured model {model!r}")


def check_key(model_config, url=None):
    """f. The key is checked by making the adapter, then used for one token-counting request to `url` (KEY_CHECK_URL
    unless given), which Anthropic's docs say is free. The request is made with http.client, which never follows a
    redirect: any 3xx reply is a refusal, so the key cannot be carried to another host (review round 1, T07-01).
    No error text names the key."""
    options = model_config.get("options") or {}
    try:
        Anthropic(**options)
    except (TypeError, ValueError) as problem:
        raise Refused(str(problem)) from None
    target = urlsplit(url or KEY_CHECK_URL)
    kind = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
    body = json.dumps({"model": model_config["model"], "messages": [{"role": "user", "content": "ping"}]})
    headers = {"x-api-key": os.environ[KEY_VARIABLE], "anthropic-version": VERSION, "content-type": "application/json"}
    connection = kind(target.hostname, target.port, timeout=15)
    try:
        connection.request("POST", "/v1/messages/count_tokens", body=body.encode("utf-8"), headers=headers)
        response = connection.getresponse()
        response.read()
        status = response.status
    except (OSError, http.client.HTTPException) as error:
        raise Refused(f"the key check could not reach the provider: {type(error).__name__}") from None
    finally:
        connection.close()
    if 300 <= status < 400:
        raise Refused(f"the key check was redirected (HTTP {status}); a redirect is never followed")
    if status != 200:
        what = "the API key does not authenticate" if status in (401, 403) else "the key check was refused"
        raise Refused(f"{what}: HTTP {status} from the token-counting endpoint")


def expected_cost(world, table, model, max_tokens, agent="baseline"):
    """The upper bound of DEC-T07-WRAPPER-CHECKS, as (calls, prompt bytes, cost): one call per item the agent sends
    to the model, every prompt byte one input token, every answer max_tokens output tokens. Retries are not counted."""
    calls = size = 0
    for item in bundles(world):
        payload = build_payload(item["evidence"])
        if not MODEL_AGENTS[agent](payload):
            continue
        calls += 1
        size += sum(len(m["content"].encode("utf-8")) for m in prompt.build_messages(payload))
    prices = table["models"][model]
    total = (size * Fraction(Decimal(prices["input"])) + calls * max_tokens * Fraction(Decimal(prices["output"])))
    return calls, size, total / 1_000_000


def launch(command, env):
    return subprocess.run(command, cwd=REPO, env=env).returncode


def after(out, before):
    """Print each new run's own report status and refusal share. Returns the refusal shares by run."""
    index = records.read_index(out)
    shares = {}
    for run in index["runs"]:
        if run["run_id"] in before:
            continue
        run_dir = Path(out).joinpath(run["run_id"])
        attempt = sum(1 for one in index["runs"] if one["run_set"] == run["run_set"])
        print(f"run {run['run_id']}: {run['state']}, attempt {attempt} in run set {run['run_set'][:8]}")
        report = run_dir.joinpath("report.json")
        if report.exists():
            validity = json.loads(report.read_text(encoding="utf-8"))["validity"]
            print(f"  its report: valid {validity['valid']} (dirty {validity['dirty']}, "
                  f"infra-invalid {validity['infra_invalid']})")
        else:
            print("  it has no report")
        items = run_dir.joinpath("items.jsonl")
        if not items.exists():
            print("  it has no items, so no refusal share")
            continue
        kinds = [json.loads(line)["result"]["failure_kind"] for line in items.read_text(encoding="utf-8").splitlines()]
        share = Fraction(kinds.count("model_refusal"), len(kinds)) if kinds else Fraction(0)
        shares[run["run_id"]] = share
        print(f"  refusals: {kinds.count('model_refusal')} of {len(kinds)} items = {float(share):.2%}")
        if share > REFUSAL_CHECKPOINT:
            print("  REFUSAL CHECKPOINT: more than 2% of items refused. If this is run 1, stop and decide before "
                  "runs 2 and 3 (DEC-T07-REFUSALS).")
    return shares


def main(config, out, rerun_cause=None, repo=REPO, ask=input, run=launch):
    """Check, confirm, run. Returns the exit code: 2 when refused, otherwise the harness's own."""
    try:
        check_clean(repo, out)
        config_path = Path(config).resolve()
        run_config = _read(config_path, "run configuration")
        if not isinstance(run_config, dict):
            raise Refused("the run configuration is not a JSON object")
        model_config = _read(config_path.parent.joinpath(str(run_config.get("model_config"))), "model configuration")
        if not isinstance(model_config, dict):
            raise Refused("the model configuration is not a JSON object")
        check_inputs(model_config, out, rerun_cause)
        check_settings(run_config, model_config)
        times = _read(config_path.parent.joinpath(str(run_config.get("modelled_time"))), "modelled-time file")
        check_times(times)
        table = _read(config_path.parent.joinpath(str(run_config.get("price_table"))), "price table")
        check_prices(table, model_config["model"])
        check_key(model_config)
        try:
            loaded = load_config(config_path)  # everything else the harness itself would refuse
        except ValueError as problem:
            raise Refused(f"the harness refuses the configuration: {problem}") from None
        calls, size, cost = expected_cost(loaded["world"], table, model_config["model"], model_config["max_tokens"],
                                          run_config["agent"])
        hold = cost * CREDIT_MARGIN
        print(f"expected run cost, upper bound: {money.amount(cost, places=4)['decimal']} {table['currency']} "
              f"({calls} calls, {size} prompt bytes counted as tokens, every answer at {model_config['max_tokens']} "
              f"tokens, retries not counted)")
        answer = ask(f'Type "yes" once the Console shows a credit of at least '
                     f'{money.amount(hold, places=4)["decimal"]} {table["currency"]} (1.5 times that): ')
        if answer.strip() != "yes":
            raise Refused("the credit was not confirmed")
    except Refused as problem:
        print(f"REFUSED: {problem}")
        return 2
    command = [str(REPO.joinpath("tools", "timed_run.sh")), sys.executable, "-m", "harness", "run-and-score",
               str(config_path), str(out)] + (["--rerun-cause", rerun_cause] if rerun_cause is not None else [])
    before = {one["run_id"] for one in records.read_index(out)["runs"]}
    code = run(command, {**os.environ, **ENV})
    after(out, before)
    return code
