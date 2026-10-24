# thatha_tv (Mac)

CLI testbed for driving the LG TV into a DStv Live TV channel. The flow gets
refined here, then lands on the `raspberry-pi` branch where a remote triggers it.

## Setup

Requires Python 3.11+. With the TV on, run once from the repo folder:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python pair.py        # accept the prompt on the TV
```

`pair.py` writes `.lgtv_client_key`, which is git-ignored. The TV IP and MAC
are set at the top of `live_tv.py`, `remote.py` and `pair.py`.

## Usage

```sh
.venv/bin/python live_tv.py        # default channel (203)
.venv/bin/python live_tv.py 201    # specific channel
.venv/bin/python live_tv.py on     # just turn the TV on
```

## Adding a channel

Run `.venv/bin/python remote.py` to drive the TV from the keyboard
(arrows/WASD, Enter, `b` back, `h` home, `q` quit). It prints every key
pressed, so you can find a channel's position in Live TV > All channels and
add it to `CHANNELS` in `live_tv.py` as `(downs, rights)` counted from 101.
