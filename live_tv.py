import asyncio
import sys
import time
from pathlib import Path
from aiowebostv import WebOsClient
from PIL import Image
from wakeonlan import wake
from screen import Screen, banner_channel, classify

TV_IP, TV_MAC = "192.168.10.232", "F4:14:BF:E7:D2:7C"
DSTV_ID = "com.multichoice.tvapp"
CLIENT_KEY = (Path(__file__).parent / ".lgtv_client_key").read_text().strip()
STATE_FILE = Path(__file__).parent / ".last_channel"   # channel last seen playing, for fast switching
UNREAD_BANNER = Path(__file__).parent / "unread_banner.png"  # saved when the banner has digits we can't read yet
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

async def toast(tv, message):
    """Pop-up message on the TV, so whoever is watching knows what's happening."""
    try:
        await tv.send_message(message)
    except Exception:
        pass                                              # only a nicety, never worth failing over

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
        except Exception as err:
            last = err
            await asyncio.sleep(2)
    raise RuntimeError(f"Could not reach the TV at {TV_IP} after waking it: {last!r}")

def grid_moves(src, dst):
    """Arrow presses that walk the All-channels highlight from one channel to another."""
    downs = CHANNELS[dst][0] - CHANNELS[src][0]
    rights = CHANNELS[dst][1] - CHANNELS[src][1]
    return (["DOWN" if downs > 0 else "UP"] * abs(downs) +
            ["RIGHT" if rights > 0 else "LEFT"] * abs(rights))

async def walk(scr, keys, channel):
    """Move the grid highlight and play the channel.

    Only called once the grid is up and highlighting a tile: keys sent while it is still
    opening hang the app. From there a steady pace is fine. The grid keeps the highlighted row
    at the top, so only the column can be checked here; the banner confirms the rest.
    """
    for key in keys:
        await scr.tv.button(key); await asyncio.sleep(0.3)
    focus = await scr.settled_grid()
    if focus[1] != CHANNELS[channel][1]:
        raise RuntimeError(f"Grid highlight ended on {focus}, expected column {CHANNELS[channel][1]} for {channel}")
    await scr.tv.button("ENTER")

class Countdown:
    """'Please wait' toasts while the channel changes. The TV shows one toast at a time for about
    3 seconds and queues the rest, so a new one goes in every 3 seconds, and only while it will
    still be true when it appears. Toasts are LG's grey box (no icons on this TV), so capitals
    and the colour hourglass emoji are what make it stand out; short enough to stay one line."""
    SHOWN_FOR = 3

    def __init__(self, tv, channel, seconds):
        self.task = asyncio.ensure_future(self.run(tv, channel, seconds))

    async def run(self, tv, channel, seconds):
        remaining, first = seconds, True
        while remaining > self.SHOWN_FOR:
            text = (f"⏳  CHANGING TO CHANNEL {channel} · PLEASE WAIT {round(remaining)} SECONDS  ⏳" if first
                    else f"⏳  CHANNEL {channel} IN {round(remaining)} SECONDS  ⏳")
            try:
                await tv.request("system.notifications/createToast", {"message": text})
            except Exception:
                return                                    # a message is a nicety, never a reason to fail
            first = False
            await asyncio.sleep(self.SHOWN_FOR); remaining -= self.SHOWN_FOR

    def stop(self):
        self.task.cancel()

async def switch(scr, playing, channel, step):
    """DStv is already playing a known channel: BACK reopens the grid on it, so walk the difference."""
    for _ in range(100):                                  # BACK is ignored while the stream is starting,
        kind, _ = classify(await scr.grab())              # and untested with the banner up: wait both out
        if kind not in ("player", "loading"):
            break
        await asyncio.sleep(0.1)
    await scr.tv.button("BACK")
    focus, _ = await scr.wait_for("grid", 6)
    if focus[1] != CHANNELS[playing][1]:
        raise RuntimeError(f"Grid opened on column {focus[1]}, but {playing} is in column {CHANNELS[playing][1]}")
    step("grid ready")
    await walk(scr, grid_moves(playing, channel), channel)

async def cold_start(tv, scr, channel, step):
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
    await press(tv, ["RIGHT"], delay=0.8)                 # (opens on Recently watched) > All channels
    await tv.button("DOWN")                               # > 101
    focus, _ = await scr.wait_for("grid", 6)
    if focus != (0, 0):
        raise RuntimeError(f"Grid opened with tile {focus} highlighted, expected 101 at the top left")
    step("grid ready")
    downs, rights = CHANNELS[channel]
    await walk(scr, ["DOWN"] * downs + ["RIGHT"] * rights, channel)

async def landed(scr, step):
    """Wait for the player banner and read the channel number off it; None if it can't be read."""
    _, frame = await scr.wait_for("player", 20)
    number = banner_channel(frame)
    if number is None:
        Image.fromarray(frame.astype("uint8")).save(UNREAD_BANNER)
        step(f"banner has digits we can't read yet, saved {UNREAD_BANNER.name}")
    return number

async def main(channel):
    t0 = time.monotonic()
    def step(msg): print(f"[{time.monotonic() - t0:5.1f}s] {msg}")
    tv, was_off = await connect(step)
    step("connected")
    playing = STATE_FILE.read_text().strip() if STATE_FILE.exists() else None
    warm = not was_off and playing in CHANNELS and tv.tv_state.current_app_id == DSTV_ID
    if warm and playing == channel:
        step(f"already on {channel}")
        await tv.disconnect()
        return
    scr = Screen(tv)
    # Measured: the grid opens in ~3s, moves take 0.3s each, the stream starts ~5s after ENTER
    moves = len(grid_moves(playing, channel)) if warm else sum(CHANNELS[channel])
    countdown = Countdown(tv, channel, (3 if warm else 30) + 0.3 * moves + 5)
    try:
        if warm:
            await switch(scr, playing, channel, step)
        else:
            await cold_start(tv, scr, channel, step)
        step("ENTER, waiting for the picture")
        seen = await landed(scr, step)
        if seen != channel and seen in CHANNELS:          # a dropped key: hop on from where it landed
            step(f"landed on {seen}, correcting")
            await switch(scr, seen, channel, step)
            seen = await landed(scr, step)
        if seen not in (channel, None):
            raise RuntimeError(f"Wanted {channel} but the TV is showing {seen}")
        STATE_FILE.write_text(channel + "\n")
        step(f"playing {channel}" + ("" if seen else " (banner unread, trusting the grid)"))
    except BaseException:
        STATE_FILE.unlink(missing_ok=True)                # state unknown, next run starts fresh
        raise
    finally:
        countdown.stop()
        await scr.close()
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
