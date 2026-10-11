# thatha_tv (PC / Windows)

Turns on the LG TV, opens the DStv app and tunes to a Live TV channel.
A small website on the PC shows a big button for each channel number, so it
can be driven from an iPad on the same Wi-Fi.

## Setup (PowerShell)

Requires [Python 3.11+ for Windows](https://www.python.org/downloads/windows/)
(tick "Add python.exe to PATH" when installing). Run these in PowerShell from the repo folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python pair.py      # TV must be on; accept the prompt on screen
```

`pair.py` writes `.lgtv_client_key`, which is git-ignored. The TV IP and MAC
are set at the top of `live_tv.py`, `remote.py` and `pair.py`.

Allow the website through Windows Firewall (run PowerShell as Administrator, once):

```powershell
New-NetFirewallRule -DisplayName "Thatha TV" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```

Your home Wi-Fi must be set to a **Private** network in Windows settings.

## Running the website

```powershell
.\start.ps1
```

On first run it creates the venv, pairs with the TV if needed and asks you to
choose an unlock PIN. It starts the server in the background, prints the
address to open on the iPad (e.g. `http://192.168.10.50:8000`), then locks the
PC into the full-screen remote. Use `.\start.ps1 -NoKiosk` to only start the server. In Safari,
use Share > **Add to Home Screen** so it opens like an app.

While a channel is changing, every button is locked (greyed out with a 🔒, and
the channel being tuned pulses orange) on every device viewing the page, until
the TV has finished. A change that takes over two minutes is abandoned and the
buttons unlock again.

### Kiosk mode (locking the PC to the remote)

The PC shows the remote in full-screen Edge with no address bar or tabs. If it
is closed (e.g. Alt+F4) it reopens within a second, and it is pulled back in
front if anything else opens on top.

**To unlock:** press and hold the "Thatha TV" title for 5 seconds, enter the
PIN on the number pad and tap OK. The remote closes and the PC works normally;
the iPad keeps working. Run `.\start.ps1` again to lock it. Three wrong PINs
lock the pad for a minute. The PIN is stored in `.unlock_pin`; delete that
file and rerun `start.ps1` to choose a new one. If the server stops, kiosk
mode exits on its own after about 10 seconds.

Ctrl+Alt+Del still works, so the PC can always be recovered. To start the
remote automatically at sign-in, put a shortcut to
`powershell -ExecutionPolicy Bypass -File <repo>\start.ps1` in `shell:startup`.

If PowerShell blocks the script, allow local scripts once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

The PC must be on and awake for the iPad to work. Set Windows to never sleep
while plugged in, or the website will be unreachable.

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
