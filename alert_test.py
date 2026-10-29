"""Tries LG's centred alert box as the "DO NOT TOUCH ANYTHING" message: .venv/bin/python alert_test.py

Start with DStv playing the channel the Pi last tuned (press a channel button first) and the
thatha-tv service stopped. Prints what it sees at each step and saves alert_*.png frames.
"""
import asyncio
import time
from pathlib import Path
import numpy as np
from PIL import Image
import live_tv
from screen import Screen, classify

MESSAGE = "🔵🔵  DO NOT TOUCH ANYTHING  🔵🔵<br>CHANGING TO CHANNEL 203"
OUT = Path(__file__).parent
t0 = time.monotonic()

def log(msg):
    print(f"[{time.monotonic() - t0:5.1f}s] {msg}", flush=True)

async def look(scr, name):
    a = await scr.grab()
    Image.fromarray(a.astype(np.uint8)).save(OUT / f"alert_{name}.png")
    kind = classify(a)
    log(f"screen: {kind} (saved alert_{name}.png)")
    return kind

async def alert(tv, payload, label):
    try:
        res = await tv.request("system.notifications/createAlert", payload)
        log(f"{label}: shown, id {res.get('alertId')}")
        return res.get("alertId")
    except Exception as err:
        log(f"{label}: refused ({err!r})")
        return None

async def close(tv, alert_id):
    try:
        await tv.request("system.notifications/closeAlert", {"alertId": alert_id})
        log("closed")
    except Exception as err:
        log(f"close failed ({err!r})")

async def main():
    tv, _ = await live_tv.connect(log)
    scr = Screen(tv)
    playing = live_tv.STATE_FILE.read_text().strip() if live_tv.STATE_FILE.exists() else None
    try:
        if playing not in live_tv.CHANNELS or tv.tv_state.current_app_id != live_tv.DSTV_ID:
            raise SystemExit("Press a channel button first so DStv is playing a channel the Pi tuned")
        log(f"DStv playing {playing}")

        # 1. Over the playing picture: does a box with no buttons show, and does it close?
        alert_id = await alert(tv, {"message": MESSAGE, "buttons": []}, "no buttons")
        if alert_id is None:
            alert_id = await alert(tv, {"message": MESSAGE, "buttons": [{"label": "OK"}]}, "one button")
        if alert_id is None:
            raise SystemExit("The TV refused both alert shapes")
        await asyncio.sleep(1)
        await look(scr, "1_over_player")
        await asyncio.sleep(3)                                # time to look at it on the TV
        await close(tv, alert_id)
        await asyncio.sleep(1)
        await look(scr, "2_after_close")

        # 2. Over the channel grid: can the screen still be read, and do keys reach DStv under it?
        for _ in range(100):
            kind, _ = classify(await scr.grab())
            if kind not in ("player", "loading"):
                break
            await asyncio.sleep(0.1)
        await tv.button("BACK")
        before, _ = await scr.wait_for("grid", 10)
        log(f"grid open, highlight on {before}")
        move = "LEFT" if before[1] > 0 else "RIGHT"
        alert_id = await alert(tv, {"message": MESSAGE, "buttons": []}, "over grid")
        await asyncio.sleep(1)
        await look(scr, "3_over_grid")
        await tv.button(move)
        log(f"pressed {move} with the box up")
        await asyncio.sleep(1.5)
        await look(scr, "4_after_key")
        await close(tv, alert_id)
        await asyncio.sleep(1)
        after = await look(scr, "5_grid_after_close")
        moved = after[0] == "grid" and after[1] != before
        log("KEYS REACH DSTV UNDER THE BOX" if moved else "keys did NOT reach DStv (box took them, or it moved and came back)")

        # Put things back: highlight on the channel that was playing, play it.
        if moved:
            await tv.button("RIGHT" if move == "LEFT" else "LEFT")
        focus = await scr.settled_grid()
        log(f"back on {focus}, playing it again")
        await tv.button("ENTER")
        await scr.wait_for("player", 20)
        log("playing again")
    except BaseException:
        live_tv.STATE_FILE.unlink(missing_ok=True)            # not sure what's on screen: next press starts fresh
        raise
    finally:
        await scr.close()
        await tv.disconnect()

asyncio.run(main())
