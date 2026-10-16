#!/bin/bash
# A timing aid for the T06 gate, not part of the harness: runs a command while watching the memory in use on the
# machine and the time it has run, and kills the command's whole process group if either passes its limit. Exits
# with the command's exit code (137 when the guard killed it).
# Usage: tools/memory_guard.sh COMMAND [ARGUMENT...]. The limits are MEMORY_GUARD_LIMIT_MB, 3000 unless set, and
# MEMORY_GUARD_MAX_SECONDS, the wall-clock time in seconds (a fraction is allowed), 110 unless set.
# Limit of this guard: the trigger is the memory in use on the whole machine, not the command's own. A spike in
# any other process can therefore stop a healthy command, and the output then says the guard stopped it. Only the
# command's own process group is ever killed. It fails closed: if the memory in use cannot be read, it does not
# start the command, or it stops it, says so, and exits with 125.
limit=${MEMORY_GUARD_LIMIT_MB:-3000}
max_seconds=${MEMORY_GUARD_MAX_SECONDS:-110}
[[ "$max_seconds" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( 10#${max_seconds/./} > 0 )) || {
  echo "STOPPED BY GUARD: MEMORY_GUARD_MAX_SECONDS is not a positive number of seconds: $max_seconds; the command was not started"; exit 125; }
max_us=$(awk -v s="$max_seconds" 'BEGIN { printf "%d", s * 1000000 }')
used() {  # the memory in use in MB, or nothing if it cannot be read
  local value
  value=$(free -m 2>/dev/null | awk '/^Mem:/{print $3}') || return 1
  [[ "$value" =~ ^[0-9]+$ ]] || return 1
  echo "$value"
}
start=$(used) || { echo "STOPPED BY GUARD: the memory in use cannot be read; the command was not started"; exit 125; }
# A background job of a script starts with Ctrl-C ignored. Put the default back before the command starts, so
# that a Ctrl-C sent to its process group still reaches it; setsid gives it a process group of its own.
setsid python3 -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp(sys.argv[1], sys.argv[1:])' "$@" &
pid=$!
began=${EPOCHREALTIME/./}
peak=$start
stopped=""
overran=""
while kill -0 "$pid" 2>/dev/null; do
  if ! now=$(used); then
    kill -KILL -- "-$pid" 2>/dev/null
    wait "$pid"
    echo "STOPPED BY GUARD: the memory in use cannot be read any more; the command was stopped"
    echo "exit=125  memory used: before $start MB, peak $peak MB (limit for stopping $limit MB)"
    exit 125
  fi
  (( now > peak )) && peak=$now
  if (( now > limit )); then
    kill -KILL -- "-$pid" 2>/dev/null
    stopped=$now
    break
  fi
  if (( ${EPOCHREALTIME/./} - began > max_us )); then
    kill -KILL -- "-$pid" 2>/dev/null
    overran=1
    break
  fi
  sleep 0.25
done
wait "$pid"
code=$?
[ -n "$stopped" ] && echo "STOPPED BY GUARD: memory used $stopped MB, above the limit of $limit MB"
[ -n "$overran" ] && echo "STOPPED BY GUARD: the command ran longer than the limit of $max_seconds s"
echo "exit=$code  memory used: before $start MB, peak $peak MB (limit for stopping $limit MB)"
exit "$code"
