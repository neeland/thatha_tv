# thatha_tv (Raspberry Pi + big-button remote)

Turns on the LG TV, opens the DStv app and tunes to a Live TV channel when
Thatha presses a labelled button on a big-button remote.

## What to buy

1. **A big-button universal TV remote** ("big button remote" / "senior
   remote"). Pick one with at least as many large buttons as channels (6 now),
   so each one can carry a label. It must be a **universal/programmable** one
   so it can be set to a brand the LG TV ignores (see below).
2. **A Flirc USB receiver** (flirc.tv). It plugs into the Pi and turns any IR
   remote's buttons into key presses.
3. **Labels**: printed sticker labels or a label maker. Write the channel
   number big (e.g. "203") and the name small under it.

Put the Pi near the TV with the Flirc facing the room. Thatha points the
remote at the TV as usual and the Flirc picks it up.

## Setting up the remote

1. **Stop the remote controlling the LG TV.** Set it, using its manual's
   code-entry steps, to a TV brand the house doesn't have (e.g. Philips).
   If the LG TV still reacts to a button you plan to use, try another brand.
2. **Teach the Flirc the buttons.** Easiest on the Windows PC: install the
   Flirc app, plug in the Flirc, choose *Controllers > Full Keyboard*, then for
   each button you'll use: click a letter (A, B, C...) and press that remote
   button. The Flirc stores this itself, so it keeps working on the Pi.
3. **Label the buttons** with their channel numbers.

## Pi setup

Use Raspberry Pi OS Lite (Bookworm or later, Python 3.11+) on the same network
as the TV. Enable SSH in Raspberry Pi Imager when flashing.

```sh
sudo apt install -y git python3-venv
git clone https://github.com/neeland/thatha_tv.git ~/thatha_tv
cd ~/thatha_tv
git checkout raspberry-pi
./install.sh
```

With the Flirc plugged in, `install.sh`:

1. creates the venv,
2. pairs with the TV (turn it on and accept the prompt on screen),
3. runs `learn.py`, which asks for each channel's button in turn:
   press the labelled button for each one,
4. installs a `thatha-tv` service that starts on boot and restarts if it crashes.

`.lgtv_client_key` and `buttons.json` are git-ignored. Re-run `install.sh`
after a `git pull`. The TV IP and MAC are at the top of `live_tv.py`,
`remote.py` and `pair.py`.

## Using it

- Press a channel's button. The TV turns on if needed and shows
  "Changing to 203... please wait". It takes about 45 seconds.
- Buttons pressed while it's changing are ignored, and the TV says "Please wait".
- A button that isn't set up shows "That button is not set up".

## Changing which button does what

```sh
sudo systemctl stop thatha-tv
.venv/bin/python learn.py
sudo systemctl start thatha-tv
```

## Managing the service

```sh
sudo systemctl status thatha-tv      # is it running?
journalctl -u thatha-tv -f           # live log: receiver found, each button and channel change
```

## Command line

```sh
.venv/bin/python live_tv.py        # default channel (203)
.venv/bin/python live_tv.py 201    # specific channel
.venv/bin/python live_tv.py on     # just turn the TV on
```

## Adding a channel

Run `.venv/bin/python remote.py` over SSH to drive the TV from your keyboard
(arrows/WASD, Enter, `b` back, `h` home, `q` quit). It prints every key
pressed, so you can find a channel's position in Live TV > All channels and
add it to `CHANNELS` in `live_tv.py` as `(downs, rights)` counted from 101.
Then teach the Flirc a new button and re-run `learn.py`.
