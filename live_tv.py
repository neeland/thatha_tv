import asyncio
import sys
import time
from pathlib import Path
from aiowebostv import WebOsClient
from wakeonlan import wake

TV_IP, TV_MAC = "192.168.10.232", "F4:14:BF:E7:D2:7C"
DSTV_ID = "com.multichoice.tvapp"
CLIENT_KEY = (Path(__file__).parent / ".lgtv_client_key").read_text().strip()
STATE_FILE = Path(__file__).parent / ".last_channel"   # channel we left playing, for fast switching
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

async def connect(step):
    """Connect right away if the TV is on; only wake it (and wait) if it isn't."""
    tv = WebOsClient(TV_IP, CLIENT_KEY, connect_timeout=3)
    try:
        await tv.connect()
        return tv, False
    except Exception:
        pass
    step("TV is off, waking it")
    power_on()
    for _ in range(15):
        tv = WebOsClient(TV_IP, CLIENT_KEY, connect_timeout=3)
        try:
            await tv.connect()
            return tv, True
        except Exception:
            await asyncio.sleep(2)
    raise RuntimeError("Could not reach the TV after waking it")

def grid_moves(src, dst):
    """Arrow presses that walk the All-channels highlight from one channel to another."""
    downs = CHANNELS[dst][0] - CHANNELS[src][0]
    rights = CHANNELS[dst][1] - CHANNELS[src][1]
    return (["DOWN" if downs > 0 else "UP"] * abs(downs) +
            ["RIGHT" if rights > 0 else "LEFT"] * abs(rights))

async def switch(tv, playing, channel):
    """DStv is already playing a known channel: BACK reopens the grid on it, so walk the difference."""
    await press(tv, ["BACK"], delay=3)
    await press(tv, grid_moves(playing, channel), delay=0.3)
    await press(tv, ["ENTER"])

async def cold_start(tv, channel, step):
    """Restart DStv so we always walk from the same screen, whatever state the app was in."""
    try:
        await tv.close_app(DSTV_ID); await asyncio.sleep(1.5)
    except Exception:
        pass                                              # wasn't running
    await tv.launch_app(DSTV_ID)
    for _ in range(15):                                   # wait only as long as DStv takes to come up
        await asyncio.sleep(1)
        if tv.tv_state.current_app_id == DSTV_ID:
            break
    step("DStv in foreground")
    await asyncio.sleep(5)                                # splash screen > profile screen
    await press(tv, ["ENTER"], delay=4)                   # Dad profile (assumed highlighted)
    step("profile chosen")
    await press(tv, ["LEFT", "DOWN", "DOWN", "ENTER"], delay=0.8)  # Live TV
    await asyncio.sleep(3.5)                              # let Live TV load
    await press(tv, ["RIGHT", "DOWN"], delay=0.8)         # (opens on Recently watched) > All channels > 101
    downs, rights = CHANNELS[channel]
    await press(tv, ["DOWN"] * downs + ["RIGHT"] * rights, delay=0.3)
    await press(tv, ["ENTER"])                            # play channel

async def main(channel):
    t0 = time.monotonic()
    def step(msg): print(f"[{time.monotonic() - t0:5.1f}s] {msg}")
    tv, was_off = await connect(step)
    step("connected")
    try:
        # Fast path: DStv still up from our last run, so hop from the playing channel to the new one.
        # After a wake the app restarts at the profile screen, so the remembered channel is useless.
        playing = STATE_FILE.read_text().strip() if STATE_FILE.exists() else None
        if not was_off and playing in CHANNELS and tv.tv_state.current_app_id == DSTV_ID:
            if playing == channel:
                step(f"already on {channel}")
                return
            await switch(tv, playing, channel)
            step(f"switched {playing} > {channel}")
        else:
            await cold_start(tv, channel, step)
            step(f"done, channel {channel}")
        STATE_FILE.write_text(channel + "\n")
    except BaseException:
        STATE_FILE.unlink(missing_ok=True)                # state unknown, next run starts fresh
        raise
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
