"""Builds lineup.json: every DStv channel's tile in the app's Live TV > All channels grid.

    .venv/bin/python lineup.py

The grid lists channels in ascending order, 4 to a row, from 101 at tile 0. DStv's guide API
lists the same channels plus 3 that the app doesn't show, so a channel's tile is its place in
the guide minus however many of those come before it. Tiles seen on the TV pin that down:

    101 -> 0 (grid opens on it)   120 -> 10, 138 -> 21   (1 extra channel in 106-118)
    167 -> 37, 201 -> 61, 203 -> 63, 204 -> 64, 212 -> 72, 213 -> 73   (2 more in 140-166)

So each channel gets a confidence:
    seen      its tile was seen on the TV
    inferred  between or past seen tiles with no extra channel in between (assumed for 214+)
    unsure    106-118 or 140-166, where an extra channel sits at an unknown place (off by up to 2)
CH+/CH- don't depend on this: they step one tile and check the highlight on screen.
"""
import json
import urllib.request
from pathlib import Path

API = "https://www.dstv.com/umbraco/api/TvGuide/GetChannels?country=zaf&unit=dstv"
SEEN = {"101": 0, "120": 10, "138": 21, "167": 37, "201": 61, "203": 63, "204": 64, "212": 72, "213": 73}
EXTRA_BEFORE = [(101, 0), (119, 1), (167, 3)]        # (from channel, extra channels below it)
UNSURE = [(106, 118), (140, 166)]

def main():
    with urllib.request.urlopen(API, timeout=30) as r:
        channels = json.load(r)["Channels"]
    names = {}
    for c in channels:                                # some numbers are listed twice (SD and HD)
        names.setdefault(c["Number"], c["Name"])
    lineup = []
    for place, number in enumerate(sorted(names, key=int)):
        n = int(number)
        extra = max(e for start, e in EXTRA_BEFORE if n >= start)
        tile = place - extra
        if number in SEEN:
            assert SEEN[number] == tile, f"{number}: guide says tile {tile}, TV showed {SEEN[number]}"
            confidence = "seen"
        elif any(lo <= n <= hi for lo, hi in UNSURE):
            confidence = "unsure"
        else:
            confidence = "inferred"
        lineup.append({"number": number, "name": names[number], "tile": tile, "confidence": confidence})
    Path(__file__).with_name("lineup.json").write_text(json.dumps(lineup, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(lineup)} channels, tiles 0-{lineup[-1]['tile']}")

if __name__ == "__main__":
    main()
