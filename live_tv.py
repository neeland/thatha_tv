import asyncio
import sys
import time
from pathlib import Path
from aiowebostv import WebOsClient
from wakeonlan import wake

TV_IP, TV_MAC = "192.168.10.232", "F4:14:BF:E7:D2:7C"
DSTV_ID = "com.multichoice.tvapp"
HOME_ID = "com.webos.app.home"
CLIENT_KEY = (Path(__file__).parent / ".lgtv_client_key").read_text().strip()
DEFAULT_CHANNEL = "203"

# Position in Live TV > All channels, counted from 101 (grid is 4 wide): (downs, rights)
CHANNELS = {
    "167": (9, 1),
    "201": (15, 1),
    "203": (15, 3),
    "204": (16, 0),
    "212": (18, 0),
    "213": (18, 1),
}

def power_on():
    """Wake the TV over the network (does nothing if it's already on). Sent a few times as Wi-Fi can drop one.

    macOS can refuse the global broadcast address, so each send is tried on its own.
    """
    for _ in range(3):
        for host in ("255.255.255.255", TV_IP.rsplit(".", 1)[0] + ".255", TV_IP):
            try:
                wake(TV_MAC, host=host)
            except OSError:
                pass
        time.sleep(0.5)

async def press(tv, keys, delay=1):
    for key in keys:
        await tv.button(key); await asyncio.sleep(delay)

async def go_home(tv, attempts=3):
    for _ in range(attempts):
        await press(tv, ["HOME"], delay=2)
        if tv.tv_state.current_app_id == HOME_ID:
            return
    raise RuntimeError(f"Could not reach Home screen (TV is on {tv.tv_state.current_app_id!r})")

async def main(channel):
    power_on(); await asyncio.sleep(8)
    tv = WebOsClient(TV_IP, CLIENT_KEY, connect_timeout=15)
    await tv.connect()
    try:
        await go_home(tv)                                 # always start from Home, whatever is on screen
        try:                                              # restart DStv so we always start from the same screen
            await tv.close_app(DSTV_ID); await asyncio.sleep(3)
        except Exception:
            pass                                          # wasn't running
        await tv.launch_app(DSTV_ID); await asyncio.sleep(10)  # DStv
        await press(tv, ["ENTER"], delay=5)               # Dad profile (assumed highlighted)
        await press(tv, ["LEFT", "DOWN", "DOWN", "ENTER"]) # Live TV
        await asyncio.sleep(5)                            # let Live TV load
        await press(tv, ["RIGHT", "DOWN"])                # (opens on Recently watched) > All channels > 101
        downs, rights = CHANNELS[channel]
        await press(tv, ["DOWN"] * downs + ["RIGHT"] * rights, delay=0.5)
        await press(tv, ["ENTER"])                        # play channel
    finally:
        await tv.disconnect()

if __name__ == "__main__":
    if sys.argv[1:] == ["on"]:
        sys.exit(power_on())
    channel = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CHANNEL
    if channel not in CHANNELS:
        sys.exit(f"Unknown channel {channel!r}, choose from: {', '.join(CHANNELS)}")
    try:
        asyncio.run(main(channel))
    except RuntimeError as err:
        sys.exit(str(err))
