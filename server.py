"""Web page with a button per channel, so the TV can be driven from an iPad.

Run on the PC, then open http://<pc-ip>:8000 on the iPad.
"""
import asyncio
from pathlib import Path
from aiohttp import web
import live_tv

PORT = 8000
STATIC = Path(__file__).parent / "static"
lock = asyncio.Lock()

async def index(request):
    return web.FileResponse(STATIC / "index.html")

async def channels(request):
    return web.json_response(sorted(live_tv.CHANNELS, key=int))

async def play(request):
    channel = request.match_info["channel"]
    if channel not in live_tv.CHANNELS:
        return web.json_response({"error": f"Unknown channel {channel}"}, status=404)
    if lock.locked():
        return web.json_response({"error": "Already changing channel, please wait"}, status=409)
    async with lock:
        try:
            await live_tv.main(channel)
        except Exception as err:
            return web.json_response({"error": str(err) or type(err).__name__}, status=500)
    return web.json_response({"channel": channel})

app = web.Application()
app.add_routes([
    web.get("/", index),
    web.get("/channels", channels),
    web.post("/play/{channel}", play),
    web.static("/static", STATIC),
])

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
