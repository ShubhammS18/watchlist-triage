"""The switch of the mutation proofs (DEC-T06-GATE-TIME): without T06_MUTATION=1 every mutation proof in
test_mutation.py is skipped, and with it they run; the check that every breakage names a guard test runs either way.
Shown in two fresh test processes started side by side."""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
T = "tests/t06_harness/test_mutation.py::"
CHEAPEST = T + "test_a_signal_with_memory_error_text_in_the_output_is_not_out_of_memory"  # a proof, quick, no subprocess
ALWAYS = T + "test_every_breakage_names_a_guard_test_that_exists"


def test_the_mutation_proofs_are_skipped_by_default_and_run_with_t06_mutation_1():
    base = {key: value for key, value in os.environ.items() if key != "T06_MUTATION"}
    command = [sys.executable, "-B", "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", CHEAPEST, ALWAYS]
    without, with_it = (subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True) for env in (base, {**base, "T06_MUTATION": "1"}))
    said_without, said_with = without.communicate(timeout=60)[0], with_it.communicate(timeout=60)[0]
    assert without.returncode == 0 and "1 passed, 1 skipped" in said_without, said_without  # the check still runs
    assert "the mutation proofs run only with T06_MUTATION=1" in said_without
    assert with_it.returncode == 0 and "2 passed" in said_with and "skipped" not in said_with, said_with
