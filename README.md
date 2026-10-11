# thatha_tv (Raspberry Pi + keypad remote)

Turns on the LG TV, opens the DStv app and tunes to a Live TV channel when
Thatha types the channel number on a wireless keypad plugged into the Pi.

## The remote to buy

A **wireless 2.4 GHz numeric keypad with a USB receiver** (sold as
"wireless numeric keypad" / "wireless number pad"). Look for:

- **2.4 GHz with a USB nano receiver, not Bluetooth.** No pairing, and it keeps
  working after battery changes. Bluetooth keypads go to sleep and often drop
  the first keypress.
- **Standalone numpad** with large, clearly printed digits and a big Enter key.
- **AA/AAA batteries** rather than a built-in rechargeable, so a flat battery is
  an easy swap.

It works through walls and doesn't need to be pointed at anything. Any
keyboard-like device works the same way (a full wireless keyboard, or a Flirc
USB receiver paired to a big-button IR remote), but the keypad is the simplest.

## Using it

- Type the channel number, e.g. **2 0 3**. It plays as soon as the third digit
  is pressed. For a shorter number, press **Enter**.
- Mistake? Press **Backspace**, **Esc** or **.** to start again. Half-typed
  numbers are forgotten after 5 seconds.
- The TV shows "Changing to 203... please wait". Changing takes about 45
  seconds; keys pressed meanwhile are ignored and the TV says "Please wait".
- An unknown number shows "Channel 999 is not set up" on the TV.

Print a card of the channels in `CHANNELS` (`live_tv.py`) to keep next to the keypad.

## Pi setup

Use Raspberry Pi OS Lite (Bookworm or later, Python 3.11+) on the same network
as the TV. Enable SSH in Raspberry Pi Imager when flashing.

```sh
sudo apt install -y git python3-venv
git clone https://github.com/neeland/thatha_tv.git ~/thatha_tv
cd ~/thatha_tv
git checkout raspberry-pi
./install.sh            # TV must be on the first time; accept the pairing prompt on screen
```

Then plug the keypad's USB receiver into the Pi. It's picked up automatically,
including after being unplugged and plugged back in.

`install.sh` creates the venv, pairs with the TV (writes the git-ignored
`.lgtv_client_key`), and installs a `thatha-tv` service that starts on boot and
restarts if it crashes. Re-run it after a `git pull`.

The TV IP and MAC are set at the top of `live_tv.py`, `remote.py` and `pair.py`.

## Managing the service

```sh
sudo systemctl status thatha-tv      # is it running?
journalctl -u thatha-tv -f           # live log: keypad found, each channel change
sudo systemctl restart thatha-tv     # after changing CHANNELS
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
Restart the service afterwards.
