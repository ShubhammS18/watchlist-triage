"""T06 stage 5: the mutation proofs. Forty-two deliberate breakages, each applied to its own temporary
copy, must each make its named guard test fail, while the same test passes on an untouched copy. The real
files are not changed. The proofs rerun the named guard tests only, `mutations.AT_A_TIME` copies at a time,
each in a process limited to `mutations.MEMORY_LIMIT` of address space."""
import os
import resource
import subprocess

import pytest

import mutations

# The mutation proofs run by hand before completion, with T06_MUTATION=1, and are recorded as evidence; the default
# gate run skips them, except the check that every breakage names a guard test that exists, which is quick and runs
# in it (DEC-T06-GATE-TIME). tests/t06_harness/test_mutation_switch.py shows both ways.
by_hand = pytest.mark.skipif(os.environ.get("T06_MUTATION") != "1",
                             reason="the mutation proofs run only with T06_MUTATION=1, by hand before completion")


def test_every_breakage_names_a_guard_test_that_exists():
    assert len(mutations.MUTATIONS) == 43
    for what, name, old, new, guard, expected in mutations.MUTATIONS:
        path, test = guard.split("::")
        assert f"def {test}(" in mutations.REPO.joinpath(path).read_text(encoding="utf-8"), guard
        assert mutations.REPO.joinpath(name).read_text(encoding="utf-8").count(old) == 1, (name, old)
        assert old != new and what and expected and all(expected)


@by_hand
def test_every_deliberate_breakage_is_caught_and_the_real_files_are_unchanged(tmp_path):
    before = mutations.real_files_digest()
    rows = mutations.prove(tmp_path)
    assert mutations.real_files_digest() == before  # hashed before and after the whole batch
    assert [row[0] for row in rows] == list(range(1, 44))
    not_proven = [row for row in rows if row[3] != "passed" or row[4] not in mutations.CAUGHT]
    assert not not_proven, not_proven
    assert len({path.name for path in tmp_path.iterdir() if path.name.startswith("broken-")}) == 43  # one copy each


@by_hand
def test_a_broken_copy_that_runs_out_of_memory_dies_at_the_limit_and_counts_as_caught(tmp_path):
    assert mutations.AT_A_TIME == 2 and mutations.MEMORY_LIMIT == 1 << 30
    before = mutations.real_files_digest()
    rows = mutations.prove(tmp_path, (mutations.HUNGRY,))
    assert mutations.real_files_digest() == before
    assert [row[3:] for row in rows] == [("passed", "out of memory")]  # the same test passes on the untouched copy
    # no process this one started and waited for ever held more than the limit (ru_maxrss is in kilobytes here)
    assert resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024 < mutations.MEMORY_LIMIT


@by_hand
def test_a_copy_ended_by_a_signal_is_not_counted_as_out_of_memory_and_is_not_caught(tmp_path):
    rows = mutations.prove(tmp_path, (mutations.KILLED,))
    assert [row[3:] for row in rows] == [("passed", "passed")]  # "passed" on the broken copy: not caught
    assert mutations.run_guards(tmp_path.joinpath("broken-1"), [mutations.KILLED[4]])[0] == -15  # it was the signal


@by_hand
def test_a_signal_with_memory_error_text_in_the_output_is_not_out_of_memory(tmp_path, monkeypatch):
    def ended(arguments, **options):  # as if the copy printed a MemoryError and was then ended by SIGTERM
        return subprocess.CompletedProcess(arguments, -15, stdout="E   MemoryError\n", stderr="")

    monkeypatch.setattr(mutations.subprocess, "run", ended)
    assert mutations.run_guards(tmp_path, ["a guard"]) == (-15, [], False)  # not out of memory
    entry = mutations.MUTATIONS[0]
    assert not mutations.caught(entry, -15, [])  # and not caught either: no failure was reported
    monkeypatch.setattr(mutations.subprocess, "run",
                        lambda arguments, **options: subprocess.CompletedProcess(arguments, 1, "E   MemoryError\n", ""))
    assert mutations.run_guards(tmp_path, ["a guard"]) == (1, [], True)  # the copy ended itself: out of memory


@by_hand
def test_an_untouched_copy_passes_only_with_exit_code_0(tmp_path):
    guard = mutations.MUTATIONS[0]
    rows = mutations.prove(tmp_path, (guard,), untouched_change=mutations.UNRELATED_FAILURE)
    code, failed, _ = mutations.run_guards(tmp_path.joinpath("untouched-0"), [guard[4]])
    assert code == 1 and not any(line.startswith("FAILED ") for line in failed)  # the guard itself passed
    assert [row[3] for row in rows] == ["failed"]  # yet the untouched copy is not a pass
    assert [row[3:] for row in mutations.prove(tmp_path.joinpath("clean"), (guard,))] == [("passed", "failed")]


@by_hand
def test_a_broken_copy_that_fails_for_a_reason_its_entry_does_not_name_is_not_caught(tmp_path):
    thirteen, twenty = mutations.MUTATIONS[12], mutations.MUTATIONS[19]
    assert thirteen[5] == mutations.LOADING_ZERO and twenty[5] == ("KeyError: 'kind'",)
    rows = mutations.prove(tmp_path, (
        thirteen[:5] + (mutations.ASSERTS,),  # the file cannot be loaded, but a failing assertion is what is named
        twenty[:5] + (mutations.ASSERTS,),    # the guard test fails with a KeyError, not with an assertion
        ("the scoring module cannot be loaded, for another reason than the one named", "harness/score.py",
         'from . import cost as money\n', 'from . import cost as money\nraise RuntimeError("unrelated")\n', *thirteen[4:]),
        ("another test's breakage: the guard still passes", *mutations.MUTATIONS[0][1:4], *thirteen[4:]),
    ))
    assert [row[3:] for row in rows] == [("passed", "passed")] * 4  # "passed" on the broken copy: not caught
    assert [row[3:] for row in mutations.prove(tmp_path.joinpath("named"), (thirteen, twenty))] == [("passed", "failed")] * 2
