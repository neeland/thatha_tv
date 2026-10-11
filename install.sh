#!/usr/bin/env bash
# Sets up the venv, pairs with the TV and maps the remote's buttons if needed,
# then runs the listener as a service that starts when the Pi boots.
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"

python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

if [ ! -f .lgtv_client_key ]; then
    echo "No TV key found - pairing now. Turn the TV on and accept the prompt on screen."
    .venv/bin/python pair.py
fi

if [ ! -f buttons.json ]; then
    sudo systemctl stop thatha-tv 2>/dev/null || true
    echo "Now set up the remote's buttons (point it at the Flirc receiver)."
    .venv/bin/python learn.py
fi

sudo tee /etc/systemd/system/thatha-tv.service > /dev/null <<UNIT
[Unit]
Description=Thatha TV remote
Wants=network-online.target
After=network-online.target

[Service]
User=$(whoami)
SupplementaryGroups=input
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/buttons.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now thatha-tv
sudo systemctl restart thatha-tv

echo "Remote running. Press a channel button to try it."
