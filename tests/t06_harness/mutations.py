"""Test-only: the mutation proofs of T06. Each deliberate breakage is applied to its own copy of the code and
the world, in a temporary folder; the named guard test must then fail there, and must pass on an untouched
copy made the same way. The real files are never changed: they are hashed before and after the whole batch.

AT_A_TIME copies run at once, each in a process whose address space is limited to MEMORY_LIMIT. A broken copy
that runs out of memory therefore dies alone, and counts as caught, instead of taking the machine down.

Run `python tests/t06_harness/mutations.py` to print the table; test_mutation.py runs the same proof in the gate.
"""
import hashlib
import os
import resource
import shutil
import subprocess
import sys
import tempfile
from concurrent import futures
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COPIED = ("harness", "tests/t06_harness", "baseline_agent", "model_interface", "worldgen", "framings", "data/world")
AT_A_TIME = 2  # copies running at once
MEMORY_LIMIT = 1 << 30  # bytes of address space (RLIMIT_AS) for each copy's test process and what it starts
CAUGHT = ("failed", "out of memory")  # the two ways a broken copy can be caught
# the launcher: set the limit in the new process itself, then run pytest there
LIMITED = ("import resource, sys; resource.setrlimit(resource.RLIMIT_AS, (int(sys.argv[1]),) * 2); "
           "import pytest; sys.exit(pytest.main(sys.argv[2:]))")
T = "tests/t06_harness/"

# How a broken copy may end, as the start of the reason pytest gives. Each entry names its own; any other ending
# is NOT a catch.
ASSERTS = ("assert ", "AssertionError")  # a failing assertion in the named guard test
NOT_REFUSED = ("Failed: DID NOT RAISE ConfigError",)  # the guard expects a refusal and none came
LOADING = "on loading: "  # before a reason: the guard's file could not even be loaded, and this is why
LOADING_ZERO = (LOADING + "ZeroDivisionError: Fraction(0, 0)",)

# (what is broken, file, the text as it is, the text as broken, the test that must catch it, how it must fail)
MUTATIONS = (
    ("a failure that says CLOSE is counted as a CLOSE", "harness/score.py",
     '    return "ESCALATE" if line["result"]["system_failure"] else line["result"]["recommendation"]',
     '    return line["result"]["recommendation"]',
     T + "test_score.py::test_a_system_failure_is_never_counted_as_a_close", ASSERTS),
    ("twin items are counted in the main figures", "harness/score.py",
     '    main = [line for line in lines if not line["twin"]]', '    main = list(lines)',
     T + "test_score.py::test_micro_overall_counts", ASSERTS),
    ("over-escalation leaves failures out", "harness/score.py",
     '"over_escalation": rate(len(escalated), len(clear)),',
     '"over_escalation": rate(len(escalated) - clear_failed, len(clear)),',
     T + "test_score.py::test_micro_over_escalation_and_its_failure_share", ASSERTS),
    ("citation existence trusts the agent's flag", "harness/score.py",
     'rate(sum(1 for line in answered if valid_citation_set(line)), len(answered)),',
     'rate(sum(1 for line in answered if not line["result"]["citation_invalid"]), len(answered)),',
     T + "test_score.py::test_citation_existence_is_worked_out_here_and_not_taken_from_the_agents_flag", ASSERTS),
    ("precision counts a twice-cited ID twice", "harness/score.py",
     'sum(len(cited) for cited, _ in keys))', 'sum(len(line["result"]["cited_ids"]) for line in closed_clear))',
     T + "test_score.py::test_micro_citation_figures", ASSERTS),
    ("the AC-2 re-check skips twin closes", "harness/score.py",
     '"ac2": {"main": _ac2(main), "twin": _ac2(twins)},', '"ac2": {"main": _ac2(main), "twin": _ac2([])},',
     T + "test_score.py::test_micro_citation_figures", ASSERTS),
    ("\"not applicable\" is reported as an ordinary 0", "harness/score.py",
     '"not_applicable": denominator == 0}', '"not_applicable": False}',
     T + "test_score.py::test_citation_accuracy_is_not_applicable_when_nothing_was_closed", ASSERTS),
    ("the injected item's ID is not set aside", "harness/score.py",
     '- {facts["removed_evidence_item_id"]}', '- set()',
     T + "test_score.py::test_micro_injection_divergence_and_its_causes", ASSERTS),
    ("a twin is compared with framing 1 of its original", "harness/score.py",
     'by_place[run, facts["twin_of"], framing], blocks', 'by_place[run, facts["twin_of"], 1], blocks',
     T + "test_score.py::test_micro_injection_divergence_and_its_causes", ASSERTS),
    ("the cause split no longer adds up: a pair is counted under its cause twice", "harness/score.py",
     '        here["by_cause"][cause] += 1', '        here["by_cause"][cause] += 2',
     T + "test_score.py::test_the_split_by_cause_adds_up_to_the_headline_on_the_micro_world", ASSERTS),
    ("percentiles are no longer by nearest rank", "harness/score.py",
     '    return ordered[max(1, -(-percent * len(ordered) // 100)) - 1]',
     '    return ordered[min(len(ordered) - 1, percent * len(ordered) // 100)]',
     T + "test_score.py::test_percentiles_are_by_nearest_rank", ASSERTS),
    ("the pooled figure is one run's, not the sum over the runs", "harness/score.py",
     'for run, lines in runs.items() for line in lines], truth, prices, times)',
     'for run, lines in list(runs.items())[:1] for line in lines], truth, prices, times)',
     T + "test_sets.py::test_the_pooled_figures_are_sums_over_the_runs", ASSERTS),
    ("a not-applicable rate enters the minimum and maximum", "harness/score.py",
     '        present = [value for value in present if not value["not_applicable"]]\n', '',
     T + "test_sets.py::test_rates_are_compared_as_exact_fractions_and_a_not_applicable_one_is_left_out",
     LOADING_ZERO),
    ("the infrastructure mark is \"at or above\" the threshold", "harness/run.py",
     '    return Fraction(transient, total) > Fraction(Decimal(threshold))',
     '    return Fraction(transient, total) >= Fraction(Decimal(threshold))',
     T + "test_manifest.py::test_the_mark_is_strictly_above_the_threshold_in_exact_arithmetic", ASSERTS),
    ("unknown token counts are a complete cost of 0", "harness/cost.py",
     '"at_least": bool(no_counts or no_price)}', '"at_least": False}',
     T + "test_cost.py::test_unknown_token_counts_are_never_a_cost_of_zero", ASSERTS),
    ("cost is summed in floats", "harness/cost.py",
     '    return Fraction(number)', '    return float(number)',
     T + "test_cost.py::test_no_float_is_used_where_floats_would_be_wrong", ASSERTS),
    ("a failure costs no L2 time", "harness/score.py",
     'cells.setdefault(name, {"ESCALATE": 0, "CLOSE": 0})[verdict(line)] += 1',
     'cells.setdefault(name, {"ESCALATE": 0, "CLOSE": 0})[verdict(line)] += not line["result"]["system_failure"]',
     T + "test_cost.py::test_a_system_failure_costs_l2_time_like_any_escalation", ASSERTS),
    ("second review is charged under the policy \"none\"", "harness/cost.py",
     'share = second if policy == "STRICT_FOUR_EYES" else 0', 'share = second',
     T + "test_cost.py::test_four_eyes_costs_exactly_the_second_reviews", ASSERTS),
    ("the always-escalate flag uses a fixed 0.9 instead of the world's counts", "harness/cost.py",
     'proposal + (1 - Fraction(escalate_alerts, alerts)) * l2 < manual', 'proposal + Fraction(9, 10) * l2 < manual',
     T + "test_cost.py::test_the_always_escalate_flag_follows_the_worlds_own_counts", ASSERTS),
    ("a file that does not say its kind is no longer refused", "harness/cost.py",
     'value.get("kind") not in KINDS:', 'value.get("kind", "fixture") not in KINDS:',
     T + "test_cost.py::test_a_file_must_say_its_kind_and_a_sourced_one_must_source_every_value",
     ("KeyError: 'kind'",)),
    ("a real provider accepts a fixture file", "harness/run.py",
     '    if fixtures and model_config["provider"] not in NOT_REAL:', '    if False:',
     T + "test_cost.py::test_a_real_provider_refuses_a_fixture_file_before_any_call",
     NOT_REFUSED),
    ("AC-6 ignores its time half", "harness/score.py",
     'if not_applicable or time_part == "fail" else', 'if not_applicable else',
     T + "test_reference.py::test_ac6_fails_if_either_part_fails", ASSERTS),
    ("the acceptance check passes AC-1 despite a missed true match", "harness/score.py",
     '"AC-1": {"result": result(missed),', '"AC-1": {"result": "pass",',
     T + "test_reference.py::test_a_missed_true_match_in_any_completed_run_fails_ac1", ASSERTS),
    ("a reference agent cites the first ID shown, not the lowest", "harness/agents.py",
     '"cited_ids": [min(item["id"] for item in items)]', '"cited_ids": [items[0]["id"]]',
     T + "test_reference.py::test_a_reference_agent_returns_the_t05_result_shape_and_cites_the_lowest_id", ASSERTS),
    ("one token wrapper is shared by all items", "harness/run.py",
     '    tokens = Tokens(model)\n    begun', '    tokens = model.__dict__.setdefault("_shared", Tokens(model))\n    begun',
     T + "test_parallel.py::test_one_token_calls_sum_exactly_under_the_stress_workers", ASSERTS),
    ("hand-offs continue after a fault", "harness/run.py",
     '                if faults:\n                    break\n                queue_s = paced(queued)\n'
     '                collect(block=False)  # again: a call may have failed during the pacer wait\n'
     '                if faults:\n                    break\n',
     '                if False:\n                    break\n                queue_s = paced(queued)\n'
     '                collect(block=False)  # again: a call may have failed during the pacer wait\n'
     '                if False:\n                    break\n',
     T + "test_parallel.py::test_after_a_fault_nothing_more_is_handed_off_and_the_calls_in_flight_are_waited_for", ASSERTS),
    ("no re-check for faults after the pacer wait", "harness/run.py",
     '                collect(block=False)  # again: a call may have failed during the pacer wait\n'
     '                if faults:\n                    break\n', '',
     T + "test_parallel.py::test_a_fault_that_comes_back_during_the_pacer_wait_stops_the_next_hand_off", ASSERTS),
    ("the pacer's wait is added to the item's own time", "harness/run.py",
     '"result": result, "wall_s": wall_s, "queue_s": queue_s,',
     '"result": result, "wall_s": wall_s + queue_s, "queue_s": queue_s,',
     T + "test_parallel.py::test_the_pacer_spaces_the_hand_offs_evenly_on_a_fake_clock", ASSERTS),
    ("the check of the log hand-over is removed", "harness/run.py",
     '        if sink != [result["log"]]:', '        if False:',
     T + "test_run.py::test_a_wrong_log_hand_over_aborts_the_run", ASSERTS),
    ("the agent-side world check is skipped", "harness/run.py",
     '        check_world(config["world"], listed)\n', '        pass\n',
     T + "test_run.py::test_a_changed_world_file_aborts_the_run_before_any_call", ASSERTS),
    ("the run step also hashes the hidden files", "harness/run.py",
     '        if name.startswith("hidden/") == hidden and', '        if (not hidden or name.startswith("hidden/")) and',
     T + "test_run.py::test_the_world_check_passes_on_the_committed_world_and_never_reads_hidden",
     ("FileNotFoundError",)),
    ("an output folder inside the repository is accepted", "harness/run.py",
     '    if out.is_relative_to(records.REPO):', '    if False:',
     T + "test_run.py::test_an_output_folder_inside_the_repository_is_refused",
     NOT_REFUSED),
    ("the dirty flag ignores untracked files", "harness/manifest.py",
     '        if status != "??" or not top.joinpath(name).resolve().is_relative_to(out):', '        if status != "??":',
     T + "test_manifest.py::test_the_dirty_flag", ASSERTS),
    ("superseding no longer asks for a written cause", "harness/manifest.py",
     '    if not isinstance(cause, str) or not cause.strip():', '    if False:',
     T + "test_sets.py::test_superseding_needs_a_written_cause",
     ("AssertionError: no refusal for a missing written cause",)),
    ("a run in a superseded set is accepted", "harness/run.py",
     '    if superseded:  # refused before any call (DEC-T06-FAULTS)', '    if False:',
     T + "test_sets.py::test_a_run_in_a_superseded_set_is_refused_before_any_call",
     NOT_REFUSED),
    ("the manifest records the environment", "harness/run.py",
     '        "run_id": run_id, "run_set": run_set, "run_set_inputs": inputs,',
     '        "environment": dict(__import__("os").environ), "run_id": run_id, "run_set": run_set, "run_set_inputs": inputs,',
     T + "test_manifest.py::test_no_environment_variable_reaches_any_output", ASSERTS),
    ("the truth is imported at the top of the scoring module", "harness/score.py",
     'from . import cost as money\n', 'from worldgen import truth\n\nfrom . import cost as money\n',
     T + "test_score.py::test_the_truth_is_read_only_after_the_outputs_exist_and_were_checked", ASSERTS),
    ("the AC-2 re-check passes a bad CLOSE", "harness/score.py",
     '    valid = sum(1 for line in closes if valid_citation_set(line))', '    valid = len(closes)',
     T + "test_score.py::test_micro_citation_figures", ASSERTS),
    ("the order probe never sees the truth loaded", T + "test_score.py",
     '            state["first"] = [files, "worldgen.truth" in sys.modules]', '            state["first"] = [files, False]',
     T + "test_score.py::test_positive_control_the_order_probe_sees_the_truth_loaded_too_early", ASSERTS),
    ("the shared schema checks nothing", "harness/schema.py",
     '    """What is wrong with `value` against `spec`, naming the field, or None."""\n',
     '    """What is wrong with `value` against `spec`, naming the field, or None."""\n    return None\n',
     T + "test_score.py::test_each_round_7_finding_is_refused_on_a_small_run_in_memory",
     ("Failed: DID NOT RAISE",)),
    ("a set with a refused completed run can still be eligible", "harness/score.py",
     '                                 and not refused and not unassigned),', '                                 and not unassigned),',
     T + "test_score.py::test_a_refused_fourth_completed_run_makes_the_set_ineligible_and_is_named", ASSERTS),
    ("a set is still eligible while an index entry or a run cannot be placed", "harness/score.py",
     '                                 and not refused and not unassigned),', '                                 and not refused),',
     T + "test_score.py::test_while_any_index_entry_or_run_cannot_be_placed_in_a_set_no_set_is_eligible", ASSERTS),
    ("the file-system recorder ignores what it sees", T + "recording_agent.py",
     '    if armed and event in WATCHED:', '    if False:',
     T + "test_child.py::test_positive_control_an_agent_that_opens_a_file_is_caught_on_every_call", ASSERTS),
)

# Not one of the proofs: the proof of the memory limit itself. Every item tries to keep 1.5 times the limit.
HUNGRY = ("every item keeps far more memory than a copy may have", "harness/run.py",
          '        return [dict(attempt) for attempt in self.attempts]',
          '        return [bytearray(64 << 20) for _ in range(3 * MEMORY_LIMIT // (128 << 20))]'.replace(
              "MEMORY_LIMIT", str(MEMORY_LIMIT)),
          T + "test_parallel.py::test_one_token_calls_sum_exactly_under_the_stress_workers", ASSERTS)

# Not proofs either: two copies the proof must refuse, for its own tests. KILLED ends the copy's test process
# with a signal that is not a MemoryError; UNRELATED_FAILURE makes the session fail at its end in a way that has
# nothing to do with the guard test, which itself still passes.
KILLED = ("the copy's test process is killed by a signal", "harness/run.py",
          '        return [dict(attempt) for attempt in self.attempts]',
          '        return __import__("os").kill(__import__("os").getpid(), 15)',
          T + "test_parallel.py::test_one_token_calls_sum_exactly_under_the_stress_workers", ASSERTS)
UNRELATED_FAILURE = ("the session fails at its end, for a reason unrelated to the guard", T + "conftest.py",
                     "    assert status() == before\n", '    assert False, "an unrelated failure at the end of the session"\n',
                     None, None)


def real_files_digest():
    """One hash over every real file that the proofs copy. It must be the same after the batch as before it."""
    digest = hashlib.sha256()
    for name in COPIED:
        for path in sorted(REPO.joinpath(name).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def make_copy(folder, mutation=None):
    """An independent copy of the code and the world in `folder`, with one mutation applied if one is given."""
    for name in COPIED:
        shutil.copytree(REPO.joinpath(name), Path(folder, name), ignore=shutil.ignore_patterns("__pycache__"))
    if mutation is not None:
        _, name, old, new, *_ = mutation
        path = Path(folder, name)
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise ValueError(f"the text to break must appear exactly once in {name}, not {text.count(old)} times: {old!r}")
        path.write_text(text.replace(old, new), encoding="utf-8")
    return Path(folder)


def run_guards(folder, guards):
    """Run these guard tests in a copy, under the memory limit. Returns (exit code, the lines of pytest's
    summary that report a failure, whether the process ran out of memory: it ended itself with a positive exit
    code and its output shows a MemoryError). The address-space limit sends no signal of its own: an allocation past it fails, which
    Python raises as MemoryError. So a process ended by a signal is never counted as out of memory."""
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["COLUMNS"] = "1000"  # so that pytest does not cut the reasons short
    done = subprocess.run([sys.executable, "-B", "-c", LIMITED, str(MEMORY_LIMIT), "-q", "-p", "no:cacheprovider",
                           "-rfE", *guards], cwd=folder, capture_output=True, text=True, env=environment)
    failed = [line for line in done.stdout.split("\n") if line.startswith(("FAILED ", "ERROR "))]
    # a positive exit code: the process ended itself; a negative one is a signal, never out of memory
    out_of_memory = done.returncode > 0 and "MemoryError" in done.stdout + done.stderr
    return done.returncode, failed, out_of_memory


def reason(guard, line):
    """What one line of pytest's summary says about `guard`: why that test failed, or, starting with LOADING,
    why its file could not be loaded. None if the line is about anything else."""
    kind, _, rest = line.partition(" ")
    if kind == "ERROR" and rest.startswith(guard.split("::")[0] + " - "):
        return LOADING + rest.split(" - ", 1)[1]
    if kind == "FAILED" and rest.startswith(guard):
        rest = rest[len(guard):]
        if rest.startswith("["):  # one case of a test with parameters
            rest = rest[rest.find("] - ") + 1:]
        if rest.startswith(" - "):
            return rest[3:]
    return None


def caught(mutation, code, failed):
    """Whether a broken copy ended exactly as its entry names: every failure pytest reports is about the guard
    and gives a named reason, and the exit code fits (1 for failed tests, 4 for a file that was not loaded)."""
    found = [reason(mutation[4], line) for line in failed]
    expected_code = 4 if mutation[5][0].startswith(LOADING) else 1
    return bool(found) and code == expected_code and all(one is not None and one.startswith(mutation[5]) for one in found)


def prove(folder, mutations=MUTATIONS, untouched_change=None):
    """The whole proof. One row per breakage: (number, what is broken, guard test, result on the untouched
    copy, result on the broken copy). A result is "passed" or "failed"; on the broken copy it can also be
    "out of memory", when the memory limit ended the copy's process."""
    folder = Path(folder)
    guards = sorted({mutation[4] for mutation in mutations})
    chunks = [chunk for chunk in (guards[start::AT_A_TIME] for start in range(AT_A_TIME)) if chunk]

    def untouched(number):
        # `untouched_change` is for the proof's own tests only: it breaks the untouched copies on purpose
        return run_guards(make_copy(folder.joinpath(f"untouched-{number}"), untouched_change), chunks[number])

    def broken(number):
        return run_guards(make_copy(folder.joinpath(f"broken-{number + 1}"), mutations[number]), [mutations[number][4]])

    with futures.ThreadPoolExecutor(max_workers=AT_A_TIME) as pool:
        clean = list(pool.map(untouched, range(len(chunks))))
        results = list(pool.map(broken, range(len(mutations))))
    clean_of = {guard: result for chunk, result in zip(chunks, clean) for guard in chunk}
    rows = []
    for number, (mutation, (code, failed, out_of_memory)) in enumerate(zip(mutations, results), start=1):
        clean_code, _, _ = clean_of[mutation[4]]
        on_untouched = "passed" if clean_code == 0 else "failed"  # anything but a clean exit is not a pass
        on_broken = "out of memory" if out_of_memory else "failed" if caught(mutation, code, failed) else "passed"
        rows.append((number, mutation[0], mutation[4].split("::")[1], on_untouched, on_broken))
    return rows


if __name__ == "__main__":
    before = real_files_digest()
    with tempfile.TemporaryDirectory() as temporary:
        table = prove(temporary)
    print(f"{'#':>2}  {'untouched':9}  {'broken':13}  what is broken  ->  the test that must catch it")
    for number, what, guard, on_untouched, on_broken in table:
        print(f"{number:>2}  {on_untouched:9}  {on_broken:13}  {what}  ->  {guard}")
    proven = sum(1 for row in table if row[3] == "passed" and row[4] in CAUGHT)
    print(f"{proven} of {len(table)} breakages caught; the real files are "
          f"{'unchanged' if real_files_digest() == before else 'CHANGED'}")
    sys.exit(0 if proven == len(table) and real_files_digest() == before else 1)
