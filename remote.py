"""Keyboard remote for the LG TV, used to discover DStv navigation paths.

Arrows / WASD = move, Enter/Space = OK, b = Back, h = Home, 0-9 = digits, q = quit.
Every key sent is printed so the path can be copied into live_tv.py.
"""
import asyncio
import sys
import termios
import tty
from pathlib import Path
from aiowebostv import WebOsClient

TV_IP = "192.168.10.232"
CLIENT_KEY = (Path(__file__).parent / ".lgtv_client_key").read_text().strip()

KEYS = {
    "\x1b[A": "UP", "\x1b[B": "DOWN", "\x1b[C": "RIGHT", "\x1b[D": "LEFT",
    "w": "UP", "s": "DOWN", "d": "RIGHT", "a": "LEFT",
    "\r": "ENTER", " ": "ENTER", "b": "BACK", "h": "HOME",
    **{str(n): str(n) for n in range(10)},
}

def read_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

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
        if ch in KEYS:
            await tv.button(KEYS[ch])
            path.append(KEYS[ch])
            print(KEYS[ch])
    print("\nPath:", path)
    await tv.disconnect()

asyncio.run(main())
