"""Changes channel, volume and power from the One For All remote.

The remote's IR is picked up by a Flirc USB receiver plugged into the Pi, which
turns each button into a key press. The Flirc is programmed (Full Keyboard) so
the number buttons 1-9 and 0 type a-j, the up and down arrows are Volume Up and
Volume Down (or the Up and Down arrow keys), and on/off is Home. Number buttons go to the channels in
CHANNELS from lowest to highest: 1 is the lowest. While the TV is changing
channel, channel and power buttons are ignored and the TV says "please wait";
volume still works.
"""
import asyncio
import logging
import time
import evdev
from evdev import ecodes
from aiowebostv import WebOsClient
import live_tv

NUMBER_KEYS = [ecodes.ecodes[f"KEY_{c}"] for c in "ABCDEFGHIJ"]   # remote buttons 1-9, 0
CHANNEL_KEYS = dict(zip(NUMBER_KEYS, sorted(live_tv.CHANNELS, key=int)))
VOLUME_KEYS = {ecodes.KEY_VOLUMEUP: "volume_up", ecodes.KEY_UP: "volume_up",     # the remote's up and down
               ecodes.KEY_VOLUMEDOWN: "volume_down", ecodes.KEY_DOWN: "volume_down"}  # arrows, as either key
POWER_KEYS = {ecodes.KEY_HOME, ecodes.KEY_HOMEPAGE, ecodes.KEY_POWER}   # on/off: keyboard Home, media Home or Power
CHANGE_TIMEOUT = 120              # seconds before giving up on a stuck channel change
WAIT_MESSAGE_EVERY = 5            # seconds between "please wait" pop-ups, so they don't pile up

log = logging.getLogger("buttons")

def key_name(code):
    name = ecodes.KEY.get(code, str(code))
    return name if isinstance(name, str) else name[-1]  # some codes have several names

def is_remote(device):
    """The Flirc shows up as several devices (keyboard, media keys, system keys such as power),
    so take every one of them, plus any other keyboard; this skips mice and things like the
    Pi 5's power button."""
    keys = device.capabilities().get(ecodes.EV_KEY, [])
    return "flirc" in device.name.lower() or ecodes.KEY_A in keys or ecodes.KEY_VOLUMEUP in keys

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
    def __init__(self):
        self.busy = None          # channel being changed to, or "power"
        self.adjusting = False    # a volume step is on its way to the TV
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

    def press(self, code, held=False):
        if not held:
            log.info("Pressed %s", key_name(code))
        if code in VOLUME_KEYS:
            if not self.adjusting:                            # drop repeats while one is still being sent
                self.adjusting = True
                self.spawn(self.volume(VOLUME_KEYS[code]))
        elif held:
            pass                                              # only volume repeats while a button is held
        elif self.busy:
            self.message(live_tv.two_lines(live_tv.DO_NOT_TOUCH, "THE TV IS TURNING ON OR OFF" if self.busy == "power"
                                           else f"STILL CHANGING TO CHANNEL {self.busy}"))
        elif code in POWER_KEYS:
            self.busy = "power"
            self.spawn(self.power())
        elif code in CHANNEL_KEYS:
            self.busy = CHANNEL_KEYS[code]
            self.spawn(self.change(self.busy))
        else:
            log.info("Button %s is not set up", key_name(code))
            self.message("That button is not set up")

    async def volume(self, step):
        tv = WebOsClient(live_tv.TV_IP, live_tv.CLIENT_KEY, connect_timeout=5)
        try:
            await tv.connect()
            await getattr(tv, step)()
            await tv.disconnect()
        except Exception:
            pass                                              # TV off: nothing to turn up
        finally:
            self.adjusting = False

    async def power(self):
        """On/off: turn the TV off if it's on, otherwise wake it."""
        tv = WebOsClient(live_tv.TV_IP, live_tv.CLIENT_KEY, connect_timeout=3)
        try:
            await tv.connect()
        except Exception:
            log.info("Turning the TV on")
            await asyncio.to_thread(live_tv.power_on)
            await asyncio.sleep(10)                           # let it come up before taking more presses
        else:
            log.info("Turning the TV off")
            try:
                await tv.power_off()
            except Exception:
                log.exception("Turning the TV off failed")
            await tv.disconnect()
            await asyncio.sleep(5)                            # a press now would just wake it again
        finally:
            self.busy = None

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
            if event.type == ecodes.EV_KEY and event.value:   # 1 pressed, 2 repeating while held
                remote.press(event.code, held=event.value == 2)
    except OSError:
        log.info("Lost %s", device.name)                      # unplugged, or receiver reset

async def main():
    remote = Remote()
    listening = {}
    while True:                                               # pick up the receiver whenever it's plugged in
        for path in evdev.list_devices():
            if path in listening:
                continue
            try:
                device = evdev.InputDevice(path)
            except OSError:
                continue
            if not is_remote(device):
                device.close()
                continue
            task = asyncio.ensure_future(listen(device, remote))
            task.add_done_callback(lambda _, p=path: listening.pop(p, None))
            listening[path] = task
        await asyncio.sleep(3)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    for key, channel in CHANNEL_KEYS.items():
        log.info("Button %s (%s): channel %s", "1234567890"[NUMBER_KEYS.index(key)], key_name(key), channel)
    asyncio.run(main())
