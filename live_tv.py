import asyncio
import json
import sys
import time
from pathlib import Path
import numpy as np
from aiowebostv import WebOsClient
from PIL import Image
from wakeonlan import wake
from screen import Screen, banner_channel, classify

TV_IP, TV_MAC = "192.168.10.232", "F4:14:BF:E7:D2:7C"
DSTV_ID = "com.multichoice.tvapp"
CLIENT_KEY = (Path(__file__).parent / ".lgtv_client_key").read_text().strip()
STATE_FILE = Path(__file__).parent / ".last_tile"      # grid tile last seen playing, for fast switching
UNREAD_BANNER = Path(__file__).parent / "unread_banner.png"  # saved when the banner has digits we can't read yet
LINEUP_FILE = Path(__file__).parent / "lineup.json"    # every channel's tile, built by lineup.py
SEEN_FILE = Path(__file__).parent / "seen_tiles.json"  # channel read off the banner at each tile, learned as we go
DEFAULT_CHANNEL = "203"
SHORTCUTS = ["167", "201", "203", "204", "212", "213"]  # number buttons 1-6, lowest first

# Live TV > All channels lists every channel in ascending order, 4 tiles to a row, from 101 at
# tile 0. TILES maps each channel to its tile: lineup.json's, overridden by tiles where the
# banner has shown that channel. CONFIDENT are the ones to trust when correcting a wrong landing.
LINEUP = json.loads(LINEUP_FILE.read_text())
TILES = {c["number"]: c["tile"] for c in LINEUP}
CONFIDENT = {c["number"] for c in LINEUP if c["confidence"] != "unsure"}
SEEN = json.loads(SEEN_FILE.read_text()) if SEEN_FILE.exists() else {}
TILES.update(SEEN); CONFIDENT.update(SEEN)

def number_at(tile):
    """Channel number at a tile, if we know it well enough to say so."""
    for number, t in SEEN.items():
        if t == tile:
            return number
    return next((n for n, t in TILES.items() if t == tile and n in CONFIDENT), None)

def remember(number, tile):
    """Banner showed `number` playing from `tile`."""
    if SEEN.get(number) != tile:
        SEEN[number] = tile; TILES[number] = tile; CONFIDENT.add(number)
        SEEN_FILE.write_text(json.dumps(SEEN, indent=1, sort_keys=True) + "\n")

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
    step("TV not answering (off, or not on this network), sending wake-up")
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
    """Arrow presses that walk the All-channels highlight from one tile to another."""
    downs, rights = dst // 4 - src // 4, dst % 4 - src % 4
    return (["DOWN" if downs > 0 else "UP"] * abs(downs) +
            ["RIGHT" if rights > 0 else "LEFT"] * abs(rights))

async def walk(scr, keys, tile):
    """Move the grid highlight and play the tile.

    Only called once the grid is up and highlighting a tile: keys sent while it is still
    opening hang the app. From there a steady pace is fine. The grid keeps the highlighted row
    at the top, so only the column can be checked here; the banner confirms the rest.
    """
    for key in keys:                                      # 0.3s dropped one of 15 DOWNs once
        await scr.tv.button(key); await asyncio.sleep(0.4)
    focus = await scr.settled_grid()
    if focus[1] != tile % 4:
        raise RuntimeError(f"Grid highlight ended on {focus}, expected column {tile % 4} for tile {tile}")
    await scr.tv.button("ENTER")

DO_NOT_TOUCH = "⏳ DO NOT TOUCH ANYTHING ⏳"

def text_width(text):
    """Rough width in screenshot pixels of capitals in the toast's font, measured on this TV."""
    return sum(4.1 if c in " ·" else 18 if c == "⏳" else 4.5 if c == "I" else 12 if c in "MW"
               else 8.4 if c.isdigit() else 9.2 for c in text)

def two_lines(first, second):
    """Toast text as two centred lines. Toasts are a fixed-width box with left-aligned text that
    ignores line breaks (and HTML), and the font has no bold. So each line is joined with
    non-breaking spaces, too long to share a line with the other so the box wraps between them,
    and pushed right with non-breaking spaces (4.1px each) to centre it in the box's 394px."""
    nb = "\u00a0"
    lines = []
    for line in (first, second):
        pad = max(0, round((197 - text_width(line) / 2) / 4.1))
        lines.append(nb * pad + nb.join(line.split()))
    return " ".join(lines)

class Countdown:
    """'Please wait' toasts while the channel changes. The TV shows one toast at a time for about
    3 seconds and queues the rest, so a new one goes in every 3 seconds, and only while it will
    still be true when it appears. Toasts are LG's grey box (no colours, icons or bold on this TV,
    and anything full-screen would take DStv out of the foreground), so capitals, the colour
    hourglass and centring are what make it stand out."""
    SHOWN_FOR = 3

    def __init__(self, tv, what, seconds, opening=None):
        self.task = asyncio.ensure_future(self.run(tv, what, seconds, opening))

    async def run(self, tv, what, seconds, opening):
        """`opening` replaces the first message's second line."""
        remaining, first = seconds, True
        while remaining > self.SHOWN_FOR:
            text = two_lines(DO_NOT_TOUCH, (opening or f"CHANGING TO {what} · {round(remaining)} SECONDS") if first
                             else f"{what} IN {round(remaining)} SECONDS")
            try:
                await tv.request("system.notifications/createToast", {"message": text})
            except Exception:
                return                                    # a message is a nicety, never a reason to fail
            first = False
            await asyncio.sleep(self.SHOWN_FOR); remaining -= self.SHOWN_FOR

    def stop(self):
        self.task.cancel()

async def open_grid(scr, playing, step):
    """DStv is playing a known tile: BACK reopens the grid with that tile highlighted."""
    for _ in range(100):                                  # BACK is ignored while the stream is starting,
        kind, _ = classify(await scr.grab())              # and untested with the banner up: wait both out
        if kind not in ("player", "loading"):
            break
        await asyncio.sleep(0.1)
    await scr.tv.button("BACK")
    try:
        focus, _ = await scr.wait_for("grid", 4)
    except TimeoutError:
        kind, _ = classify(await scr.grab())
        if kind not in ("dark", "player", "loading"):
            raise                                         # BACK did something else: don't press again blind
        await scr.tv.button("BACK")                       # still on the picture: a stream that was still
        focus, _ = await scr.wait_for("grid", 6)          # starting ignored the first BACK
    if focus[1] != playing % 4:
        raise RuntimeError(f"Grid opened on column {focus[1]}, but tile {playing} is in column {playing % 4}")
    step("grid ready")

async def switch(scr, playing, tile, step):
    await open_grid(scr, playing, step)
    await walk(scr, grid_moves(playing, tile), tile)

async def step_tile(scr, playing, delta, step):
    """CH+/CH-: play the next or previous tile, or None at either end of the list (the same
    channel plays on). No channel list needed: the end shows on screen, as a RIGHT that doesn't
    move the highlight or a DOWN that doesn't scroll the grid."""
    await open_grid(scr, playing, step)
    col, tile = playing % 4, playing + delta
    if tile < 0:
        end = True                                        # 101 is the first; UP from it leaves the grid
    elif tile // 4 == playing // 4:                       # same row: one step sideways
        await scr.tv.button("RIGHT" if delta > 0 else "LEFT")
        focus = await scr.settled_grid()
        end = focus[1] == col
        if not end and focus[1] != tile % 4:
            raise RuntimeError(f"Grid highlight ended on {focus}, expected column {tile % 4}")
    else:                                                 # next or previous row, then to its far end
        await scr.settled_grid()
        before = scr.frame
        await scr.tv.button("DOWN" if delta > 0 else "UP")
        await scr.settled_grid()
        end = np.abs(scr.frame - before).mean() < 3
        if not end:
            await walk(scr, ["LEFT" if delta > 0 else "RIGHT"] * 3, tile)
            return tile
    await scr.tv.button("ENTER")                          # plays the highlighted tile
    return None if end else tile

async def cold_start(tv, scr, tile, step):
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
    await walk(scr, ["DOWN"] * (tile // 4) + ["RIGHT"] * (tile % 4), tile)

async def landed(scr, step):
    """Wait for the player banner and read the channel number off it; None if it can't be read."""
    _, frame = await scr.wait_for("player", 20)
    number = banner_channel(frame)
    if number is None:
        Image.fromarray(frame.astype("uint8")).save(UNREAD_BANNER)
        step(f"banner has digits we can't read yet, saved {UNREAD_BANNER.name}")
    return number

async def main(channel=None, delta=0):
    """Play `channel`, or with delta +1/-1 the next/previous channel in the list (CH+/CH-)."""
    t0 = time.monotonic()
    def step(msg): print(f"[{time.monotonic() - t0:5.1f}s] {msg}")
    tv, was_off = await connect(step)
    step("connected")
    playing = int(STATE_FILE.read_text()) if STATE_FILE.exists() else None
    warm = not was_off and playing is not None and tv.tv_state.current_app_id == DSTV_ID
    if delta and not warm:
        channel = DEFAULT_CHANNEL                         # nothing known to step from: start at the usual one
        step(f"not sure what's playing, going to {channel}")
    if channel:
        tile = TILES[channel]
        if warm and playing == tile:
            step(f"already on {channel}")
            await tv.disconnect()
            return
        what = f"CHANNEL {channel}"
        moves = len(grid_moves(playing, tile)) if warm else tile // 4 + tile % 4
    else:
        tile = playing + delta
        what = f"CHANNEL {number_at(tile)}" if number_at(tile) else ("THE NEXT CHANNEL" if delta > 0 else "THE PREVIOUS CHANNEL")
        moves = 1 if tile // 4 == playing // 4 else 4
    scr = Screen(tv)
    # Measured: the grid opens in ~3s, moves take 0.4s each, the stream starts ~5s after ENTER
    countdown = Countdown(tv, what, (3 if warm else 30) + 0.4 * moves + 5,
                          None if warm else "WAKING UP · NEXT TIME IS QUICKER")
    try:
        if not channel:
            tile = await step_tile(scr, playing, delta, step)
            if tile is None:
                tile = playing
                step("end of the list")
                countdown.stop()
                await toast(tv, two_lines("⏳ NO MORE CHANNELS THIS WAY ⏳", "STAYING ON THIS CHANNEL"))
        elif warm:
            await switch(scr, playing, tile, step)
        else:
            await cold_start(tv, scr, tile, step)
        step("ENTER, waiting for the picture")
        seen = await landed(scr, step)
        if channel and seen not in (channel, None) and seen in CONFIDENT:  # a dropped key: hop on from where it landed
            step(f"landed on {seen}, correcting")
            await switch(scr, TILES[seen], tile, step)
            seen = await landed(scr, step)
        if channel and seen not in (channel, None):
            raise RuntimeError(f"Wanted {channel} but the TV is showing {seen}")
        if seen:
            remember(seen, tile)
        STATE_FILE.write_text(f"{tile}\n")
        step(f"playing tile {tile}: " + (seen or f"{channel or '?'} (banner unread, trusting the grid)"))
    except BaseException:
        STATE_FILE.unlink(missing_ok=True)                # state unknown, next run starts fresh
        raise
    finally:
        countdown.stop()
        await scr.close()
        await tv.disconnect()

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CHANNEL
    if arg == "on":
        sys.exit(power_on())
    if arg not in TILES and arg not in ("up", "down"):
        sys.exit(f"Unknown channel {arg!r}: use a DStv channel number (see lineup.json), up, down or on")
    try:
        asyncio.run(main(delta=1) if arg == "up" else main(delta=-1) if arg == "down" else main(arg))
    except RuntimeError as err:
        sys.exit(str(err))
