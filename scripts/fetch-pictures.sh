#!/usr/bin/env bash
# Copy the screenshots the Pi saves when it can't read something into ./pi-pictures/.
set -euo pipefail
source "$(dirname "$0")/_pi.sh"
mkdir -p pi-pictures
scp "$PI:thatha_tv/{unread_banner,unsettled_grid}.png" pi-pictures/ || true
ls -l pi-pictures
