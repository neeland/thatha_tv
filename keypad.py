"""Changes channel from a wireless numeric keypad plugged into the Pi.

Type a channel number (e.g. 2 0 3): it plays after the third digit, or press
Enter for a shorter number. Backspace / Esc / . clears a mistake. While the TV
is changing channel, every key is ignored and the TV says "please wait".
"""
import asyncio
import logging
import time
import evdev
from evdev import ecodes
from aiowebostv import WebOsClient
import live_tv

DIGITS = {getattr(ecodes, f"KEY_{n}"): str(n) for n in range(10)}
DIGITS |= {getattr(ecodes, f"KEY_KP{n}"): str(n) for n in range(10)}  # same codes whether Num Lock is on or off
ENTER = {ecodes.KEY_ENTER, ecodes.KEY_KPENTER}
CLEAR = {ecodes.KEY_BACKSPACE, ecodes.KEY_ESC, ecodes.KEY_DELETE, ecodes.KEY_KPDOT}
CHANNEL_LENGTH = 3                # DStv channel numbers are 3 digits
TYPING_TIMEOUT = 5                # seconds before half-typed digits are forgotten
CHANGE_TIMEOUT = 120              # seconds before giving up on a stuck channel change
WAIT_MESSAGE_EVERY = 5            # seconds between "please wait" pop-ups, so they don't pile up

log = logging.getLogger("keypad")

async def say(message):
    """Pop-up on the TV from a short-lived connection (does nothing if the TV is off)."""
    tv = WebOsClient(live_tv.TV_IP, live_tv.CLIENT_KEY, connect_timeout=5)
    try:
        await tv.connect()
        await live_tv.toast(tv, message)
        await tv.disconnect()
    except Exception:
        pass

class Keypad:
    def __init__(self):
        self.typed = ""
        self.last_key = 0
        self.busy = None          # channel being changed to
        self.last_wait_message = 0
        self.tasks = set()        # keeps pop-ups and changes alive until they finish

    def spawn(self, coro):
        task = asyncio.ensure_future(coro)
        self.tasks.add(task); task.add_done_callback(self.tasks.discard)

    def press(self, code):
        now = time.monotonic()
        if now - self.last_key > TYPING_TIMEOUT:
            self.typed = ""
        self.last_key = now

        if self.busy:
            if now - self.last_wait_message > WAIT_MESSAGE_EVERY:
                self.last_wait_message = now
                self.spawn(say(f"Please wait, still changing to {self.busy}"))
            return
        if code in DIGITS:
            self.typed += DIGITS[code]
            if len(self.typed) == CHANNEL_LENGTH:
                self.submit()
        elif code in ENTER and self.typed:
            self.submit()
        elif code in CLEAR:
            self.typed = ""

    def submit(self):
        channel, self.typed = self.typed, ""
        if channel not in live_tv.CHANNELS:
            log.info("Unknown channel %s", channel)
            self.spawn(say(f"Channel {channel} is not set up"))
            return
        self.busy = channel
        self.spawn(self.change(channel))

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
            self.typed = ""                                   # drop anything pressed while waiting

def is_keyboard(device):
    keys = device.capabilities().get(ecodes.EV_KEY, [])
    return ecodes.KEY_KP0 in keys or ecodes.KEY_0 in keys

async def listen(device, keypad):
    log.info("Using %s (%s)", device.name, device.path)
    try:
        device.grab()                                         # keep keystrokes away from the Pi's own console
    except OSError:
        pass
    try:
        async for event in device.async_read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:  # key down only, not repeats
                keypad.press(event.code)
    except OSError:
        log.info("Lost %s", device.name)                      # unplugged, or receiver reset

async def main():
    keypad = Keypad()
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
            task = asyncio.ensure_future(listen(device, keypad))
            task.add_done_callback(lambda _, p=path: listening.pop(p, None))
            listening[path] = task
        await asyncio.sleep(3)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    asyncio.run(main())
