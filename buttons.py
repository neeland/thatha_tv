"""Changes channel, volume, mute and power from the One For All remote.

The remote's IR is picked up by a Flirc USB receiver plugged into the Pi, which
turns each button into a key press. The Flirc is programmed (Full Keyboard) so:

    1-9, 0          a-j            number buttons: live_tv.SHORTCUTS, lowest first (0 not set)
    CH+ / CH-       = / -          next / previous channel in DStv's list, any channel
    up / down       Up / Down      volume (Volume Up / Volume Down work too)
    on/off          P              TV off if on, on if off (Home or Power work too)
    mute            M              mute on/off (Mute works too)

While the TV is changing channel, channel and power buttons are ignored and the
TV says "do not touch anything"; volume and mute still work.
"""
import asyncio
import logging
import time
import evdev
from evdev import ecodes
import live_tv

NUMBER_KEYS = [ecodes.ecodes[f"KEY_{c}"] for c in "ABCDEFGHIJ"]   # remote buttons 1-9, 0
CHANNEL_KEYS = dict(zip(NUMBER_KEYS, live_tv.SHORTCUTS))
STEP_KEYS = {k: +1 for k in (ecodes.KEY_EQUAL, ecodes.KEY_KPPLUS, ecodes.KEY_PAGEUP, ecodes.KEY_CHANNELUP)}
STEP_KEYS.update({k: -1 for k in (ecodes.KEY_MINUS, ecodes.KEY_KPMINUS, ecodes.KEY_PAGEDOWN, ecodes.KEY_CHANNELDOWN)})
MUTE_KEYS = {ecodes.KEY_M, ecodes.KEY_MUTE}
VOLUME_KEYS = {ecodes.KEY_VOLUMEUP: "volume_up", ecodes.KEY_UP: "volume_up",     # the remote's up and down
               ecodes.KEY_VOLUMEDOWN: "volume_down", ecodes.KEY_DOWN: "volume_down"}  # arrows, as either key
POWER_KEYS = {ecodes.KEY_P, ecodes.KEY_HOME, ecodes.KEY_HOMEPAGE, ecodes.KEY_POWER, ecodes.KEY_SLEEP}
CHANGE_TIMEOUT = 300              # seconds before giving up on a stuck channel change, retries included
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
    """Pop-up on the TV (does nothing if the TV is off)."""
    try:
        tv, _ = await live_tv.connect(log.info, wake=False)
        await live_tv.toast(tv, message)
    except Exception:
        pass

class Remote:
    def __init__(self):
        self.busy = None          # what's being changed to ("CHANNEL 203", "THE NEXT CHANNEL"), or "power"
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
        if code in MUTE_KEYS:
            if not held and not self.adjusting:
                self.adjusting = True
                self.spawn(self.mute())
        elif code in VOLUME_KEYS:
            if not self.adjusting:                            # drop repeats while one is still being sent
                self.adjusting = True
                self.spawn(self.volume(VOLUME_KEYS[code]))
        elif held:
            pass                                              # only volume repeats while a button is held
        elif self.busy:
            self.message(live_tv.two_lines(live_tv.DO_NOT_TOUCH, "THE TV IS TURNING ON OR OFF" if self.busy == "power"
                                           else f"STILL CHANGING TO {self.busy}"))
        elif code in POWER_KEYS:
            self.busy = "power"
            self.spawn(self.power())
        elif code in CHANNEL_KEYS:
            channel = CHANNEL_KEYS[code]
            self.busy = live_tv.channel_label(channel)
            self.spawn(self.change(self.busy, channel=channel))
        elif code in STEP_KEYS:
            delta = STEP_KEYS[code]
            self.busy = "THE NEXT CHANNEL" if delta > 0 else "THE PREVIOUS CHANNEL"
            self.spawn(self.change(self.busy, delta=delta))
        else:
            log.info("Button %s is not set up", key_name(code))
            self.message("That button is not set up")

    async def volume(self, step):
        try:
            tv, _ = await live_tv.connect(log.info, wake=False)
            await getattr(tv, step)()
        except Exception:
            pass                                              # TV off: nothing to turn up
        finally:
            self.adjusting = False

    async def mute(self):
        try:
            tv, _ = await live_tv.connect(log.info, wake=False)
            await tv.set_mute(not await tv.get_muted())
        except Exception:
            log.exception("Mute failed")
        finally:
            self.adjusting = False

    async def power(self):
        """On/off: turn the TV off if it's on; if it's off, turn it on straight to the last channel
        watched (any slow DStv start happens now, under the waking-up message, not on the next
        channel press)."""
        try:
            try:
                tv, _ = await live_tv.connect(log.info, wake=False)
            except Exception:
                channel = live_tv.last_watched()
                log.info("Turning the TV on, to %s", channel)
                self.busy = live_tv.channel_label(channel)
                await self.change(self.busy, channel=channel)  # wakes the TV, then starts DStv on it
                return
            log.info("Turning the TV off")
            try:
                await tv.power_off()
            except Exception:
                log.exception("Turning the TV off failed")
            await live_tv.drop()
            await asyncio.sleep(5)                            # a press now would just wake it again
        finally:
            if self.busy == "power":
                self.busy = None

    async def change(self, what, **target):
        log.info("Changing to %s", target)
        try:
            async with asyncio.timeout(CHANGE_TIMEOUT):
                await live_tv.main(**target)
            log.info("Done: %s", target)
        except Exception:
            log.exception("Changing to %s failed", target)
            await say(live_tv.two_lines("⏳ SORRY, THAT DIDN'T WORK ⏳", "PLEASE PRESS THE BUTTON AGAIN"))
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
    log.info("CH+ = and CH- -, volume Up/Down, on/off P (or Home), mute M")
    asyncio.run(main())
