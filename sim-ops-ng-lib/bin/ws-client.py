
import os
import asyncio
import json
import base64
import websockets
from dotenv import load_dotenv

load_dotenv(override=False)

USER_PASSWORD = os.getenv("SIM_OPS_NG_USER_PASSWORD", "user123")
BACKEND_WS_URL = os.getenv("SIM_OPS_NG_BACKEND_WS", "ws://localhost:9111/api/ws")

async def listen():
    # password as a subprotocol, see so/api.py (WS_PASSWORD_PREFIX)
    token = base64.urlsafe_b64encode(USER_PASSWORD.encode()).decode().rstrip("=")
    async with websockets.connect(
        BACKEND_WS_URL,
        subprotocols=["sim-ops", f"sim-ops.password.{token}"],
    ) as ws:
        print("Connected")

        while True:
            data = json.loads(await ws.recv())
            print("!!", data["spacecraft"])

asyncio.run(listen())
