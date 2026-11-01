#!/usr/bin/env bash
# Whether the service is running, which code it's on, what it thinks is playing, and the channels it has learned.
set -euo pipefail
source "$(dirname "$0")/_pi.sh"
ssh "$PI" 'cd ~/thatha_tv
echo "service: $(systemctl is-active thatha-tv), since $(systemctl show -p ActiveEnterTimestamp --value thatha-tv)"
echo "code:    $(git log --oneline -1)"
echo "playing: $(cat .last_watched 2>/dev/null || echo unknown) (tile $(cat .last_tile 2>/dev/null || echo unknown))"
echo "learned: $(tr -d "\n " < seen_tiles.json 2>/dev/null)"'
