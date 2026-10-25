"""The W2-07 tests have teeth: with socket creation no longer refused, the tests that guard it fail.

Nothing in the repository is changed. The package and these tests are copied to a temporary folder, the copy's
guard is broken, and the tests run there, inside `unshare -rn` so that a broken copy cannot send a name lookup off
this machine. The untouched copy must pass the same tests, the broken copy must fail in the named ones, and the
real files must hash the same before and after.
"""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT.joinpath("model_interface")
BREAK = '"socket.__new__", '
MUST_FAIL = (
    "test_no_dns_query_leaves_the_agent_process",
    "test_refused_before_the_resolver",
    "test_no_socket_object_can_be_made")


def hashes():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(PACKAGE.iterdir()) if path.is_file()}


def run_copy(folder, broken):
    skip = shutil.ignore_patterns("__pycache__")
    shutil.copytree(PACKAGE, folder.joinpath("model_interface"), ignore=skip)
    shutil.copytree(HERE, folder.joinpath("tests", "w2_07_isolation"), ignore=skip)
    if broken:
        child = folder.joinpath("model_interface", "child.py")
        source = child.read_text(encoding="utf-8")
        assert source.count(BREAK) == 1, "the text to break is no longer in child.py"
        child.write_text(source.replace(BREAK, ""), encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "WT_SKIP_NETNS"}  # the copy must not skip
    return subprocess.run(
        ["unshare", "-rn", sys.executable, "-m", "pytest", "tests/w2_07_isolation/test_dns_isolation.py",
         "-k", "not t04_name_lookup", "-q", "-p", "no:cacheprovider", "-rf"],
        cwd=folder, env=env, capture_output=True, text=True, timeout=120)


def test_removing_the_socket_creation_block_is_caught(netns, tmp_path):
    before = hashes()
    untouched = run_copy(tmp_path.joinpath("untouched"), broken=False)
    assert untouched.returncode == 0, untouched.stdout

    done = run_copy(tmp_path.joinpath("broken"), broken=True)

    assert done.returncode == 1, done.stdout
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED ")]
    for test in MUST_FAIL:
        assert any(f"::{test}" in line for line in failed), f"{test} did not fail:\n{done.stdout}"
    print(f"\nremove socket.__new__: {len(failed)} tests failed on the broken copy")
    assert hashes() == before
