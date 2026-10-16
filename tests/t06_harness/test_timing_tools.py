"""The timing aids of the gate, tools/power_check.sh and tools/memory_guard.sh. They are not part of the harness.
These tests use harmless dummy processes only and never point the guard at the suite."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2].joinpath("tools")
POWER, GUARD = str(TOOLS.joinpath("power_check.sh")), str(TOOLS.joinpath("memory_guard.sh"))
FAR_ABOVE = {**os.environ, "MEMORY_GUARD_LIMIT_MB": "100000"}  # a limit the dummy processes can never reach


def memory_used_mb():
    """Memory in use on the machine, read the same way as the guard reads it."""
    done = subprocess.run(["free", "-m"], capture_output=True, text=True, check=True)
    return int(next(line for line in done.stdout.split("\n") if line.startswith("Mem:")).split()[2])


def test_the_power_check_says_plugged_in_on_battery_or_unknown(tmp_path):
    online = tmp_path.joinpath("online")
    said = lambda: subprocess.run([POWER, str(online)], capture_output=True, text=True).stdout.strip()
    online.write_text("1\n")
    assert said() == "Power: plugged in"
    online.write_text("0\n")
    assert said() == "Power: ON BATTERY"
    online.unlink()
    assert said() == f"Power: unknown ({online} not readable)"


def test_the_guard_passes_a_process_through_and_returns_its_exit_code():
    done = subprocess.run([GUARD, sys.executable, "-c", "import sys; print('hello'); sys.exit(7)"],
                          capture_output=True, text=True, env=FAR_ABOVE, timeout=10)
    assert done.returncode == 7
    lines = done.stdout.strip().split("\n")
    assert lines[0] == "hello" and lines[1].startswith("exit=7  memory used: before ") and "STOPPED" not in done.stdout


def test_the_guard_kills_a_process_that_takes_memory_past_a_low_limit_and_says_so():
    limit = memory_used_mb() + 50  # a low limit, just above what is in use now
    begun = time.monotonic()
    done = subprocess.run([GUARD, sys.executable, "-c", "import time; block = bytearray(150 << 20); time.sleep(20)"],
                          capture_output=True, text=True, env={**os.environ, "MEMORY_GUARD_LIMIT_MB": str(limit)},
                          timeout=10)
    assert time.monotonic() - begun < 5  # killed long before its 20-second sleep ended
    assert done.returncode == 137  # 128 + SIGKILL
    assert "STOPPED BY GUARD: memory used " in done.stdout and f"above the limit of {limit} MB" in done.stdout
    assert "exit=137  memory used: before " in done.stdout



def test_the_guard_kills_a_process_that_runs_past_the_time_limit_and_says_so():
    begun = time.monotonic()
    done = subprocess.run([GUARD, "sleep", "30"], capture_output=True, text=True,
                          env={**FAR_ABOVE, "MEMORY_GUARD_MAX_SECONDS": "0.3"}, timeout=10)
    assert time.monotonic() - begun < 1  # stopped at the 0.3-second limit, long before its 30-second sleep ended
    assert done.returncode == 137  # 128 + SIGKILL, as for the memory limit
    assert "STOPPED BY GUARD: the command ran longer than the limit of 0.3 s" in done.stdout
    assert "exit=137  memory used: before " in done.stdout

def test_a_memory_spike_in_an_unrelated_process_stops_the_guarded_command_and_the_output_says_so():
    """The limit of the guard (stated in its header): its trigger is the memory in use on the whole machine."""
    limit = memory_used_mb() + 50
    guard = subprocess.Popen([GUARD, sys.executable, "-c", "import time; time.sleep(20)"],  # takes no memory itself
                             stdout=subprocess.PIPE, text=True, env={**os.environ, "MEMORY_GUARD_LIMIT_MB": str(limit)})
    hog = subprocess.Popen([sys.executable, "-c", "import time; block = bytearray(150 << 20); time.sleep(20)"])
    try:  # the hog is not guarded: it is another process, in another process group
        said, _ = guard.communicate(timeout=10)
        assert guard.returncode == 137 and "STOPPED BY GUARD: memory used " in said and f"above the limit of {limit} MB" in said
        assert hog.poll() is None  # the guard killed its own command only, never the unrelated process
    finally:
        hog.kill()
        hog.wait()
        if guard.poll() is None:
            guard.kill()


FREE_THAT_FAILS = """#!/bin/bash
# a stand-in for free: it answers like the real one for the first ANSWERS calls, then fails
count=$(cat "$0.count" 2>/dev/null || echo 0); echo $((count + 1)) > "$0.count"
if (( count < ANSWERS )); then
  echo "              total        used        free"
  echo "Mem:           3619        1500        2000"
  exit 0
fi
exit 1
"""


def test_the_guard_fails_closed_when_the_memory_in_use_cannot_be_read(tmp_path):
    marker = tmp_path.joinpath("the command ran")
    command = [GUARD, sys.executable, "-c", f"import time; open({str(marker)!r}, 'w').close(); time.sleep(20)"]
    for answers, started in ((0, False), (2, True)):  # no reading at all; a reading that fails while running
        fake = tmp_path.joinpath(f"bin-{answers}")
        fake.mkdir()
        fake.joinpath("free").write_text(FREE_THAT_FAILS.replace("ANSWERS", str(answers)))
        fake.joinpath("free").chmod(0o755)
        marker.unlink(missing_ok=True)
        done = subprocess.run(command, capture_output=True, text=True, timeout=10,
                              env={**FAR_ABOVE, "PATH": f"{fake}:{os.environ['PATH']}"})
        assert done.returncode == 125, done.stdout  # never 0: a guard that cannot watch does not pass the run
        if started:
            assert "STOPPED BY GUARD: the memory in use cannot be read any more; the command was stopped" in done.stdout
        else:
            assert done.stdout == "STOPPED BY GUARD: the memory in use cannot be read; the command was not started\n"
            assert not marker.exists()

CHILD = """
import os, sys, time
print("ready", os.getpgid(0), flush=True)
try:
    time.sleep(20)
except KeyboardInterrupt:
    print("KeyboardInterrupt reached the child", flush=True)
    sys.exit(3)
"""


def test_ctrl_c_sent_to_the_guarded_process_group_reaches_the_child():
    guard = subprocess.Popen([GUARD, sys.executable, "-c", CHILD], stdout=subprocess.PIPE, text=True, env=FAR_ABOVE)
    try:
        word, group = guard.stdout.readline().split()
        assert word == "ready" and int(group) != os.getpgid(0)  # the child has a process group of its own
        os.killpg(int(group), signal.SIGINT)  # as Ctrl-C in a terminal would
        rest, _ = guard.communicate(timeout=10)
    finally:
        if guard.poll() is None:
            guard.kill()
    assert guard.returncode == 3 and rest.startswith("KeyboardInterrupt reached the child\n")
    assert "exit=3  memory used: before " in rest


# ---- tools/timed_run.sh: refuses an unfit machine, otherwise runs the command under the guard

TIMED = str(TOOLS.joinpath("timed_run.sh"))
HEALTHY = "echo 'benchmark: 0.780 s (N=12000000, result 983797)'"


def marks(tmp_path):
    """The two lines timed_run.sh prints first whenever these tests use its two test overrides."""
    return [f"UNCHECKED TIMING: TIMED_RUN_POWER_PATH is set, so the charger state is read from {tmp_path.joinpath('online')},"
            " not from the machine", "UNCHECKED TIMING: TIMED_RUN_BENCH is set, so the fixed benchmark is not run"]


def timed(tmp_path, online, bench=HEALTHY, flags=(), **settings):
    """Run timed_run.sh with a fake charger file (None: no file at all) and a dummy benchmark command. The command
    only leaves a marker file and exits 5. Returns (what it printed, its exit code, whether the command ran)."""
    power = tmp_path.joinpath("online")
    power.unlink(missing_ok=True)
    if online is not None:
        power.write_text(online)
    marker = tmp_path.joinpath("the command ran")
    marker.unlink(missing_ok=True)
    environment = {**os.environ, "MEMORY_GUARD_LIMIT_MB": "100000", "TIMED_RUN_POWER_PATH": str(power),
                   "TIMED_RUN_BENCH": bench}
    environment.pop("BENCH_MAX_S", None)  # the default, whatever this shell has set
    environment.update(settings)
    done = subprocess.run([TIMED, *flags, sys.executable, "-c", f"import sys; open({str(marker)!r}, 'w').close(); sys.exit(5)"],
                          capture_output=True, text=True, env=environment, timeout=10)
    return done.stdout, done.returncode, marker.exists()


def test_timed_run_refuses_on_battery_before_the_benchmark_and_the_command(tmp_path):
    said, code, ran = timed(tmp_path, "0\n")
    assert code == 2 and not ran
    assert said.split("\n") == [*marks(tmp_path), "Power: ON BATTERY", "REFUSED: on battery; plug the charger in", ""]


def test_timed_run_refuses_an_unknown_charger_state(tmp_path):
    said, code, ran = timed(tmp_path, None)  # no charger file: the state cannot be read
    assert code == 2 and not ran
    assert said.split("\n")[2].startswith("Power: unknown (") and "REFUSED: the charger is not confirmed in: Power: unknown" in said
    said, code, ran = timed(tmp_path, "2\n")  # nor any value other than 1
    assert code == 2 and not ran and "REFUSED: the charger is not confirmed in" in said


def test_timed_run_refuses_a_slow_benchmark_and_the_limit_is_a_setting(tmp_path):
    said, code, ran = timed(tmp_path, "1\n", "echo 'benchmark: 1.628 s (N=12000000, result 983797)'")
    assert code == 2 and not ran
    assert said.split("\n")[2:4] == ["Power: plugged in", "benchmark: 1.628 s (N=12000000, result 983797)"]
    assert "REFUSED: the benchmark took 1.628 s, above BENCH_MAX_S=1.2 s" in said
    said, code, ran = timed(tmp_path, "1\n", "echo 'benchmark: 1.000 s (N=12000000, result 983797)'", BENCH_MAX_S="0.9")
    assert code == 2 and not ran and "above BENCH_MAX_S=0.9 s" in said  # the limit is BENCH_MAX_S when it is set
    said, code, ran = timed(tmp_path, "1\n", "echo 'benchmark: no time s (N=12000000, result 983797)'")
    assert code == 2 and not ran and "REFUSED: the benchmark printed no time" in said


def test_timed_run_refuses_a_benchmark_that_fails_or_is_not_the_reference(tmp_path):
    said, code, ran = timed(tmp_path, "1\n", HEALTHY + "; exit 1")  # a good-looking line, but it failed
    assert code == 2 and not ran and "REFUSED: the benchmark failed with exit code 1" in said
    said, code, ran = timed(tmp_path, "1\n", "echo 'benchmark: 0.780 s (N=12000000, result 1)'")  # the wrong result
    assert code == 2 and not ran and "REFUSED: the benchmark did not print N=12000000 and result 983797" in said
    said, code, ran = timed(tmp_path, "1\n", "echo 'benchmark: 0.010 s (N=1000, result 983797)'")  # another size
    assert code == 2 and not ran and "did not print N=12000000 and result 983797" in said


def test_timed_run_on_a_fit_machine_runs_the_command_under_the_guard(tmp_path):
    said, code, ran = timed(tmp_path, "1\n")
    assert code == 5 and ran  # the command ran, and its exit code came back through the guard
    lines = said.strip().split("\n")
    assert lines[2:4] == ["Power: plugged in", "benchmark: 0.780 s (N=12000000, result 983797)"]
    assert lines[4].startswith("exit=5  memory used: before ") and "REFUSED" not in said
    assert lines[:2] == marks(tmp_path)  # the overrides of this test are marked, even on a fit machine


def test_each_test_override_alone_marks_the_timing_unchecked(tmp_path):
    tmp_path.joinpath("online").write_text("0\n")  # on battery: refused before the real benchmark would run
    clean = {key: item for key, item in os.environ.items() if not key.startswith("TIMED_RUN_")}
    for name, value in (("TIMED_RUN_POWER_PATH", str(tmp_path.joinpath("online"))), ("TIMED_RUN_BENCH", HEALTHY)):
        done = subprocess.run([TIMED, "true"], capture_output=True, text=True, timeout=10,
                              env={**clean, "MEMORY_GUARD_LIMIT_MB": "100000", name: value})
        assert done.stdout.split("\n")[0].startswith(f"UNCHECKED TIMING: {name} is set"), (name, done.stdout)
        assert sum(line.startswith("UNCHECKED TIMING:") for line in done.stdout.split("\n")) == 1  # this one alone


def test_the_override_runs_the_command_and_marks_the_timing_unchecked(tmp_path):
    said, code, ran = timed(tmp_path, "0\n", "echo 'benchmark: 1.628 s (N=12000000, result 1)'", flags=["--unchecked"])
    assert code == 5 and ran and "REFUSED" not in said
    lines = said.strip().split("\n")
    assert lines[0] == "UNCHECKED TIMING: the checks below do not stop this run"
    assert "UNCHECKED TIMING: on battery; plug the charger in" in lines
    assert "UNCHECKED TIMING: the benchmark did not print N=12000000 and result 983797: it is not the recorded reference" in lines
    assert lines[-1].startswith("exit=5  memory used: before ")
