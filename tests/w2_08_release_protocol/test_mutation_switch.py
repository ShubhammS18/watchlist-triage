"""W2-08: the switch of the mutation proofs, as T06's (tests/t06_harness/test_mutation_switch.py). In a fresh test
process without W2_08_MUTATION=1, the proofs are skipped with their reason while the check that every breakage names a
guard test still runs. That they run with W2_08_MUTATION=1 is shown by the by-hand run recorded in the design doc;
running them here would put their 30-odd seconds back into the gate."""
import os
import subprocess
import sys

from release_common import REPO

T = "tests/w2_08_release_protocol/test_mutation.py::"
PROOF = T + "test_every_breakage_is_caught_and_the_real_files_are_unchanged"
ALWAYS = T + "test_every_breakage_names_a_guard_test_that_exists_and_a_text_that_occurs_once"


def test_the_mutation_proofs_are_skipped_without_w2_08_mutation_1():
    env = {key: value for key, value in os.environ.items() if key != "W2_08_MUTATION"}
    done = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", PROOF, ALWAYS],
                          cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and "1 passed, 1 skipped" in done.stdout, done.stdout
    assert "the mutation proofs run only with W2_08_MUTATION=1" in done.stdout
