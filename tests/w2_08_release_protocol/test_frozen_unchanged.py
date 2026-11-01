"""W2-08: without --release the release check is the one W2-01 and W2-02 reviewed. Its output on the two committed run
sets is byte for byte what it was before this task's first code change, and so are its exit codes. The hashes were
taken from `python -m harness acceptance` before release_check.py was edited."""
import hashlib
import subprocess
import sys

from release_common import REPO

GOLDEN = {  # folder, run set -> (SHA-256 of the command's standard output, exit code, result)
    ("w2-02-runs", "8f4050be0f28031f8ec64da2d193ecf12d9c5cb7aee868b4adda84e22c76f33e"):
        ("c839620e06603dec04f549e5e1aed7ba1277b87f7c0b89066bd22b50f067ccbe", 3,
         "PASS (cost bounded under a stated assumption)"),
    ("baseline", "f2e614d2d530dc65c1d9f4dbec452d93296f5f52420b0f7829ff4404e7a99305"):
        ("b4c3d94e66f47b68faf184d6f443ff317bf78892f4528d7757b4f4eef274fb5b", 1, "FAIL"),
}


def test_the_committed_run_sets_give_byte_identical_output():
    for (folder, run_set), (digest, code, result) in GOLDEN.items():
        done = subprocess.run([sys.executable, "-B", "-m", "harness", "acceptance", folder, run_set], cwd=REPO,
                              capture_output=True)
        assert f'"result": "{result}"'.encode() in done.stdout, done.stderr[-2000:]
        assert (hashlib.sha256(done.stdout).hexdigest(), done.returncode) == (digest, code), folder
