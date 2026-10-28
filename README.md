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
3. installs a `thatha-tv` service that starts on boot and restarts if it crashes.

`.lgtv_client_key` is git-ignored. Re-run `install.sh`
after a `git pull`. The TV IP and MAC are at the top of `live_tv.py`,
`remote.py` and `pair.py`.

## The buttons

The Flirc is programmed (Flirc app, *Controllers > Full Keyboard*) so that:

| Remote button | Flirc key | Does |
|---|---|---|
| 1 2 3 4 5 6 7 8 9 0 | A B C D E F G H I J | channels, lowest first: 1 = 167, 2 = 201, 3 = 203, 4 = 204, 5 = 212, 6 = 213 |
| up arrow | Volume Up | volume up (hold to keep going) |
| down arrow | Volume Down | volume down |
| on/off | Home | TV off if it's on, on if it's off |

The remote is set (SETUP + a code) to a TV brand the LG ignores, so only the
Pi acts on it. Number buttons with no channel yet show "That button is not set
up". The service log lists which button goes to which channel when it starts.

## Using it

- Press a channel's button. The TV turns on if needed and counts down with
  "⏳ CHANGING TO CHANNEL 203 · PLEASE WAIT 9 SECONDS ⏳" messages. If DStv is
  already playing a channel the Pi tuned, it takes about 10 seconds; otherwise
  (TV was off, or DStv was used by hand) it restarts DStv first, about 40.
- Channel and on/off buttons pressed while it's changing are ignored, and the
  TV says "Please wait". Volume works any time.
- A button that isn't set up shows "That button is not set up".

Every step waits for the TV screen to show what it expects (the TV takes a
screenshot in about 0.1s, see `screen.py`): keys are only sent once the
channel grid has a highlighted tile, because keys sent while it's still
opening can hang the DStv app. The channel number on the player banner is read
back to confirm the change, and a wrong landing is corrected with a second
hop. `.last_channel` holds the channel last seen playing.

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
Number buttons go to channels in order, so a new channel shifts the ones
above it to the next button: relabel them.
If its banner has a digit `screen.py` can't read yet, `live_tv.py` saves the
frame to `unread_banner.png`; add the digit's shape to `DIGITS` in `screen.py`.
