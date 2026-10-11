"""Changes channel when a button on the big-button remote is pressed.

The remote's IR is picked up by a Flirc USB receiver plugged into the Pi, which
turns each button into a key press. learn.py records which key belongs to which
channel in buttons.json. While the TV is changing channel, every button is
ignored and the TV says "please wait".
"""
import asyncio
import json
import logging
import time
from pathlib import Path
import evdev
from evdev import ecodes
from aiowebostv import WebOsClient
import live_tv

BUTTONS_FILE = Path(__file__).parent / "buttons.json"
CHANGE_TIMEOUT = 120              # seconds before giving up on a stuck channel change
WAIT_MESSAGE_EVERY = 5            # seconds between "please wait" pop-ups, so they don't pile up

log = logging.getLogger("buttons")

def load_buttons():
    """{key code: channel} from buttons.json, which stores {channel: key name}."""
    saved = json.loads(BUTTONS_FILE.read_text())
    return {ecodes.ecodes[key]: channel for channel, key in saved.items()}

def key_name(code):
    name = ecodes.KEY.get(code, str(code))
    return name if isinstance(name, str) else name[-1]  # some codes have several names

def is_keyboard(device):
    """Flirc shows up as a keyboard; this skips mice and things like the Pi 5's power button."""
    return ecodes.KEY_A in device.capabilities().get(ecodes.EV_KEY, [])

async def say(message):
    """Pop-up on the TV from a short-lived connection (does nothing if the TV is off)."""
    tv = WebOsClient(live_tv.TV_IP, live_tv.CLIENT_KEY, connect_timeout=5)
    try:
        await tv.connect()
        await live_tv.toast(tv, message)
        await tv.disconnect()
    except Exception:
        pass

class Remote:
    def __init__(self, buttons):
        self.buttons = buttons
        self.busy = None          # channel being changed to
        self.last_message = 0
        self.tasks = set()        # keeps pop-ups and changes alive until they finish

    def spawn(self, coro):
        task = asyncio.ensure_future(coro)
        self.tasks.add(task); task.add_done_callback(self.tasks.discard)

    def message(self, text):
        """Pop-up, at most one every few seconds so a held or mashed button doesn't flood the TV."""
        now = time.monotonic()
        if now - self.last_message > WAIT_MESSAGE_EVERY:
            self.last_message = now
            self.spawn(say(text))

    def press(self, code):
        if self.busy:
            self.message(f"Please wait, still changing to {self.busy}")
        elif code not in self.buttons:
            log.info("Button %s is not set up", key_name(code))
            self.message("That button is not set up")
        else:
            self.busy = self.buttons[code]
            self.spawn(self.change(self.busy))

    async def change(self, channel):
        log.info("Changing to %s", channel)
        try:
            async with asyncio.timeout(CHANGE_TIMEOUT):
                await live_tv.main(channel)
            log.info("Now on %s", channel)
        except Exception:
            log.exception("Changing to %s failed", channel)
            await say(f"Could not change to {channel}, please try again")
        finally:
            self.busy = None

async def listen(device, remote):
    log.info("Using %s (%s)", device.name, device.path)
    try:
        device.grab()                                         # keep key presses away from the Pi's own console
    except OSError:
        pass
    try:
        async for event in device.async_read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:  # press only, not repeats while held
                remote.press(event.code)
    except OSError:
        log.info("Lost %s", device.name)                      # unplugged, or receiver reset

async def main():
    remote = Remote(load_buttons())
    listening = {}
    while True:                                               # pick up the receiver whenever it's plugged in
        for path in evdev.list_devices():
            if path in listening:
                continue
            try:
                device = evdev.InputDevice(path)
            except OSError:
                continue
            if not is_keyboard(device):
                device.close()
                continue
            task = asyncio.ensure_future(listen(device, remote))
            task.add_done_callback(lambda _, p=path: listening.pop(p, None))
            listening[path] = task
        await asyncio.sleep(3)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if not BUTTONS_FILE.exists():
        raise SystemExit("No buttons.json yet - run learn.py to set up the remote's buttons")
    asyncio.run(main())
