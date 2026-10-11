"""Web page with a button per channel, so the TV can be driven from an iPad.

Run on the PC, then open http://<pc-ip>:8000 on the iPad.
"""
import asyncio
import hmac
import time
from pathlib import Path
from aiohttp import web
import live_tv

PORT = 8000
TIMEOUT = 120                     # seconds before giving up on a stuck channel change
STATIC = Path(__file__).parent / "static"
state = {"busy": None, "channel": None, "error": None}  # shared by every device viewing the page
tasks = set()                     # keeps running changes alive until they finish
PIN_FILE = Path(__file__).parent / ".unlock_pin"
kiosk = {"locked": False, "wrong": 0, "wait_until": 0}  # full-screen lock on the PC itself

async def index(request):
    return web.FileResponse(STATIC / "index.html")

async def channels(request):
    return web.json_response(sorted(live_tv.CHANNELS, key=int))

async def status(request):
    return web.json_response(state)

async def change(channel):
    try:
        async with asyncio.timeout(TIMEOUT):
            await live_tv.main(channel)
        state.update(channel=channel, error=None)
    except TimeoutError:
        state.update(channel=None, error=f"TV did not respond within {TIMEOUT} seconds")
    except Exception as err:
        state.update(channel=None, error=str(err) or type(err).__name__)
    finally:
        state["busy"] = None

async def play(request):
    channel = request.match_info["channel"]
    if channel not in live_tv.CHANNELS:
        return web.json_response({"error": f"Unknown channel {channel}"}, status=404)
    if state["busy"]:
        return web.json_response({"error": f"Already changing to {state['busy']}, please wait"}, status=409)
    state.update(busy=channel, error=None)
    # Runs as its own task so it finishes even if the iPad disconnects mid-change
    task = asyncio.ensure_future(change(channel))
    tasks.add(task); task.add_done_callback(tasks.discard)
    await asyncio.shield(task)
    return web.json_response(state)

def local_only(handler):
    """Unlocking is only allowed from the PC's own screen, not the iPad."""
    async def wrapper(request):
        if request.remote not in ("127.0.0.1", "::1"):
            return web.json_response({"error": "Only allowed on the PC"}, status=403)
        return await handler(request)
    return wrapper

async def kiosk_status(request):
    return web.json_response({"locked": kiosk["locked"]})

@local_only
async def lock(request):
    kiosk["locked"] = True
    return web.json_response({"locked": True})

@local_only
async def unlock(request):
    wait = kiosk["wait_until"] - time.monotonic()
    if wait > 0:
        return web.json_response({"error": f"Too many wrong PINs, try again in {wait:.0f} seconds"}, status=429)
    pin = str((await request.json()).get("pin", ""))
    if not hmac.compare_digest(pin.encode(), PIN_FILE.read_text().strip().encode()):
        kiosk["wrong"] += 1
        if kiosk["wrong"] >= 3:
            kiosk.update(wrong=0, wait_until=time.monotonic() + 60)
        return web.json_response({"error": "Wrong PIN"}, status=403)
    kiosk.update(locked=False, wrong=0)
    return web.json_response({"locked": False})

app = web.Application()
app.add_routes([
    web.get("/", index),
    web.get("/channels", channels),
    web.get("/status", status),
    web.post("/play/{channel}", play),
    web.get("/kiosk", kiosk_status),
    web.post("/kiosk/lock", lock),
    web.post("/kiosk/unlock", unlock),
    web.static("/static", STATIC),
])

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=PORT)  # this PC only
