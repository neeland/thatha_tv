#!/usr/bin/env bash
# Once per computer: copy this computer's SSH key to the Pi, so the other scripts don't ask for a login.
set -euo pipefail
source "$(dirname "$0")/_pi.sh"
ssh-copy-id "$PI"
