"""The T05 tests have teeth: each deliberate breakage of baseline_agent makes the tests that guard it fail.

Nothing in the repository is changed. The package and these tests are copied to a temporary folder, the copy is
broken, and the tests run there against the real world and the real worldgen and framings. model_interface is
copied too, unbroken, because its child process puts its own folder on the path: without the copy the child would
run the real agent and not the broken one. The untouched copy must pass in full, each broken copy must fail in
the named tests, and the real files must hash the same before and after. The hashes are printed (pytest -s).

The untouched copy runs every other test file of this folder, once. A broken copy reruns only its guard files:
the test files that hold that mutation's must-fail tests. Until the fourth review each broken copy reran every
file, which took about five minutes in all, more than the two minutes the task gate allows. The must-fail tests
of every mutation are unchanged. A broken copy now reports fewer failing tests in total where the breakage also
tripped tests in other files; those other files are not rerun for it.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT.joinpath("baseline_agent")
SUITE = ("test_payload_prompt.py", "test_agent.py", "test_refusal.py", "test_log.py", "test_agent_static.py",
         "test_parent_validation.py", "test_kinds.py")

ALLOWLIST = "[{key: item[key] for key in ITEM_KEYS} for item in items]"
ESCAPING = '    return line.replace("<", "\\\\u003c").replace(">", "\\\\u003e").replace("&", "\\\\u0026")\n'

FAIL_CLOSED = '''    except ChildTimeout:
        result = failure("child_timeout", "ChildTimeout", latency_s=time.monotonic() - begun)
    except ChildError:
        result = failure("child_crash", "ChildError", latency_s=time.monotonic() - begun)
    except Exception as error:  # anything else, such as a fault inside the model object itself
        result = failure("internal_error", type(error).__name__, latency_s=time.monotonic() - begun)
'''
STOP_UNLESS_RETRIED = "        if error_name not in RETRIED:\n"
REFUSAL_MAPPING = ',\n           "ModelRefusal": "model_refusal"}'
ITEM_COUNT_CHECK = '''    if payload.get("item_count") != len(payload["items"]):
        return failure("truncated_evidence", attempts=0)
'''
PARENT_KIND_RULE = '''        return (attempts is None and not entries and model_id is None and isinstance(error, str)
                and (PARENT_KINDS[kind] is None or error in PARENT_KINDS[kind]))
'''
RETRY_ORDER_RULE = ("    if errors[-1] != error or any(name not in RETRIED for name in errors[:-1]) "
                    "or (error in RETRIED and attempts != max_attempts):\n")
BAD = "test_an_inconsistent_result_from_the_child_ends_as_child_crash"
FORGED = "test_a_close_whose_log_contradicts_it_does_not_leave_as_a_close"

# name -> (file, text to find exactly once, replacement, tests that must then fail)
MUTATIONS = {
    "retry bad output": (
        "agent.py", STOP_UNLESS_RETRIED,
        '        if kind == "ok" or error_name is not None and error_name not in RETRIED:\n', (
            "test_bad_output_is_escalated_as_a_system_failure_and_not_tried_again[not JSON]",
            "test_bad_output_is_escalated_as_a_system_failure_and_not_tried_again[a CLOSE citing an id outside the bundle]",
            "test_bad_output_after_a_timeout_ends_the_run_there")),
    "remove fail-closed": (
        "recommend.py", FAIL_CLOSED, "    except ZeroDivisionError:\n        raise\n", (
            "test_a_model_that_never_answers_ends_as_child_timeout",
            "test_a_child_that_crashes_ends_as_child_crash",
            "test_a_fault_inside_the_model_object_or_an_alert_with_no_items_does_not_raise")),
    "allow a CLOSE with an unknown id": (
        "reply.py", '    if unknown and reply["recommendation"] == "CLOSE":', "    if False:", (
            "test_bad_output_is_escalated_as_a_system_failure_and_not_tried_again[a CLOSE citing an id outside the bundle]",
            "test_bad_output_is_escalated_as_a_system_failure_and_not_tried_again[a CLOSE citing only an id outside the bundle]",
            "test_no_fault_of_any_kind_gives_a_close")),
    "unlimited retries": (
        "agent.py", '    for attempt in range(1, job["retries"] + 2):', "    for attempt in range(1, 1000):", (
            "test_a_fault_that_does_not_go_away_fails_after_three_attempts[step0-timeout-ModelTimeout]",
            "test_a_fault_that_does_not_go_away_fails_after_three_attempts[step1-provider_error-ProviderError]",
            "test_the_number_of_retries_can_be_set_and_must_be_a_whole_number")),
    "drop the item-count check": (
        "agent.py", ITEM_COUNT_CHECK, "", (
            "test_a_damaged_payload_is_a_system_failure_and_the_model_is_never_asked[an item lost]",
            "test_a_damaged_payload_is_a_system_failure_and_the_model_is_never_asked[a count too high]",
            "test_a_damaged_payload_is_a_system_failure_and_the_model_is_never_asked[no count]")),
    "remove the refusal mapping": (
        "agent.py", REFUSAL_MAPPING, "}", (
            "test_a_refusal_is_escalated_as_a_system_failure_after_one_attempt_with_a_log_entry",
            "test_a_model_that_always_refuses_is_asked_once",
            "test_a_refusal_after_a_timeout_ends_the_run_there")),
    "retry a refusal": (
        "agent.py", 'RETRIED = ("ModelTimeout", "ProviderError")', 'RETRIED = ("ModelTimeout", "ProviderError", "ModelRefusal")', (
            "test_a_refusal_is_escalated_as_a_system_failure_after_one_attempt_with_a_log_entry",
            "test_a_model_that_always_refuses_is_asked_once")),
    "send correlation_id to the child": (
        "recommend.py", '"retries": retries}', '"retries": retries, "correlation_id": correlation_id}', (
            "test_the_correlation_id_is_in_the_log_and_never_in_the_job_the_payload_or_the_prompt",
            "test_the_child_gets_only_the_payload_the_settings_and_the_retries_and_a_limit_above_all_attempts")),
    "add an open() call": (
        "agent.py", '    payload = job["payload"]\n', '    payload = job["payload"]\n    open("/dev/null").close()\n', (
            "test_no_module_that_runs_in_the_child_touches_files_or_imports_outside_the_allowlist",)),
    "remove the parent check of the child result": (
        "recommend.py", "        if not _valid(result, item_ids, 1 + retries):", "        if result is None:", (
            "test_a_close_with_no_reason_no_citations_and_a_failure_kind_does_not_leave_as_a_close",
            "test_an_inconsistent_result_from_the_child_ends_as_child_crash[a close citing an id outside the bundle]",
            "test_an_inconsistent_result_from_the_child_ends_as_child_crash[a failure that says CLOSE]",
            "test_an_inconsistent_result_from_the_child_ends_as_child_crash[a log key missing]",
            "test_the_ids_are_checked_against_this_alert_and_no_other")),
    # ---- the log-to-result rules of the parent, one group each (DEC-T05-LOG-INVARIANTS)
    "drop the limit on attempts": (
        "recommend.py", "    if not _count(attempts) or len(entries) != attempts or attempts > max_attempts:",
        "    if not _count(attempts) or len(entries) != attempts:", (
            f"{BAD}[a close with more attempts than allowed]",
            "test_more_retries_allow_more_attempts")),
    "accept a result with no model call for any kind": (
        "recommend.py", '        return kind in PAYLOAD_KINDS and error is None and model_id is None and log["latency_s"] == 0',
        "        return True", (
            f"{FORGED}[no attempts]",
            f"{BAD}[a close with no attempts]",
            f"{BAD}[an escalate with no attempts]",
            f"{BAD}[a timeout with no attempts]",
            f"{BAD}[missing citations with no attempts]",
            f"{BAD}[truncated evidence with a model id]",
            f"{BAD}[truncated evidence with an error name]")),
    "drop the rules on the order of attempts": (
        "recommend.py", RETRY_ORDER_RULE, "    if False:\n", (
            f"{FORGED}[a final attempt with an error]",
            f"{BAD}[a close whose final attempt has an error]",
            f"{BAD}[a close after an earlier attempt that is not retried]",
            f"{BAD}[a close after an earlier attempt with no error]",
            f"{BAD}[a timeout whose final attempt differs from its error name]",
            f"{BAD}[a timeout that stopped before the last attempt]")),
    "drop the rule that an error names its kind": (
        "recommend.py", '    return kind == KIND_OF.get(error, "model_error") and model_id is None', "    return True", (
            f"{BAD}[a close whose error name and final attempt agree]",
            f"{BAD}[a refusal with a timeout error name]",
            f"{BAD}[a model error with a name that has its own kind]",
            f"{BAD}[missing citations with an error name]",
            f"{BAD}[a timeout with a model id]")),
    "accept any kind when the last call returned a reply": (
        "recommend.py", '        return kind in ("ok", *REPLY_KINDS) and isinstance(model_id, str)', "        return True", (
            f"{BAD}[a close with no model id]",
            f"{BAD}[a timeout with no error name]",
            f"{BAD}[missing citations with no model id]",
            f"{BAD}[truncated evidence with a model call]")),
    "accept a parent-only kind with any log": (
        "recommend.py", PARENT_KIND_RULE, "        return True\n", (
            f"{BAD}[a child timeout with attempts]",
            f"{BAD}[a child timeout with another error name]",
            f"{BAD}[a child crash with an unknown error name]",
            f"{BAD}[an internal error with no error name]")),
    "accept a total time shorter than an attempt": (
        "recommend.py", '    if any(entry["latency_s"] > log["latency_s"] for entry in entries):', "    if False:", (
            "test_a_close_whose_total_latency_is_shorter_than_one_of_its_attempts_does_not_leave_as_a_close",
            f"{BAD}[a close whose total time is shorter than its attempt]",
            f"{BAD}[a close whose total time is shorter than an earlier attempt]",
            f"{BAD}[a timeout whose total time is shorter than one attempt]")),
    "accept a total time on a payload that was refused": (
        "recommend.py", ' and model_id is None and log["latency_s"] == 0', " and model_id is None", (
            f"{BAD}[truncated evidence with a total time]",
            f"{BAD}[an unknown payload schema version with a total time]")),
    "give the sink the result's own log": (
        "recommend.py", 'sink.append(copy.deepcopy(result["log"]))', 'sink.append(result["log"])', (
            "test_a_sink_that_changes_its_record_leaves_the_returned_close_intact",
            "test_the_sink_gets_a_copy_that_later_changes_to_the_result_do_not_reach")),
    "add a failure kind in the child that the parent does not know": (
        "reply.py", 'raise ReplyFault("invalid_citation")', 'raise ReplyFault("bad_citation")', (
            "test_every_kind_the_child_can_emit_is_known_to_the_parent_and_nothing_else_is",
            "test_there_is_a_way_to_produce_every_kind_the_child_can_emit")),
    "add record_id to the payload": (
        "payload.py", ALLOWLIST, '[{key: item[key] for key in (*ITEM_KEYS, "record_id") if key in item} for item in items]', (
            "test_the_payload_has_exactly_the_agreed_keys",
            "test_every_real_alert_builds_in_every_framing_with_no_label_or_key_name")),
    "pass every item field through": (
        "payload.py", ALLOWLIST, "[dict(item) for item in items]", (
            "test_the_payload_has_exactly_the_agreed_keys",
            "test_every_real_alert_builds_in_every_framing_with_no_label_or_key_name",
            "test_extra_fields_on_an_item_never_reach_the_payload_or_the_prompt")),
    "remove the escaping": (
        "prompt.py", ESCAPING, "    return line\n", (
            "test_a_snippet_cannot_close_the_delimiter_or_add_a_line",)),
}


def hashes():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(PACKAGE.glob("*.py"))}


def copy_to(folder):
    skip = shutil.ignore_patterns("__pycache__")
    shutil.copytree(PACKAGE, folder.joinpath("baseline_agent"), ignore=skip)
    shutil.copytree(ROOT.joinpath("model_interface"), folder.joinpath("model_interface"), ignore=skip)
    shutil.copytree(HERE, folder.joinpath("tests", "t05_agent"), ignore=skip)
    return folder


def guard_files(must_fail):
    """The test files that hold these must-fail tests, in the order of SUITE: all that a broken copy reruns."""
    wanted = {test.split("[")[0] for test in must_fail}
    defined = {name: set(re.findall(r"^def (test_\w+)", HERE.joinpath(name).read_text(encoding="utf-8"), re.M))
               for name in SUITE}
    missing = wanted - set().union(*defined.values())
    assert not missing, f"must-fail tests that no test file defines: {sorted(missing)}"
    return tuple(name for name in SUITE if wanted & defined[name])


def run_suite(folder, files=SUITE):
    # The folder comes first on the path, so baseline_agent and model_interface are the copies; worldgen and
    # framings are the real ones.
    return subprocess.run(
        [sys.executable, "-B", "-m", "pytest", *(f"tests/t05_agent/{name}" for name in files), "-q", "-p",
         "no:cacheprovider", "-rf"],
        cwd=folder, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=300)


@pytest.fixture(scope="module")
def untouched_copy_passes(tmp_path_factory):
    done = run_suite(copy_to(tmp_path_factory.mktemp("untouched")))
    assert done.returncode == 0, done.stdout


@pytest.mark.parametrize("name", MUTATIONS)
def test_a_deliberate_breakage_is_caught(tmp_path, untouched_copy_passes, name):
    filename, old, new, must_fail = MUTATIONS[name]
    before = hashes()
    target = copy_to(tmp_path).joinpath("baseline_agent", filename)
    source = target.read_text(encoding="utf-8")
    assert source.count(old) == 1, f"the text to break is no longer in {filename}"
    target.write_text(source.replace(old, new), encoding="utf-8")

    files = guard_files(must_fail)
    done = run_suite(tmp_path, files)

    assert done.returncode == 1, done.stdout
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED ")]
    for test in must_fail:
        assert any(f"::{test}" in line for line in failed), f"{test} did not fail:\n{done.stdout}"
    after = hashes()
    print(f"\n{name}: {len(failed)} tests failed on the broken copy, rerunning {', '.join(files)}")
    for line in failed:
        print(f"  {line[:150]}")
    for file in before:
        print(f"  {file}  before {before[file][:16]}  after {after[file][:16]}")
    assert after == before
