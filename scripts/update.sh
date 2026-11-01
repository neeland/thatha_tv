#!/usr/bin/env bash
# Pull the latest code on the Pi and restart the remote service on it (asks for the Pi's password for sudo).
set -euo pipefail
source "$(dirname "$0")/_pi.sh"
ssh -t "$PI" 'cd ~/thatha_tv && git pull && sudo systemctl restart thatha-tv && systemctl is-active thatha-tv && git log --oneline -1'
