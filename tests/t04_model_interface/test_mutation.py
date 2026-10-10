"""The T04 tests have teeth: each deliberate breakage of model_interface makes the tests that guard it fail.

Nothing in the repository is changed. The package and these tests are copied to a temporary folder, the copy is
broken, and the tests run there. The untouched copy must pass in full, each broken copy must fail in the named
tests, and the real files must hash the same before and after. The hashes are printed (run pytest with -s).
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT.joinpath("model_interface")
SUITE = ("test_interface.py", "test_isolation.py")

NETWORK_EVENTS = '''    "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg",
    "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo",
'''
PROGRAM_EVENTS = '''    "subprocess.Popen", "os.system", "os.exec", "os.spawn", "os.posix_spawn", "os.fork", "os.forkpty",
    "os.startfile", "os.startfile/2", "pty.spawn",
    # loading a library through ctypes
    "ctypes.dlopen"))
'''
ONE_CALL = '''    try:
        return {"result": asdict(model(request))}
    except ModelError as error:
'''
TWO_CALLS = '''    try:
        try:
            return {"result": asdict(model(request))}
        except ModelError:
            return {"result": asdict(model(request))}
    except ModelError as error:
'''

SETTINGS_KEYS = '''    if set(data["settings"]) != set(Settings.__dataclass_fields__):
        raise ValueError(f"settings must have exactly the keys {sorted(Settings.__dataclass_fields__)}")
'''

# The two tests that aim at an outside address and an outside name are left out of the run without the network
# block, so that a broken copy never sends anything off this machine. The local-server tests carry that proof.
LOCAL_ONLY = ("-k", "not outside_address and not name_lookup")

# name -> (file, text to find exactly once, replacement, test file to run, extra pytest arguments,
#          tests that must then fail)
MUTATIONS = {
    "remove the network block": (
        "child.py", NETWORK_EVENTS, "", "test_isolation.py", LOCAL_ONLY, (
            "test_no_connection_from_the_agent_process_arrives_at_the_local_server",
            "test_network_route_works_in_the_control_and_is_refused_in_the_agent_process[connect]",
            "test_network_route_works_in_the_control_and_is_refused_in_the_agent_process[getaddrinfo]",
            "test_network_route_works_in_the_control_and_is_refused_in_the_agent_process[bind]",
            "test_every_event_the_hook_blocks_is_covered_here")),
    "remove the program block": (
        "child.py", PROGRAM_EVENTS, "    ))\n", "test_isolation.py", (), (
            "test_exec_works_in_the_control_and_is_refused_in_the_agent_process",
            "test_program_start_works_in_the_control_and_is_refused_in_the_agent_process[subprocess]",
            "test_program_start_works_in_the_control_and_is_refused_in_the_agent_process[system]",
            "test_program_start_works_in_the_control_and_is_refused_in_the_agent_process[fork]",
            "test_program_start_works_in_the_control_and_is_refused_in_the_agent_process[posix_spawn]",
            "test_program_start_works_in_the_control_and_is_refused_in_the_agent_process[forkpty]",
            "test_program_start_works_in_the_control_and_is_refused_in_the_agent_process[pty_spawn]",
            "test_program_start_works_in_the_control_and_is_refused_in_the_agent_process[ctypes]",
            "test_every_event_the_hook_blocks_is_covered_here")),
    "remove the wall-clock cap": (
        "runner.py", "    timer.start()\n", "", "test_isolation.py", (), (
            "test_a_child_that_sleeps_past_the_limit_is_killed_and_reported_by_name",
            "test_a_model_call_that_outlasts_the_limit_ends_the_run_on_time")),
    "remove the model-call thread": (
        "runner.py", "    threading.Thread(target=work, daemon=True).start()\n", "    work()\n",
        "test_isolation.py", (), (
            "test_a_model_call_that_outlasts_the_limit_ends_the_run_on_time",)),
    "accept unknown request keys": (
        "__init__.py", ' or set(data) != {"messages", "settings"}:', ":", "test_interface.py", (), (
            "test_a_forged_call_with_a_tools_key_is_refused_and_never_reaches_the_model",
            "test_a_forged_call_of_the_wrong_shape_is_refused_at_the_pipe[a tools key]",
            "test_a_request_of_the_wrong_shape_is_a_value_error[a tools key]")),
    "accept unknown settings keys": (
        "__init__.py", SETTINGS_KEYS, "", "test_interface.py", (), (
            "test_forged_settings_are_a_value_error_and_not_a_raw_type_error[unknown field]",
            "test_forged_settings_are_a_value_error_and_not_a_raw_type_error[missing field]")),
    "add a retry": (
        "runner.py", ONE_CALL, TWO_CALLS, "test_interface.py", (), (
            "test_a_failure_crosses_the_pipe_as_the_same_named_error_after_exactly_one_call[timeout]",
            "test_a_failure_crosses_the_pipe_as_the_same_named_error_after_exactly_one_call[empty]",
            "test_a_failure_crosses_the_pipe_as_the_same_named_error_after_exactly_one_call[provider_error]")),
    "hardcode the stub": (
        "providers.py", 'model = PROVIDERS[config["provider"]](**options)', "model = Stub()", "test_interface.py", (), (
            "test_two_configuration_files_drive_the_same_code_to_different_replies",
            "test_two_configuration_files_drive_the_same_child_process_to_different_replies",
            "test_a_configured_failure_reaches_the_same_calling_code",
            "test_a_new_provider_is_one_registry_entry_and_no_change_to_the_calling_code")),
}


def hashes():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(PACKAGE.iterdir()) if path.is_file()}


def copy_to(folder):
    skip = shutil.ignore_patterns("__pycache__")
    shutil.copytree(PACKAGE, folder.joinpath("model_interface"), ignore=skip)
    shutil.copytree(HERE, folder.joinpath("tests", "t04_model_interface"), ignore=skip)
    return folder


def run_suite(folder, files, extra=()):
    return subprocess.run(
        [sys.executable, "-m", "pytest", *(f"tests/t04_model_interface/{name}" for name in files),
         "-q", "-p", "no:cacheprovider", "-rf", *extra], cwd=folder, capture_output=True, text=True, timeout=300)


@pytest.fixture(scope="module")
def untouched_copy_passes(tmp_path_factory):
    done = run_suite(copy_to(tmp_path_factory.mktemp("untouched")), SUITE)
    assert done.returncode == 0, done.stdout


@pytest.mark.parametrize("name", MUTATIONS)
def test_a_deliberate_breakage_is_caught(tmp_path, untouched_copy_passes, name):
    filename, old, new, suite_file, extra, must_fail = MUTATIONS[name]
    before = hashes()
    target = copy_to(tmp_path).joinpath("model_interface", filename)
    source = target.read_text(encoding="utf-8")
    assert source.count(old) == 1, f"the text to break is no longer in {filename}"
    target.write_text(source.replace(old, new), encoding="utf-8")

    done = run_suite(tmp_path, [suite_file], extra)

    assert done.returncode == 1, done.stdout
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED ")]
    for test in must_fail:
        assert any(f"::{test}" in line for line in failed), f"{test} did not fail:\n{done.stdout}"
    after = hashes()
    print(f"\n{name}: {len(failed)} tests failed on the broken copy")
    for file in before:
        print(f"  {file}  before {before[file][:16]}  after {after[file][:16]}")
    assert after == before
