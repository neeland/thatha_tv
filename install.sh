#!/usr/bin/env bash
# Sets up the venv, pairs with the TV if needed, and runs the keypad listener
# as a service that starts when the Pi boots.
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"

python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

if [ ! -f .lgtv_client_key ]; then
    echo "No TV key found - pairing now. Turn the TV on and accept the prompt on screen."
    .venv/bin/python pair.py
fi

sudo tee /etc/systemd/system/thatha-tv.service > /dev/null <<UNIT
[Unit]
Description=Thatha TV keypad
Wants=network-online.target
After=network-online.target

[Service]
User=$(whoami)
SupplementaryGroups=input
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/keypad.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now thatha-tv
sudo systemctl restart thatha-tv

echo "Keypad listener running. Plug in the keypad's USB receiver and type a channel number."
