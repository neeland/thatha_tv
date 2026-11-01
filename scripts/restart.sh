#!/usr/bin/env bash
# Restart the remote service on the Pi (asks for the Pi's password for sudo).
set -euo pipefail
source "$(dirname "$0")/_pi.sh"
ssh -t "$PI" 'sudo systemctl restart thatha-tv && systemctl is-active thatha-tv'
