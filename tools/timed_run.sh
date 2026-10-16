#!/bin/bash
# A timing aid for the T06 gate, not part of the harness: checks that the machine is fit for a timed run, then
# runs the command under tools/memory_guard.sh. Without starting the command, it refuses with exit code 2 unless
# all of these hold: the charger check says exactly "Power: plugged in"; the fixed benchmark exits with 0, prints
# N=12000000 and result 983797, and takes no longer than BENCH_MAX_S seconds.
# Usage: tools/timed_run.sh [--unchecked] COMMAND [ARGUMENT...]
# --unchecked runs the command even when a check fails, and marks the output "UNCHECKED TIMING": a time taken
# that way is not to be recorded as a gate timing.
# Settings: BENCH_MAX_S, 1.2 unless set. For the tests only: TIMED_RUN_POWER_PATH, the charger file to read, and
# TIMED_RUN_BENCH, a command to run instead of the benchmark. Either one, when set, means the real checks were not
# made, so its use always prints "UNCHECKED TIMING"; the checks still refuse as usual.
here=$(cd "$(dirname "$0")" && pwd)
max=${BENCH_MAX_S:-1.2}
unchecked=""
if [ "$1" = "--unchecked" ]; then
  unchecked=1
  shift
  echo "UNCHECKED TIMING: the checks below do not stop this run"
fi
failed() {  # refuse, or with --unchecked say what failed and go on
  if [ -n "$unchecked" ]; then echo "UNCHECKED TIMING: $1"; else echo "REFUSED: $1"; exit 2; fi
}
if [ -n "$TIMED_RUN_POWER_PATH" ]; then
  echo "UNCHECKED TIMING: TIMED_RUN_POWER_PATH is set, so the charger state is read from $TIMED_RUN_POWER_PATH, not from the machine"
fi
if [ -n "$TIMED_RUN_BENCH" ]; then
  echo "UNCHECKED TIMING: TIMED_RUN_BENCH is set, so the fixed benchmark is not run"
fi

power=$("$here/power_check.sh" ${TIMED_RUN_POWER_PATH:+"$TIMED_RUN_POWER_PATH"})
echo "$power"
if [ "$power" = "Power: ON BATTERY" ]; then
  failed "on battery; plug the charger in"
elif [ "$power" != "Power: plugged in" ]; then
  failed "the charger is not confirmed in: $power"
fi

if [ -n "$TIMED_RUN_BENCH" ]; then bench=$(bash -c "$TIMED_RUN_BENCH"); else bench=$(python3 -I "$here/bench_reference.py"); fi
code=$?
echo "$bench"
seconds=$(sed -n 's/^benchmark: \([0-9.]*\) s (N=12000000, result 983797)$/\1/p' <<< "$bench")
if [ "$code" != 0 ]; then
  failed "the benchmark failed with exit code $code"
elif ! grep -q '(N=12000000, result 983797)$' <<< "$bench"; then
  failed "the benchmark did not print N=12000000 and result 983797: it is not the recorded reference"
elif [ -z "$seconds" ]; then
  failed "the benchmark printed no time"
elif awk -v s="$seconds" -v m="$max" 'BEGIN { exit !(s > m) }'; then
  failed "the benchmark took $seconds s, above BENCH_MAX_S=$max s: the machine is slower than when the recorded timings were taken"
fi

exec "$here/memory_guard.sh" "$@"
