#!/usr/bin/env bash
# Change the TV's channel through the Pi, as the remote would: scripts/channel.sh 212
# Also: up, down (CH+/CH-), on (wake the TV). Don't press the remote while it runs.
set -euo pipefail
source "$(dirname "$0")/_pi.sh"
ssh "$PI" "cd ~/thatha_tv && .venv/bin/python live_tv.py ${1:?give a channel number, up, down or on}"
