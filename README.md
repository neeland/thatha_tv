# thatha_tv (Raspberry Pi)

Turns on the LG TV, opens the DStv app and tunes to a Live TV channel.
It runs on a Raspberry Pi and is triggered from an iPad with Apple Shortcuts
over SSH: one Home Screen icon per channel.

## Pi setup

Use Raspberry Pi OS (Bookworm or later, Python 3.11+) on the same network as the TV.
Enable SSH in Raspberry Pi Imager when flashing, or later with `sudo raspi-config`.

```sh
git clone https://github.com/neeland/thatha_tv.git ~/thatha_tv
cd ~/thatha_tv
git checkout raspberry-pi
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python pair.py      # TV must be on; accept the prompt on screen
.venv/bin/python live_tv.py   # test: should tune to channel 203
```

`pair.py` writes `.lgtv_client_key`, which is git-ignored. The TV IP and MAC
are set at the top of `live_tv.py`, `remote.py` and `pair.py`.

Give the Pi a fixed IP address (a DHCP reservation in your router) so the
iPad shortcuts keep working.

## iPad shortcuts

For each channel, in the Shortcuts app:

1. New Shortcut, then add the **Run Script Over SSH** action.
2. Host: the Pi's IP. Port: 22. User: your Pi username. Authentication: password,
   or SSH key (tap it to copy the public key into `~/.ssh/authorized_keys` on the Pi).
3. Script: `~/thatha_tv/.venv/bin/python ~/thatha_tv/live_tv.py 203`
4. Name it after the channel and choose an icon, then Share > **Add to Home Screen**.

Changing the channel takes about 45 seconds.

## Command line

```sh
.venv/bin/python live_tv.py        # default channel (203)
.venv/bin/python live_tv.py 201    # specific channel
```

## Adding a channel

Run `.venv/bin/python remote.py` (over SSH works) to drive the TV from the
keyboard (arrows/WASD, Enter, `b` back, `h` home, `q` quit). It prints every
key pressed, so you can find a channel's position in Live TV > All channels and
add it to `CHANNELS` in `live_tv.py` as `(downs, rights)` counted from 101.
Then add a matching shortcut on the iPad.
