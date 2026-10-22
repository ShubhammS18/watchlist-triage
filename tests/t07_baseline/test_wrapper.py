"""T07: the run wrapper (DEC-T07-WRAPPER, DEC-T07-WRAPPER-CHECKS). Each refusal reason, and the path to the run,
with the fake API on this machine. No harness run is started: the step that would run tools/timed_run.sh is
replaced by a recorder."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from baseline_run import wrapper
from harness.manifest import REPO
from model_interface.anthropic_api import KEY_VARIABLE

from fake_api import CANARY, answer, other_server, server  # noqa: F401  (server and other_server are fixtures)

MODEL = "claude-haiku-5-5"
TIMES = {"LOW": ("3", "0.5", "40", "1"), "BASE": ("8", "2", "120", "2"), "HIGH": ("30", "5", "480", "5")}
PARAMETERS = ("manual_clearing", "proposal_review", "l2", "second_review")


def times():
    return {"kind": "sourced", "unit": "minutes",
            "sets": {name: dict(zip(PARAMETERS, values)) for name, values in TIMES.items()},
            "sources": {name: dict.fromkeys(PARAMETERS, "a source") for name in TIMES}}


def prices():
    return {"kind": "sourced", "source": "platform.claude.com/docs/en/about-claude/pricing", "date": "2026-10-19",
            "currency": "USD", "unit": "per million tokens", "models": {MODEL: {"input": "0.10", "output": "0.50"}},
            "sources": {MODEL: {"input": "pricing page", "output": "pricing page"}}}


@pytest.fixture
def setup(tmp_path, server, monkeypatch):
    monkeypatch.setattr(wrapper, "KEY_CHECK_URL", server.url)  # the run config itself names no address
    repo = tmp_path.joinpath("repo")
    repo.mkdir()
    git = lambda *args: subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--no-verify", "--allow-empty",
        "-m", "clean")
    server.script = lambda handler, body: answer(handler, 200, {"input_tokens": 9})
    s = SimpleNamespace(
        repo=repo, out=tmp_path.joinpath("out"), config=tmp_path.joinpath("run.json"), server=server, ran=[],
        run={"agent": "baseline", "world": str(REPO.joinpath("data", "world")), "model_config": "model.json",
             "workers": 4, "pacer_per_minute": 120, "infra_invalid_threshold": "0.02", "price_table": "prices.json",
             "modelled_time": "times.json"},
        model={"provider": "anthropic", "model": MODEL, "temperature": 1, "max_tokens": 512, "timeout_s": 30,
               "options": {"thinking": "disabled"}},
        times=times(), prices=prices())
    return s


def go(s, rerun_cause=None, ask=lambda prompt: "yes"):
    for name, value in (("run.json", s.run), ("model.json", s.model), ("times.json", s.times),
                        ("prices.json", s.prices)):
        s.config.parent.joinpath(name).write_text(json.dumps(value), encoding="utf-8")

    def record(command, env):
        s.ran.append((command, env))
        return 0
    return wrapper.main(s.config, s.out, rerun_cause=rerun_cause, repo=s.repo, ask=ask, run=record)


def index_with(out, state, infra_invalid=None):
    out.mkdir(exist_ok=True)
    out.joinpath("index.json").write_text(json.dumps({"runs": [
        {"run_id": "r1", "run_set": "s" * 64, "state": state, "infra_invalid": infra_invalid,
         "started_at": "2026-10-20T10:00:00+00:00"}], "sets": {}}), encoding="utf-8")


def set_key(s, value):
    s.monkeypatch.setenv(KEY_VARIABLE, value) if value is not None else s.monkeypatch.delenv(KEY_VARIABLE)


# (what is wrong, how to make it so, words the refusal must contain, whether the key check may have been sent)
REFUSALS = [
    ("a.dirty", lambda s: s.repo.joinpath("new.txt").write_text("x"), "working tree is not clean", False),
    ("a.out in repo", lambda s: setattr(s, "out", REPO.joinpath("t07-out-test")), "outside the repository", False),
    ("b.blank cause", lambda s: setattr(s, "cause", "   "), "re-run cause is blank", False),
    ("b.space model", lambda s: s.model.update(model="   "), "only of spaces", False),
    ("b.nan temperature", lambda s: s.model.update(temperature=float("nan")), "temperature is not a finite", False),
    ("b.inf timeout", lambda s: s.model.update(timeout_s=float("inf")), "timeout_s is not a finite", False),
    ("b.cause needed, aborted", lambda s: index_with(s.out, "aborted"), "needs --rerun-cause", False),
    ("b.cause needed, unfinished", lambda s: index_with(s.out, "started"), "needs --rerun-cause", False),
    ("b.cause needed, infra-invalid", lambda s: index_with(s.out, "completed", True), "needs --rerun-cause", False),
    ("c.provider", lambda s: s.model.update(provider="stub"), "provider is 'stub'", False),
    ("c.temperature", lambda s: s.model.update(temperature=0), "temperature is 0", False),
    ("c.temperature flag", lambda s: s.model.update(temperature=True), "finite number: True", False),
    ("c.thinking", lambda s: s.model["options"].update(thinking="enabled"), "thinking is 'enabled'", False),
    ("c.max_tokens", lambda s: s.model.update(max_tokens=1024), "max_tokens is 1024", False),
    ("c.timeout", lambda s: s.model.update(timeout_s=60), "timeout_s is 60", False),
    ("c.workers", lambda s: s.run.update(workers=8), "workers is 8", False),
    ("c.pacer", lambda s: s.run.update(pacer_per_minute=None), "pacer_per_minute is None", False),
    ("c.threshold", lambda s: s.run.update(infra_invalid_threshold="0.05"), "infra_invalid_threshold is '0.05'", False),
    ("c.agent", lambda s: s.run.update(agent="always_close"), "agent is 'always_close'", False),
    ("c.base_url local", lambda s: s.model["options"].update(base_url=s.server.url),
     "base_url must be exactly https://api.anthropic.com (the default)", False),
    ("c.base_url other host", lambda s: s.model["options"].update(base_url="https://api.anthropic.com.example.invalid"),
     "base_url must be exactly https://api.anthropic.com (the default)", False),
    ("d.fixture", lambda s: s.times.update(kind="fixture") or s.times.pop("sources"), 'kind "sourced"', False),
    ("d.order", lambda s: s.times["sets"]["LOW"].update(l2="200"), "LOW <= BASE <= HIGH", False),
    ("d.zero", lambda s: s.times["sets"]["LOW"].update(proposal_review="0"), "above 0", False),
    ("d.shape", lambda s: s.times["sets"].pop("HIGH"), "the modelled-time file:", False),
    ("e.fixture", lambda s: s.prices.update(kind="fixture") or s.prices.pop("sources"), 'kind "sourced"', False),
    ("e.no entry", lambda s: s.model.update(model="claude-haiku-5-4"), "no entry for the configured model", False),
    ("f.key missing", lambda s: set_key(s, None), "the API key is missing", False),
    ("f.key malformed", lambda s: set_key(s, "sk-ant bad key"), "characters an API key cannot have", False),
    ("f.key rejected", lambda s: setattr(s.server, "script", lambda h, b: answer(h, 401, {})),
     "does not authenticate: HTTP 401", True),
    ("f.key check refused", lambda s: setattr(s.server, "script", lambda h, b: answer(h, 404, {})),
     "key check was refused: HTTP 404", True),
    ("harness refuses", lambda s: s.run.update(extra=1), "the harness refuses the configuration", True),
    ("credit not confirmed", lambda s: setattr(s, "answer", "y"), "the credit was not confirmed", True),
]


@pytest.mark.parametrize("name, make, words, network", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_each_refusal_names_its_reason_and_starts_nothing(setup, monkeypatch, capsys, name, make, words, network):
    setup.monkeypatch, setup.cause, setup.answer = monkeypatch, None, "yes"
    make(setup)
    code = go(setup, rerun_cause=setup.cause, ask=lambda prompt: setup.answer)
    printed = capsys.readouterr().out
    assert code == 2 and "REFUSED: " in printed and words in printed, printed
    assert setup.ran == []
    if not network:  # every check before the key check is made without the network
        assert setup.server.requests == []
    assert CANARY not in printed


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirected_key_check_is_refused_and_the_key_never_reaches_the_other_host(setup, other_server, capsys, status):
    target = other_server.url + "/v1/messages/count_tokens"
    setup.server.script = lambda h, b: answer(h, status, {}, headers=(("location", target),))
    assert go(setup) == 2
    printed = capsys.readouterr().out
    assert f"REFUSED: the key check was redirected (HTTP {status}); a redirect is never followed" in printed
    assert len(setup.server.requests) == 1 and other_server.requests == [] and setup.ran == []
    assert CANARY not in printed


def test_a_clean_run_prints_the_upper_bound_asks_and_runs_through_timed_run(setup, capsys):
    assert go(setup) == 0
    printed = capsys.readouterr().out
    # S3's prompt size, measured again: 1,845 calls and 3,785,896 bytes; 3,785,896 x 0.10 + 1,845 x 512 x 0.50
    # per million = 0.8509096 USD, and 1.5 times that is 1.2763644
    assert "expected run cost, upper bound: 0.8509 USD (1845 calls, 3785896 prompt bytes" in printed
    [(command, env)] = setup.ran
    assert command[0] == str(REPO.joinpath("tools", "timed_run.sh"))
    assert command[2:] == ["-m", "harness", "run-and-score", str(setup.config), str(setup.out)]
    assert env["MEMORY_GUARD_MAX_SECONDS"] == "7200" and env["BENCH_MAX_S"] == "0.82"
    [check] = setup.server.requests
    assert check["path"] == "/v1/messages/count_tokens" and check["body"]["model"] == MODEL
    headers = {name.lower(): value for name, value in check["headers"].items()}  # urllib capitalises names
    assert headers["x-api-key"] == CANARY and headers["anthropic-version"] == "2023-06-01"


def test_the_credit_prompt_names_one_and_a_half_times_the_bound(setup):
    asked = []
    assert go(setup, ask=lambda prompt: asked.append(prompt) or "no") == 2 and setup.ran == []
    assert "at least 1.2764 USD (1.5 times that)" in asked[0]


def test_a_rerun_with_a_written_cause_passes_it_on(setup):
    index_with(setup.out, "aborted")
    assert go(setup, rerun_cause="run 1 was killed by the memory guard") == 0
    assert setup.ran[0][0][-2:] == ["--rerun-cause", "run 1 was killed by the memory guard"]


def test_a_run_after_a_valid_run_needs_no_cause(setup):
    index_with(setup.out, "completed", False)
    assert go(setup) == 0


def write_run(out, run_id, refused, total, validity):
    out.joinpath(run_id).mkdir(parents=True)
    lines = [{"result": {"failure_kind": "model_refusal" if n < refused else None}} for n in range(total)]
    out.joinpath(run_id, "items.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
    out.joinpath(run_id, "report.json").write_text(json.dumps({"validity": validity}))


@pytest.mark.parametrize("refused, flagged", [(2, False), (3, True)])
def test_after_the_run_its_report_status_and_refusal_share_are_printed(tmp_path, capsys, refused, flagged):
    validity = {"dirty": False, "infra_invalid": False, "valid": True}
    write_run(tmp_path, "old", 0, 10, validity)
    write_run(tmp_path, "new", refused, 100, validity)
    tmp_path.joinpath("index.json").write_text(json.dumps({"runs": [
        {"run_id": "old", "run_set": "a" * 64, "state": "completed"},
        {"run_id": "new", "run_set": "a" * 64, "state": "completed"}], "sets": {}}))
    shares = wrapper.after(tmp_path, before={"old"})
    printed = capsys.readouterr().out
    assert list(shares) == ["new"] and "attempt 2 in run set aaaaaaaa" in printed
    assert "its report: valid True (dirty False, infra-invalid False)" in printed
    assert f"refusals: {refused} of 100 items = {refused}.00%" in printed
    assert ("REFUSAL CHECKPOINT" in printed) == flagged  # exactly 2% is not above 2%
