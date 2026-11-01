#!/usr/bin/env bash
# The Pi's log: the last 100 lines, then new lines as they come (Ctrl-C to stop).
# Pass a number for more history: scripts/logs.sh 500
set -euo pipefail
source "$(dirname "$0")/_pi.sh"
ssh -t "$PI" "tail -n ${1:-100} -F ~/thatha_tv/thatha_tv.log"
