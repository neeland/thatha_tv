"""Times each stage of a TV screenshot, to find what's slow on the Pi: .venv/bin/python grab_timing.py"""
import asyncio
import io
import time
import aiohttp
import numpy as np
from PIL import Image
from aiowebostv import WebOsClient
import live_tv
from screen import classify

async def main():
    tv = WebOsClient(live_tv.TV_IP, live_tv.CLIENT_KEY, connect_timeout=5)
    await tv.connect()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        for _ in range(4):
            t0 = time.monotonic()
            res = await tv.request("tv/executeOneShot", {"method": "DISPLAY", "format": "JPG"})
            t1 = time.monotonic()
            async with session.get(res["imageUri"]) as r:
                data = await r.read()
            t2 = time.monotonic()
            a = np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).astype(np.int16)
            t3 = time.monotonic()
            kind = classify(a)
            t4 = time.monotonic()
            print(f"ask TV {t1 - t0:.2f}s | download {t2 - t1:.2f}s ({len(data) // 1024} KB) | "
                  f"decode {t3 - t2:.2f}s | read screen {t4 - t3:.2f}s | {kind}")
    await tv.disconnect()

asyncio.run(main())
