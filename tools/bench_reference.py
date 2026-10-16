"""The fixed timing reference of the T06 gate (DEC-T06-GATE-TIME): the same pure-Python loop every time.

It imports nothing from this repository. Run `python3 -I tools/bench_reference.py` just before a timed run of the
gate, with the charger state. On the build machine it takes about 0.77 to 0.82 s with the charger in.
"""
import time

N = 12_000_000


def work(n):
    total = 0
    for i in range(n):
        total = (total + i * i) % 1_000_003
    return total


if __name__ == "__main__":
    begun = time.perf_counter()
    result = work(N)
    print(f"benchmark: {time.perf_counter() - begun:.3f} s (N={N}, result {result})")
