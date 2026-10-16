"""The fixed timing reference of the gate (DEC-T06-GATE-TIME): tools/bench_reference.py. Its loop is deterministic,
and it imports nothing but time, so it measures the machine and not this repository."""
import ast
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[2].joinpath("tools", "bench_reference.py")
spec = importlib.util.spec_from_file_location("bench_reference", PATH)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_the_reference_loop_is_deterministic_and_imports_only_time():
    assert bench.work(10_000) == bench.work(10_000) == 335154  # worked out by the loop written out by hand
    assert bench.N == 12_000_000  # the size the recorded timings were taken with
    assert bench.work(bench.N) == 983797  # the full result the recorded timings printed, and timed_run.sh checks
    imported = {alias.name for node in ast.walk(ast.parse(PATH.read_text(encoding="utf-8")))
                if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    assert imported == {"time"}
