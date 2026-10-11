"""Sets up the big-button remote: press the button you've labelled for each channel.

Stop the service first (sudo systemctl stop thatha-tv) so it doesn't react to
the presses, and point the remote at the Flirc receiver. Saves buttons.json.
"""
import asyncio
import json
import evdev
from evdev import ecodes
import live_tv
from buttons import BUTTONS_FILE, is_keyboard, key_name

async def read_presses(device, queue):
    async for event in device.async_read_loop():
        if event.type == ecodes.EV_KEY and event.value == 1:  # press only, not repeats while held
            await queue.put(event.code)

async def main():
    devices = [d for d in map(evdev.InputDevice, evdev.list_devices()) if is_keyboard(d)]
    if not devices:
        raise SystemExit("No receiver found - is the Flirc plugged in?")
    for d in devices:
        d.grab()                                              # keep presses off the terminal
    presses = asyncio.Queue()
    readers = [asyncio.ensure_future(read_presses(d, presses)) for d in devices]
    print("Listening on:", ", ".join(d.name for d in devices))
    print("Press the button for each channel. Press a button that is already used to skip a channel.\n")

    saved = {}
    for channel in sorted(live_tv.CHANNELS, key=int):
        print(f"Channel {channel}: ", end="", flush=True)
        code = await presses.get()
        name = key_name(code)
        if name in saved.values():
            print("skipped (button already used)")
            continue
        saved[channel] = name
        print(name)

    for r in readers:
        r.cancel()
    BUTTONS_FILE.write_text(json.dumps(saved, indent=2) + "\n")
    print(f"\nSaved {len(saved)} buttons to {BUTTONS_FILE.name}. Start the service: sudo systemctl start thatha-tv")

asyncio.run(main())
