"""Test-only: a fake model and an in-process agent for the harness tests (DEC-T06-FAKE-MODEL). Not shipped.

The fake reads only the prompt it is sent. What it answers, and which IDs it cites, depends on the sorted set
of evidence IDs in the prompt and, for the outcome "by_first" only, on which ID is presented first, so that some alerts get different
verdicts in different framings. It never depends on call order and it holds no state, so a fault repeats on
every retry of the same item.
"""
import copy
import hashlib
import json
import time
from dataclasses import asdict

from baseline_agent import agent
from baseline_agent.payload import build_payload
from harness import run as harness_run
from harness.run import AGENTS, RETRIES
from model_interface import BadReply, ModelRefusal, ModelTimeout, ProviderError, Result, providers

MODEL_ID = "fake-1"
UNKNOWN_ID = "EVD-UNKNOWN"
FAULTS = {"timeout": ModelTimeout, "provider_error": ProviderError, "refusal": ModelRefusal, "empty": BadReply}

# (outcome, how many of 100 buckets). The bucket of a bundle comes from a hash of its sorted evidence IDs.
SHARES = (("close", 50), ("escalate", 24), ("by_first", 8), ("escalate_unknown_id", 2), ("close_unknown_id", 2),
          ("not_json", 2), ("no_citations", 2), ("wrong_version", 2), ("timeout", 2), ("provider_error", 2),
          ("refusal", 2), ("empty", 2))
BUCKETS = [name for name, share in SHARES for _ in range(share)]
assert len(BUCKETS) == 100


def evidence_ids(request):
    """The evidence IDs in the user message, in the order presented."""
    block = request.messages[-1].content.split("<evidence>\n", 1)[1].rsplit("\n</evidence>", 1)[0]
    return [json.loads(line)["id"] for line in block.split("\n")]


def key_of(ids):
    return tuple(sorted(ids))


def _number(ids):
    return int(hashlib.sha256("|".join(key_of(ids)).encode("utf-8")).hexdigest(), 16)


def outcome_of(ids):
    """The outcome for a bundle with these evidence IDs, whatever their order."""
    return BUCKETS[_number(ids) % 100]


def cited_of(ids):
    """The two evidence IDs a plain CLOSE or ESCALATE cites: picked by the same hash, so sometimes an ID of the
    supporting evidence key and sometimes not, and sometimes the same ID twice."""
    key, number = key_of(ids), _number(ids)
    return [key[number // 100 % len(key)], key[number // 10_000 % len(key)]]


def reply_text(ids):
    """The reply text for a bundle presented with `ids` in this order. Not defined for the four model faults."""
    lowest, outcome = key_of(ids)[0], outcome_of(ids)
    reply = {"schema_version": "1", "recommendation": "ESCALATE", "reason": f"fake {outcome}", "cited_ids": cited_of(ids)}
    if outcome == "close":
        reply["recommendation"] = "CLOSE"
    elif outcome == "by_first":  # the one outcome that looks at the order
        reply["recommendation"] = "CLOSE" if ids[0] == lowest else "ESCALATE"
        reply["cited_ids"] = [ids[0]]
    elif outcome == "escalate_unknown_id":
        reply["cited_ids"] = [lowest, UNKNOWN_ID]
    elif outcome == "close_unknown_id":
        reply.update(recommendation="CLOSE", cited_ids=[UNKNOWN_ID])
    elif outcome == "not_json":
        return "I would rather not answer in JSON."
    elif outcome == "no_citations":
        reply["cited_ids"] = []
    elif outcome == "wrong_version":
        reply["schema_version"] = "2"
    return json.dumps(reply)


class Fake:
    """The fake model. With `tokens` false it reports no token counts, as the T04 stub does."""

    def __init__(self, tokens=True):
        self._tokens = tokens

    def __call__(self, request):
        ids = evidence_ids(request)
        outcome = outcome_of(ids)
        if outcome in FAULTS:
            raise FAULTS[outcome](f"fake scripted failure: {outcome}")
        text = reply_text(ids)
        counts = (len(request.messages[-1].content), len(text)) if self._tokens else (None, None)
        return Result(text=text, model_id=MODEL_ID, input_tokens=counts[0], output_tokens=counts[1], latency_s=0.0)


class FailsOnce:
    """A second test double: the first call for a bundle raises a provider error, the next one answers as the
    fake does. It keeps a note of the bundles it has seen, so use a new one for every test. It is for bundles
    the fake answers; a bundle scripted to fail keeps failing."""

    def __init__(self):
        self._fake, self._seen = Fake(), set()

    def __call__(self, request):
        key = key_of(evidence_ids(request))
        if key not in self._seen:
            self._seen.add(key)
            raise ProviderError("fails once: the first attempt")
        return self._fake(request)


class Slow:
    """A third test double: the fake, after a pause. For the tests that need calls to be in flight."""

    def __init__(self, delay=1.0):
        self._fake, self._delay = Fake(), delay

    def __call__(self, request):
        time.sleep(self._delay)
        return self._fake(request)


def inprocess(items, model, settings, item_id):
    """The baseline agent's own code, called in this process with no child. For tests only: it is registered as
    an agent by `register`, and nothing in the shipped harness can select it."""
    job = {"payload": build_payload(items), "settings": asdict(settings), "retries": RETRIES}
    result = json.loads(json.dumps(agent.main(model, json.loads(json.dumps(job)))))  # as the pipe would carry it
    result["log"]["correlation_id"] = item_id
    return result, [copy.deepcopy(result["log"])]


def register(patch):
    """Make the provider "fake" and the agent "inprocess" selectable, through a pytest MonkeyPatch."""
    patch.setitem(providers.PROVIDERS, "fake", Fake)
    patch.setitem(providers.PROVIDERS, "slow", Slow)
    patch.setattr(harness_run, "NOT_REAL", harness_run.NOT_REAL | {"fake", "slow"})  # no real providers either
    patch.setitem(AGENTS, "inprocess", inprocess)
