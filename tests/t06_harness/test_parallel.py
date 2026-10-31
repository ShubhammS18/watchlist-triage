"""T06 stage 4: the worker pool, the pacer and clean shutdown (DEC-T06-PARALLEL).

The five safeguards: a parallel run equals a sequential one, on replies and on fault choices; nothing is shared
between calls, shown by one-token calls that must sum exactly; output is sorted; the pacer, with a fake clock;
and an interrupted run is aborted and leaves no child process behind.
"""
import copy
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import pytest

import fake_model
from conftest import FIXTURES, write_config
from framings import FRAMINGS, frame
from harness import run as harness_run
from model_interface import Result, Settings, providers
from worldgen.loader import load_alerts

REPO = Path(__file__).resolve().parents[2]
SETTINGS = Settings("fake-1", 0, 512, 30)
STRESS_WORKERS, STRESS_ITEMS = 8, 1000  # sized for a 3.5 GiB machine: a breakage that shares one token wrapper
#                                         makes every item keep all attempts so far, which grows with ITEMS squared


def without_timings(line):
    line = copy.deepcopy(line)
    del line["wall_s"], line["queue_s"]
    line["result"]["log"]["latency_s"] = None
    for attempt in line["result"]["log"]["attempt_log"]:
        attempt["latency_s"] = None
    return line


def lines_of(out, manifest):
    text = Path(out).joinpath(manifest["run_id"], "items.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]


# ---- safeguard 1 and 3: parallel equals sequential, and the output is sorted

def test_a_parallel_run_of_the_whole_world_equals_the_sequential_one(full_run, tmp_path):
    _, sequential, sequential_lines = full_run
    parallel = harness_run.run(write_config(tmp_path, workers=8), tmp_path.joinpath("out"))
    parallel_lines = lines_of(tmp_path.joinpath("out"), parallel)
    assert sequential["workers"] == 1 and parallel["workers"] == 8 and parallel["state"] == "completed"
    assert [line["item_id"] for line in parallel_lines] == sorted(line["item_id"] for line in parallel_lines)
    assert [without_timings(line) for line in parallel_lines] == [without_timings(line) for line in sequential_lines]
    kinds = {line["result"]["failure_kind"] for line in parallel_lines}
    assert {None, "timeout", "provider_error", "model_refusal", "malformed_output", "missing_citations",
            "unknown_schema_version", "invalid_citation"} == kinds  # replies and every fault choice of the fake
    assert parallel["calls"] == sequential["calls"] and parallel["cost"] == sequential["cost"]
    assert parallel["infra_invalid"] == sequential["infra_invalid"]
    assert parallel["run_set"] != sequential["run_set"]  # the worker count is a run-set input


def test_parallel_real_children_equal_the_sequential_in_process_path():
    chosen = {}
    for alert in load_alerts():
        chosen.setdefault(fake_model.outcome_of([item["id"] for item in alert["evidence"]]), alert)
    items = [{"item_id": f"{alert['id']}/{framing}", "alert_id": alert["id"], "framing": framing, "twin": False,
              "evidence": frame(alert, framing)} for alert in chosen.values() for framing in FRAMINGS]
    model, settings = providers.load(FIXTURES.joinpath("model_fake.json"))
    child, inside = [], []
    harness_run.hand_off(items, harness_run.AGENTS["baseline"], model, settings, child, workers=4)
    harness_run.hand_off(items, fake_model.inprocess, model, settings, inside)
    assert len(child) == 36 == len(inside)
    by_id = lambda lines: sorted((without_timings(line) for line in lines), key=lambda line: line["item_id"])
    assert by_id(child) == by_id(inside)


# ---- safeguard 2: nothing is shared

class OneToken:
    """Every call reports exactly one input token and one output token."""

    def __call__(self, request):
        return Result("text", "one-token", 1, 1, 0.0)


def calling(times_for):
    """A test agent that calls the model a number of times that depends on the item, and nothing else."""
    def agent(items, model, settings, item_id):
        for _ in range(times_for(item_id)):
            model(item_id)
        log = {"item": item_id}
        return {"failure_kind": None, "log": log}, [dict(log)]
    return agent


def test_one_token_calls_sum_exactly_under_the_stress_workers():
    count = STRESS_ITEMS
    items = [{"item_id": f"I-{number:05d}", "alert_id": f"I-{number:05d}", "framing": 1, "twin": False,
              "evidence": [{"id": f"E-{number:05d}"}]} for number in range(count)]
    times_for = lambda item_id: 1 + int(item_id[2:]) % 5
    done = []
    harness_run.hand_off(items, calling(times_for), OneToken(), SETTINGS, done, workers=STRESS_WORKERS)
    assert len(done) == count and {line["item_id"] for line in done} == {item["item_id"] for item in items}
    for line in done:  # every item has its own calls and its own log, and nobody else's
        assert len(line["attempts"]) == times_for(line["item_id"]) and line["result"]["log"] == {"item": line["item_id"]}
        assert line["sent_ids"] == [f"E-{line['item_id'][2:]}"]
        assert all(one == {"error": None, "input_tokens": 1, "output_tokens": 1, "model_id": "one-token",
                           "prompt_bytes": None} for one in line["attempts"])  # prompt_bytes: W2-02; no messages here
    expected = sum(times_for(item["item_id"]) for item in items)
    assert expected == 3 * STRESS_ITEMS
    assert harness_run._calls([one for line in done for one in line["attempts"]]) == {
        "attempts": expected, "without_token_counts": 0, "input_tokens": expected, "output_tokens": expected}


def test_calls_really_run_side_by_side_and_never_more_than_the_worker_count():
    running, most, lock = 0, 0, threading.Lock()

    def agent(items, model, settings, item_id):
        nonlocal running, most
        with lock:
            running += 1
            most = max(most, running)
        time.sleep(0.02)
        with lock:
            running -= 1
        log = {"item": item_id}
        return {"failure_kind": None, "log": log}, [dict(log)]

    items = [{"item_id": str(number), "alert_id": str(number), "framing": 1, "twin": False, "evidence": [{"id": "E"}]}
             for number in range(40)]
    done = []
    harness_run.hand_off(items, agent, None, SETTINGS, done, workers=4)
    assert len(done) == 40 and most == 4
    one_by_one = []
    most = 0
    harness_run.hand_off(items[:5], agent, None, SETTINGS, one_by_one)
    assert most == 1 and [line["item_id"] for line in one_by_one] == ["0", "1", "2", "3", "4"]  # one worker keeps the order


# ---- safeguard 4: the pacer

class FakeClock:
    def __init__(self):
        self.now, self.waits = 0.0, []

    def clock(self):
        return self.now

    def wait(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


def instant(items, model, settings, item_id):
    log = {"item": item_id}
    return {"failure_kind": None, "log": log}, [dict(log)]


def few(count):
    return [{"item_id": str(number), "alert_id": str(number), "framing": 1, "twin": False, "evidence": [{"id": "E"}]}
            for number in range(count)]


@pytest.mark.parametrize("workers", [1, 3])  # the sequential path and the pool
def test_the_pacer_spaces_the_hand_offs_evenly_on_a_fake_clock(workers):
    fake, done = FakeClock(), []
    harness_run.hand_off(few(6), instant, None, SETTINGS, done, workers=workers, pacer_per_minute=30,
                         clock=fake.clock, wait=fake.wait)
    assert fake.waits == [2.0] * 5 and fake.now == 10.0  # 30 a minute is one every 2 seconds; the first goes at once
    assert sorted(line["queue_s"] for line in done) == [0.0, 2.0, 2.0, 2.0, 2.0, 2.0]  # the wait is queue time
    assert all(line["wall_s"] < 1.0 for line in done)  # and no part of the item's own time


def test_the_pacer_waits_only_for_what_is_left_of_the_interval():
    fake, done = FakeClock(), []

    def slow(items, model, settings, item_id):
        fake.now += 0.5  # the call itself takes half a second of the fake clock
        return instant(items, model, settings, item_id)

    harness_run.hand_off(few(4), slow, None, SETTINGS, done, pacer_per_minute=60, clock=fake.clock, wait=fake.wait)
    assert fake.waits == [0.5, 0.5, 0.5]  # one a second, and half of each second was already spent in the call

    fake, done = FakeClock(), []

    def slower(items, model, settings, item_id):
        fake.now += 3.0
        return instant(items, model, settings, item_id)

    harness_run.hand_off(few(4), slower, None, SETTINGS, done, pacer_per_minute=60, clock=fake.clock, wait=fake.wait)
    assert fake.waits == []  # calls slower than the interval are never held back


@pytest.mark.parametrize("workers", [1, 3])
def test_the_pacer_is_off_by_default(workers):
    fake, done = FakeClock(), []
    harness_run.hand_off(few(6), instant, None, SETTINGS, done, workers=workers, clock=fake.clock, wait=fake.wait)
    assert fake.waits == [] and [line["queue_s"] for line in done] == [0.0] * 6
    config = harness_run.load_config(FIXTURES.joinpath("run.json"))
    assert config["pacer_per_minute"] is None and config["workers"] == 1


@pytest.mark.parametrize("changes", [{"workers": 1}, {"workers": 8}, {"workers": 64}, {"pacer_per_minute": 1},
                                     {"pacer_per_minute": 600}, {"workers": 4, "pacer_per_minute": 120}])
def test_worker_counts_and_pacer_settings_are_accepted_and_recorded(tmp_path, changes):
    config = harness_run.load_config(write_config(tmp_path, **changes))
    assert {key: config[key] for key in changes} == changes


def test_the_manifest_records_workers_pacer_and_the_runs_timing(tmp_path, monkeypatch):
    waited, passed, real = [], {}, harness_run.hand_off

    def watching(*args, **settings):  # the real hand-off, with a wait that only notes what it was asked to wait
        passed.update(settings)
        return real(*args, **settings, wait=waited.append)

    monkeypatch.setattr(harness_run, "hand_off", watching)
    manifest = harness_run.run(write_config(tmp_path, workers=2, pacer_per_minute=6000), tmp_path.joinpath("out"))
    assert passed == {"workers": 2, "pacer_per_minute": 6000}  # the configuration reaches the hand-off
    assert manifest["state"] == "completed" and manifest["workers"] == 2 and manifest["pacer_per_minute"] == 6000
    assert manifest["run_set_inputs"]["workers"] == 2 and manifest["run_set_inputs"]["pacer_per_minute"] == 6000
    assert waited and all(0 < seconds <= 0.01 for seconds in waited)  # one every hundredth of a second at most
    lines = lines_of(tmp_path.joinpath("out"), manifest)
    assert manifest["timing"]["duration_s"] > 0
    assert abs(manifest["timing"]["queue_s"] - sum(line["queue_s"] for line in lines)) < 1e-6


# ---- safeguard 5: a fault or an interrupt stops the hand-offs and waits for the calls in flight

def test_a_fault_that_comes_back_during_the_pacer_wait_stops_the_next_hand_off(monkeypatch):
    """Two workers and a pacer on a fake clock. Item 0 is handed off at once; the pacer then holds item 1 back, and
    during that wait item 0 fails and its result is in. Item 1 must not start, and the run is aborted."""
    started, go, failure_in = [], threading.Event(), threading.Event()

    class Watched(queue.SimpleQueue):  # tells the test when a result is in
        def put(self, outcome):
            super().put(outcome)
            failure_in.set()

    monkeypatch.setattr(harness_run, "queue", types.SimpleNamespace(SimpleQueue=Watched))
    fake = FakeClock()

    def wait(seconds):  # the pacer's wait before item 1: item 0 fails now, and its result comes back
        fake.wait(seconds)
        go.set()
        assert failure_in.wait(5)

    def agent(items, model, settings, item_id):
        started.append(item_id)
        assert go.wait(5)
        raise RuntimeError("boom during the pacer wait")

    done = []
    with pytest.raises(harness_run.HarnessFault) as caught:
        harness_run.hand_off(few(5), agent, None, SETTINGS, done, workers=2, pacer_per_minute=30,
                             clock=fake.clock, wait=wait)
    assert caught.value.item_id == "0" and str(caught.value.cause) == "boom during the pacer wait"
    assert started == ["0"] and done == [] and fake.waits == [2.0]  # no item was handed off after the pacer wait

def test_after_a_fault_nothing_more_is_handed_off_and_the_calls_in_flight_are_waited_for():
    """Items 0 to 9 answer at once. Item 10 fails, but only once the three other workers each hold a later item,
    and every later item blocks until the gate opens. So exactly three calls are in flight when the fault comes
    back, and the order of events does not depend on timing."""
    started, finished, lock, gate, returned = [], [], threading.Lock(), threading.Event(), threading.Event()
    three_in_flight = threading.Event()

    def agent(items, model, settings, item_id):
        with lock:
            started.append(item_id)
            if sum(int(one) > 10 for one in started) == 3:
                three_in_flight.set()
        model(item_id)
        if item_id == "10":
            assert three_in_flight.wait(10)
            raise RuntimeError("boom at ten")
        if int(item_id) > 10:
            gate.wait()
            assert not returned.is_set()  # the hand-off is still waiting for this call
        with lock:
            finished.append(item_id)
        return instant(items, model, settings, item_id)

    done = []
    threading.Timer(0.3, gate.set).start()  # the calls in flight are let go only later
    begun = time.monotonic()
    with pytest.raises(harness_run.HarnessFault) as caught:
        harness_run.hand_off(few(200), agent, OneToken(), SETTINGS, done, workers=4)
    returned.set()
    assert time.monotonic() - begun >= 0.25  # it did wait for the calls in flight
    assert caught.value.item_id == "10" and str(caught.value.cause) == "boom at ten"
    assert caught.value.attempts == [{"error": None, "input_tokens": 1, "output_tokens": 1, "model_id": "one-token",
                                      "prompt_bytes": None}]  # prompt_bytes: W2-02; no messages here
    assert sorted(started, key=int) == [str(number) for number in range(14)]  # the ten before it, itself, and
    #                                                                          the three other workers' calls
    assert sorted(finished + ["10"]) == sorted(started)  # every call that was started was waited for
    assert sorted(line["item_id"] for line in done) == sorted(finished)
    time.sleep(0.1)
    assert len(started) == 14  # and nothing was started later


def test_a_fault_in_a_parallel_run_aborts_it_and_counts_what_the_calls_in_flight_cost(tmp_path, monkeypatch):
    def breaking(items, model, settings, item_id):
        result, sink = fake_model.inprocess(items, model, settings, item_id)
        if item_id == "ALT-0005/2":
            raise RuntimeError("boom in a worker")
        return result, sink

    monkeypatch.setitem(harness_run.AGENTS, "breaking", breaking)
    manifest = harness_run.run(write_config(tmp_path, agent="breaking", workers=4), tmp_path.joinpath("out"))
    assert manifest["state"] == "aborted" and manifest["outputs"] is None
    assert manifest["aborted"] == {"item_id": "ALT-0005/2", "error_type": "RuntimeError", "message": "boom in a worker"}
    # the 13 items before it, and the few handed off while it was still running; the exact bound is shown by
    # the test above, where the order of events is certain
    assert 13 <= manifest["items"]["total"] < 100
    assert manifest["calls"]["attempts"] > manifest["items"]["total"] and manifest["cost"]["attempts"] == manifest["calls"]["attempts"]
    assert sorted(path.name for path in tmp_path.joinpath("out", manifest["run_id"]).iterdir()) == [
        "audit.jsonl", "checkpoint.json", "manifest.json"]  # no items.jsonl; the log is kept (W2-05)


INTERRUPTED = {"item_id": None, "error_type": "KeyboardInterrupt", "message": "the run was interrupted"}


@pytest.mark.parametrize("workers", [1, 2])  # the sequential path and the pool
def test_a_keyboard_interrupt_is_a_clean_abort(tmp_path, monkeypatch, workers):
    def interrupting(items, model, settings, item_id):
        result = fake_model.inprocess(items, model, settings, item_id)
        if item_id == "ALT-0002/1":
            signal.raise_signal(signal.SIGINT)  # as Ctrl-C would, after this item's model call was made
            time.sleep(0.05)
        return result

    monkeypatch.setitem(harness_run.AGENTS, "interrupting", interrupting)
    manifest = harness_run.run(write_config(tmp_path, agent="interrupting", workers=workers), tmp_path.joinpath("out"))
    assert manifest["state"] == "aborted" and manifest["outputs"] is None
    assert manifest["aborted"] == INTERRUPTED
    assert manifest["items"]["total"] < 20  # it stopped near the start; the calls in flight were waited for
    if workers == 1:  # the interrupt cut that item short: it has no line, but its model call is counted
        assert manifest["calls"]["attempts"] > manifest["items"]["total"] == 3
    else:  # with a pool the calls in flight were waited for and finished
        assert manifest["calls"]["attempts"] >= manifest["items"]["total"] >= 3
    entry, = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["state"] == "aborted" and entry["cause"] == "KeyboardInterrupt: the run was interrupted"


def test_ctrl_c_before_the_first_hand_off_marks_the_listed_run_aborted(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setitem(harness_run.AGENTS, "counting", lambda *args: calls.append(args))

    def interrupted_check(world, listed, hidden=False):
        index = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))
        assert [run["state"] for run in index["runs"]] == ["started"]  # the run is already listed
        raise KeyboardInterrupt

    monkeypatch.setattr(harness_run, "check_world", interrupted_check)
    manifest = harness_run.run(write_config(tmp_path, agent="counting"), tmp_path.joinpath("out"))
    assert calls == [] and manifest["state"] == "aborted" and manifest["aborted"] == INTERRUPTED
    assert manifest["items"]["total"] == 0 and manifest["calls"]["attempts"] == 0
    entry, = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["state"] == "aborted" and entry["cause"] == "KeyboardInterrupt: the run was interrupted"


def test_one_worker_makes_its_calls_in_this_thread_and_more_workers_do_not():
    threads = []

    def noting(items, model, settings, item_id):
        threads.append(threading.current_thread())
        return instant(items, model, settings, item_id)

    harness_run.hand_off(few(5), noting, None, SETTINGS, [])
    assert set(threads) == {threading.current_thread()}  # the sequential path: no pool at all
    threads.clear()
    harness_run.hand_off(few(5), noting, None, SETTINGS, [], workers=2)
    assert threading.current_thread() not in threads


# ---- no orphan process

INTERRUPTED_RUN = """
import json, sys
sys.path.insert(0, sys.argv[1])
import pytest, fake_model, conftest
from harness import run
with pytest.MonkeyPatch.context() as patch:
    fake_model.register(patch)
    config = conftest.write_config(sys.argv[2], agent="baseline", model_config=sys.argv[2] + "/slow.json",
                                   workers=int(sys.argv[3]))
    manifest = run.run(config, sys.argv[2] + "/out")
print(json.dumps({"state": manifest["state"], "aborted": manifest["aborted"]}))
"""


def session_members(session, running=None):
    """The processes of one session, from /proc: the run and everything it started. With `running`, only those
    whose command line holds that text."""
    members = []
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                fields = Path("/proc", entry, "stat").read_text().rsplit(")", 1)[1].split()
                command = Path("/proc", entry, "cmdline").read_text()
            except OSError:
                continue  # it ended while we were looking
            if int(fields[3]) == session and fields[0] != "Z" and (running is None or running in command):
                members.append(int(entry))
    return members


def wait_for(condition, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="no /proc here: the orphan-process check needs it, "
                    "so clean shutdown of the agent processes is not shown on this system")
@pytest.mark.parametrize("workers, target, times, expected", [
    (2, "group", 1, "aborted"),    # Ctrl-C in a terminal: the run and its agent processes all get the signal
    (2, "parent", 1, "aborted"),   # the run alone gets it: the agent processes are waited for, then ended
    (2, "parent", 2, "aborted"),   # a second Ctrl-C during that wait: the wait is given up, the run still marked
    (1, "group", 1, "aborted"),    # the sequential path: the call in flight is cut short and its agent process ended
    (1, "parent", 1, "aborted"),
])
def test_an_interrupted_run_through_the_real_child_leaves_no_process_behind(tmp_path, workers, target, times, expected):
    tmp_path.joinpath("slow.json").write_text(json.dumps({
        "provider": "slow", "model": "fake-1", "temperature": 0, "max_tokens": 512, "timeout_s": 30,
        "options": {"delay": 1.0}}), encoding="utf-8")
    run = subprocess.Popen([sys.executable, "-B", "-c", INTERRUPTED_RUN, str(Path(__file__).resolve().parent), str(tmp_path),
                            str(workers)],
                           cwd=REPO, env={**os.environ, "PYTHONPATH": str(REPO)}, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        # wait until an agent process is running. A git command the run starts first is also a child, so the
        # check is for the agent's own start-up script, which only exists once calls are being handed off.
        assert wait_for(lambda: session_members(run.pid, running="child.py"), 10), "no agent process was started"
        for number in range(times):
            if number:
                time.sleep(0.3)
            os.killpg(run.pid, signal.SIGINT) if target == "group" else os.kill(run.pid, signal.SIGINT)
        output, errors = run.communicate(timeout=20)
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
    assert wait_for(lambda: session_members(run.pid) == [], 3), f"left behind: {session_members(run.pid)}"
    entry, = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["state"] == expected
    assert run.returncode == 0, errors
    assert json.loads(output) == {"state": "aborted", "aborted": INTERRUPTED}
    assert not tmp_path.joinpath("out", entry["run_id"], "items.jsonl").exists()
    assert tmp_path.joinpath("out", entry["run_id"], "manifest.json").exists()
