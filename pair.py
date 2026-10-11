"""Pair with the LG TV and save the client key to .lgtv_client_key.

Run once with the TV on, then accept the prompt that appears on the TV screen.
"""
import asyncio
from pathlib import Path
from aiowebostv import WebOsClient

TV_IP = "192.168.10.232"
KEY_FILE = Path(__file__).parent / ".lgtv_client_key"

async def main():
    tv = WebOsClient(TV_IP, connect_timeout=60)
    print("Accept the pairing prompt on the TV...")
    await tv.connect()
    KEY_FILE.write_text(tv.client_key + "\n")
    print(f"Saved client key to {KEY_FILE}")
    await tv.disconnect()

asyncio.run(main())
