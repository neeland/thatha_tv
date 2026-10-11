"""Keyboard remote for the LG TV, used to discover DStv navigation paths.

Arrows / WASD = move, Enter/Space = OK, b = Back, h = Home, 0-9 = digits, q = quit.
Every key sent is printed so the path can be copied into live_tv.py.
"""
import asyncio
import msvcrt
from pathlib import Path
from aiowebostv import WebOsClient

TV_IP = "192.168.10.232"
CLIENT_KEY = (Path(__file__).parent / ".lgtv_client_key").read_text().strip()

# msvcrt reports arrow keys as a "\xe0" or "\x00" prefix followed by a code
ARROWS = {"H": "UP", "P": "DOWN", "M": "RIGHT", "K": "LEFT"}
KEYS = {
    "w": "UP", "s": "DOWN", "d": "RIGHT", "a": "LEFT",
    "\r": "ENTER", " ": "ENTER", "b": "BACK", "h": "HOME",
    **{str(n): str(n) for n in range(10)},
}

def read_key():
    ch = msvcrt.getwch()
    if ch in ("\xe0", "\x00"):
        return ARROWS.get(msvcrt.getwch())
    return ch

async def main():
    tv = WebOsClient(TV_IP, CLIENT_KEY, connect_timeout=15)
    await tv.connect()
    print(__doc__)
    path = []
    loop = asyncio.get_running_loop()
    while True:
        ch = await loop.run_in_executor(None, read_key)
        if ch in ("q", "\x03"):
            break
        key = ch if ch in KEYS.values() else KEYS.get(ch)
        if key:
            await tv.button(key)
            path.append(key)
            print(key)
    print("\nPath:", path)
    await tv.disconnect()

asyncio.run(main())
