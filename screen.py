"""Reads the DStv app off the TV screen, so each step waits for (and checks) what is actually shown.

Screenshots come from the TV itself (tv/executeOneShot, ~0.1s each, always 960x540). Video
captures as black (DRM), but the app's own menus and the player banner are drawn on top of it.
"""
import asyncio
import io
import time
from pathlib import Path
import aiohttp
import numpy as np
from PIL import Image

# Channel-number glyphs in the player banner at 960x540: '#' lit, '.' dark, '+' half-lit edge
# (ignored). A digit lands on different sub-pixel offsets depending on the logo before it, so
# some have more than one shape.
DIGITS = {
    "0": [(".#####.", ".#...#.", "##...##", "#....##", "#....##", "#....##", "##...##", ".#...#.", ".#####."),
          (".#####.", ".#...#.", "#+...#+", "#+...+#", "#+...+#", "#+...+#", "+#...#+", ".#...#.", ".####+."),
          (".####.", "#+..+#", "#....#", "#....#", "#....#", "#....#", "#....#", "#+..##", ".####.")],
    "1": [("###", "..#", "..#", "..#", "..#", "..#", "..#", "..#", "..#"),
          ("+##", "..#", "..#", "..#", "..#", "..#", "..#", "..#", "..#")],
    "2": [(".####.", "#...##", "#...##", "....##", "....#.", "...#..", "..##..", ".#....", "######"),
          ("+####.", "#...#+", "#...+#", "....#+", "....#.", "...#+.", "..#+..", "+#+...", "######")],
    "3": [("#####", "#...#", "....#", "...##", ".###.", "....#", "....#", "#...#", "#####"),
          (".####.", "#+..+#", ".....#", "...+#.", "..###.", "....##", "+....#", "#+..##", ".####.")],
    "4": [(".....#.", "....##.", "...#.#.", "..##.#.", "..#..#.", ".#...#.", "#######", ".....#.", ".....#.")],
    "5": [("#####.", "#.....", "#.....", "#+##+.", "##..#+", "....+#", "....+#", "#...##", "+####.")],
    "6": [(".####+.", ".#...#.", "##.....", "#++##..", "##+.+#.", "##...##", "##...+#", ".#...#+", ".+####.")],
    "7": [("######", ".....#", "....#+", "....#.", "...+#.", "...#..", "..+#..", "..#+..", "..#...")],
}
TEMPLATES = [(digit, np.array([[c == "#" for c in row] for row in rows]),
              np.array([[c == "." for c in row] for row in rows]))
             for digit, shapes in DIGITS.items() for rows in shapes]

def cyan(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r < 110) & (g > 160) & (b > 160) & (abs(g - b) < 50)

UNSETTLED_GRID = Path(__file__).parent / "unsettled_grid.png"  # last frame when the grid never settles

SLOT_X, SLOT_Y = (193, 407, 621, 835), (162, 344)    # play-button centres of the visible tiles

def classify(a):
    """('player', None) with the banner up, ('loading', None) while a stream starts, ('grid',
    (row, col)) with a tile focused (its play button turns cyan), ('dark', None) for playing
    video (it captures black), else ('other', None)."""
    m = cyan(a)
    if m[390:403, 90:870].sum() > 400:                   # the player's cyan progress bar
        return "player", None
    if m[240:300, 450:510].sum() > 60:                   # DStv's cyan spinner: stream still starting
        return "loading", None
    # DStv logo, so this is the app's own menu, with the sidebar's Live TV icon lit (DStv home has
    # a cyan Watch button where a tile's play button would be)
    if m[28:56, 26:60].sum() > 400 and m[205:228, 30:53].sum() > 25:
        counts = {(r, c): m[y - 25:y + 25, x - 25:x + 25].sum()
                  for r, y in enumerate(SLOT_Y) for c, x in enumerate(SLOT_X)}
        slot = max(counts, key=counts.get)
        if counts[slot] > 150:
            return "grid", slot
    return ("dark" if a.mean() < 15 else "other"), None

def banner_channel(a):
    """Channel number from the player banner (e.g. '203'), or None if it can't be read.

    Where the number starts depends on the width of the channel logo before it, so the digits
    land on different sub-pixel offsets and their edges shade differently: match each digit
    shape left to right, ignoring the half-lit edge pixels, and take the closest within a few.
    """
    grey = np.asarray(Image.fromarray(a.astype(np.uint8)).convert("L")).astype(int)[150:320, 130:185]
    rows = np.nonzero((grey > 110).any(axis=1))[0]
    if not len(rows):
        return None
    line = grey[rows[0]:rows[0] + 9]
    if line.shape[0] != 9:
        return None
    on, off = line > 150, line < 60
    number, x = "", 0
    while x < line.shape[1]:
        if not on[:, x].any():
            x += 1
            continue
        best, digit = None, None
        for d, lit, dark in TEMPLATES:
            w = lit.shape[1]
            for dx in (0, -1):                           # a soft first column can sit just left of x
                x0 = x + dx
                if x0 < 0 or x0 + w > line.shape[1]:
                    continue
                wrong = (lit & off[:, x0:x0 + w]).sum() + (dark & on[:, x0:x0 + w]).sum()
                if best is None or wrong < best[0]:
                    best, digit = (wrong, x0 + w), d
        if best is None or best[0] > 4:
            break                                        # the PVR cloud icon after the number, or noise
        number += digit
        x = best[1]
    return number if len(number) == 3 else None         # DStv channel numbers are 101-999

class Screen:
    def __init__(self, tv):
        self.tv = tv
        self.frame = None
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))

    async def close(self):
        await self.session.close()

    async def grab(self):
        res = await self.tv.request("tv/executeOneShot", {"method": "DISPLAY", "format": "JPG"})
        async with self.session.get(res["imageUri"]) as r:
            return np.asarray(Image.open(io.BytesIO(await r.read())).convert("RGB")).astype(np.int16)

    async def wait_for(self, kind, timeout):
        """Poll until the screen is `kind`; returns (focus, frame) or raises TimeoutError."""
        end = time.monotonic() + timeout
        while True:
            a = await self.grab()
            got, focus = classify(a)
            if got == kind:
                return focus, a
            if time.monotonic() > end:
                raise TimeoutError(f"screen stayed {got!r}, expected {kind!r}")
            await asyncio.sleep(0.05)

    async def settled_grid(self, timeout=6, still_for=0.5):
        """Wait for the grid to stop scrolling and return the focus.

        Scrolling pauses briefly between queued moves, so two alike frames aren't enough: the
        screen has to stay the same, with the same tile highlighted, for `still_for` seconds.
        """
        start = time.monotonic()
        end, last = start + timeout, await self.grab()
        still_since, focus, seen = None, None, []
        while time.monotonic() < end:
            await asyncio.sleep(0.05)
            a = await self.grab()
            kind, now = classify(a)
            diff = np.abs(a - last).mean()
            seen.append(f"{time.monotonic() - start:.1f}s {kind} {now} diff {diff:.2f}")
            if kind == "grid" and now == focus and diff < 0.3:
                if time.monotonic() - still_since >= still_for:
                    self.frame = a                       # the settled grid, for callers comparing screens
                    return focus
            else:
                still_since, focus = time.monotonic(), (now if kind == "grid" else None)
            last = a
        Image.fromarray(last.astype(np.uint8)).save(UNSETTLED_GRID)
        raise TimeoutError(f"grid did not settle (frame saved to {UNSETTLED_GRID.name}): " + "; ".join(seen))
