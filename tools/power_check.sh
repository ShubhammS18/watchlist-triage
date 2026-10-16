#!/bin/bash
# A timing aid for the T06 gate, not part of the harness: prints whether the charger is in, as WSL reports it.
# Usage: tools/power_check.sh [PATH]. PATH is /sys/class/power_supply/AC1/online unless given (the tests give a
# fake one).
path=${1:-/sys/class/power_supply/AC1/online}
online=$(cat "$path" 2>/dev/null)
case "$online" in
  1) echo "Power: plugged in" ;;
  0) echo "Power: ON BATTERY" ;;
  *) echo "Power: unknown ($path not readable)" ;;
esac
