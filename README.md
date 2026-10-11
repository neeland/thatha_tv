# thatha_tv (PC / Windows)

Turns on the LG TV, opens the DStv app and tunes to a Live TV channel.
The PC shows a full-screen remote with a big button for each channel number.
It is only reachable from the PC itself.

## Setup

Requires [Python 3.11+ for Windows](https://www.python.org/downloads/windows/).
With the TV on, run this once in PowerShell from the repo folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-shortcut.ps1 -Startup
```

It puts a **Thatha TV** icon in the top-right corner of the desktop, and with
`-Startup` also starts the remote automatically at sign-in. The first time the
icon runs it creates the venv, pairs with the TV (accept the prompt on the TV)
and asks you to choose an unlock PIN. Any problem (no Python, pairing failed,
server didn't start) is shown in a window that stays open until Enter is pressed.

`pair.py` writes `.lgtv_client_key`, which is git-ignored. The TV IP and MAC
are set at the top of `live_tv.py`, `remote.py` and `pair.py`.

## Running the remote

Double-click the **Thatha TV** desktop icon (or run `.\start.ps1`). It updates
to the latest version from GitHub (restarting the server if anything changed),
turns the TV on, starts the server in the background and locks the PC into the full-screen remote.
Clicking it again while it is running does nothing. Use `.\start.ps1 -NoKiosk`
to only start the server.

While a channel is changing, every button is locked (greyed out with a 🔒, and
the channel being tuned pulses orange) until the TV has finished. A change that
takes over two minutes is abandoned and the buttons unlock again.

### Kiosk mode (locking the PC to the remote)

The PC shows the remote in full-screen Edge with no address bar or tabs. If it
is closed (e.g. Alt+F4) it reopens within a second, and it is pulled back in
front if anything else opens on top. To save power the screen turns off
when idle (after 5 minutes by default); moving the mouse or tapping brings the
remote straight back. The PC never asks to sign in again and, plugged in, never
goes to standby, so the remote keeps running (`install-shortcut.ps1` sets this up).

**To unlock:** press and hold the "Thatha TV" title for 5 seconds, enter the
PIN on the number pad and tap OK. The remote closes and the PC works normally.
Click the desktop icon to lock it again. Three wrong PINs lock the pad for a
minute. The PIN is stored in `.unlock_pin`; delete that file and click the icon
to choose a new one. If the server stops, kiosk mode exits on its own after
about 10 seconds.

Ctrl+Alt+Del still works, so the PC can always be recovered.

## Command line

```powershell
.\.venv\Scripts\python live_tv.py        # default channel (203)
.\.venv\Scripts\python live_tv.py 201    # specific channel
```

## Adding a channel

Run `.\.venv\Scripts\python remote.py` to drive the TV from the keyboard
(arrows/WASD, Enter, `b` back, `h` home, `q` quit). It prints every key
pressed, so you can find a channel's position in Live TV > All channels and
add it to `CHANNELS` in `live_tv.py` as `(downs, rights)` counted from 101.
New channels appear on the website automatically after a restart.
