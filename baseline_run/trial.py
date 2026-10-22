"""The trial (DEC-T07-TRIAL): the baseline agent with the real adapter on the hand-written alerts in
trial/alerts.json, none of them from the frozen world. It writes trial-results.json to a folder outside the
repository and prints one line per model call and the pre-declared verdicts (DEC-T07-RUN-SETTINGS-2,
DEC-T07-REFUSALS, DEC-T07-PRICES):

    p99 latency over 10 s          revisit timeout_s before the run commit
    largest answer over 256 output tokens, or any answer at the max_tokens cap
                                   raise max_tokens to 1,024 before the run commit
    any refusal                    stop and decide before the run commit
    a reported model ID other than the requested one
                                   the price table key is not confirmed

The API key comes from WT_ANTHROPIC_API_KEY, read by the adapter. stop_reason is derived, not reported: the
adapter keeps no stop_reason, and with no tools and no stop sequences a call that returned ended on a refusal
(its own error), on the max_tokens cap (output tokens equal to the cap; an answer that happened to end at exactly
512 tokens would look the same) or at the end of its turn.
"""
import json
import math
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from baseline_agent.recommend import recommend
from harness import manifest as records
from harness.run import RETRIES, Tokens
from model_interface import providers

REPO = records.REPO
ALERTS = REPO.joinpath("trial", "alerts.json")
MODEL_CONFIG = REPO.joinpath("trial", "model.json")
# Claude Haiku 5.5, USD per million tokens up to 100k prompt tokens: platform.claude.com/docs/en/about-claude/pricing,
# read 17 and 19 Oct 2026. Only for the trial's own spend; the runs use the committed price table.
PRICE_IN, PRICE_OUT = Fraction(Decimal("0.10")), Fraction(Decimal("0.50"))
LATENCY_LIMIT_S, ANSWER_LIMIT = 10, 256


def stop_reason(attempt, max_tokens):
    """The derived stop_reason of one call, or None for a call that raised another error."""
    if attempt["error"] == "ModelRefusal":
        return "refusal"
    if attempt["error"] is not None:
        return None
    return "max_tokens" if attempt["output_tokens"] == max_tokens else "end_turn"


def p99(values):
    """Nearest-rank 99th percentile."""
    ordered = sorted(values)
    return ordered[math.ceil(0.99 * len(ordered)) - 1]


def call_rows(alert, result, attempts, max_tokens):
    """One row per model call of one alert. The alert's own outcome is on its last call."""
    entries = result["log"]["attempt_log"]
    rows = []
    for number, attempt in enumerate(attempts, 1):
        last = number == len(attempts)
        counted = attempt["input_tokens"] is not None and attempt["output_tokens"] is not None
        cost = (attempt["input_tokens"] * PRICE_IN + attempt["output_tokens"] * PRICE_OUT) / 1_000_000 if counted else None
        rows.append({
            "alert_id": alert["id"], "call": number, "expected_action": alert["expected_action"],
            "valid_json": (result["failure_kind"] != "malformed_output") if last and attempt["error"] is None else None,
            "recommendation": result["recommendation"] if last else None,
            "failure_kind": result["failure_kind"] if last else None,
            "model_id": attempt["model_id"], "error": attempt["error"],
            "stop_reason_derived": stop_reason(attempt, max_tokens),
            "latency_s": entries[number - 1]["latency_s"] if number <= len(entries) else None,
            "input_tokens": attempt["input_tokens"], "output_tokens": attempt["output_tokens"],
            "cost_usd": str(Decimal(cost.numerator) / Decimal(cost.denominator)) if cost is not None else None})
    return rows


def verdicts(rows, settings):
    returned = [row for row in rows if row["error"] is None]
    latencies = [row["latency_s"] for row in rows if row["latency_s"] is not None]
    outputs = [row["output_tokens"] for row in returned if row["output_tokens"] is not None]
    refusals = sum(1 for row in rows if row["stop_reason_derived"] == "refusal")
    ids = sorted({str(row["model_id"]) for row in returned})
    largest = max(outputs) if outputs else None
    return {
        "p99_latency_s": {"value": p99(latencies) if latencies else None, "limit_s": LATENCY_LIMIT_S,
                          "pass": bool(latencies) and p99(latencies) <= LATENCY_LIMIT_S},
        "largest_output_tokens": {"value": largest, "limit": ANSWER_LIMIT, "cap": settings.max_tokens,
                                  "pass": largest is not None and largest <= ANSWER_LIMIT and largest < settings.max_tokens},
        "refusals": {"value": refusals, "pass": refusals == 0},
        "model_ids": {"value": ids, "expected": settings.model,
                      "pass": bool(returned) and ids == [settings.model]},
    }


def trial(out, model_config=MODEL_CONFIG, alerts=ALERTS):
    out = Path(out).resolve()
    if out.is_relative_to(REPO):
        raise ValueError(f"the trial output must lie outside the repository, not {str(out)!r}")
    model, settings = providers.load(model_config)
    rows = []
    for alert in json.loads(Path(alerts).read_text(encoding="utf-8")):
        tokens = Tokens(model)
        result = recommend(alert["evidence"], tokens, settings, retries=RETRIES, correlation_id=alert["id"])
        rows += call_rows(alert, result, tokens.snapshot(), settings.max_tokens)
    known = [Fraction(Decimal(row["cost_usd"])) for row in rows if row["cost_usd"] is not None]
    results = {"model": settings.model, "max_tokens": settings.max_tokens, "rows": rows,
               "total_cost_usd": str(float(sum(known))), "calls_without_cost": len(rows) - len(known),
               "verdicts": verdicts(rows, settings)}
    out.mkdir(parents=True, exist_ok=True)
    records.write_json(out.joinpath("trial-results.json"), results)
    return results


def show(results):
    print("alert      call valid  rec       model_id          stop_reason(derived)  latency_s  in    out   cost_usd")
    for row in results["rows"]:
        latency = f"{row['latency_s']:.2f}" if row["latency_s"] is not None else "-"
        print(f"{row['alert_id']:<10} {row['call']:<4} {str(row['valid_json']):<6} {str(row['recommendation']):<9} "
              f"{str(row['model_id']):<17} {str(row['stop_reason_derived'] or row['error']):<21} {latency:<10} "
              f"{str(row['input_tokens']):<5} {str(row['output_tokens']):<5} {row['cost_usd']}")
    print(f"total known cost: {results['total_cost_usd']} USD; calls without a cost: {results['calls_without_cost']}")
    v = results["verdicts"]
    print(f"p99 latency {v['p99_latency_s']['value']} s vs 10 s: "
          f"{'PASS' if v['p99_latency_s']['pass'] else 'FAIL, revisit timeout_s'}")
    print(f"largest answer {v['largest_output_tokens']['value']} output tokens vs 256 and the "
          f"{v['largest_output_tokens']['cap']} cap: "
          f"{'PASS' if v['largest_output_tokens']['pass'] else 'FAIL, raise max_tokens to 1,024'}")
    print(f"refusals {v['refusals']['value']}: {'PASS' if v['refusals']['pass'] else 'STOP, decide before the run commit'}")
    print(f"reported model IDs {v['model_ids']['value']} vs the price table key {v['model_ids']['expected']!r}: "
          f"{'PASS' if v['model_ids']['pass'] else 'FAIL'}")
    return 0 if all(one["pass"] for one in v.values()) else 1
