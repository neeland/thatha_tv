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

On first run it creates the venv and pairs with the TV if needed, then prints
the address to open on the iPad (e.g. `http://192.168.10.50:8000`). In Safari,
use Share > **Add to Home Screen** so it opens like an app.

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
