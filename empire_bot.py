import asyncio
import logging
import websockets as ws
import json
import re
from typing import Optional
from websockets.exceptions import ConnectionClosed

class EmpireBot:
    def __init__(self, config):
        self.config = config
        self.map_data = []
        
    async def connect(self, name: str) -> Optional[ws.WebSocketClientProtocol]:
        login_msg = self.config.LOGIN_MSG_TEMPLATE.format(
            username=self.config.USERNAME,
            password=self.config.PASSWORD
        )
        lli_msg = self.config.LLI_MSG_TEMPLATE.format(
            username=self.config.USERNAME,
            password=self.config.PASSWORD
        )

        try:
            self.websocket = await ws.connect(self.config.URL)
            logging.info(f"{name}: Connected to server")

            await self.websocket.send(self.config.VER_CHK)
            logging.info(f"{name}: Sent VER_CHK")
            response = await self.websocket.recv()
            logging.info(f"{name}: Received: {response}")

            await self.websocket.send(login_msg)
            logging.info(f"{name}: Sent Login")

            await self.websocket.send(self.config.AUTO_JOIN)
            logging.info(f"{name}: Sent AUTO_JOIN")
            await self.websocket.send(self.config.ROUND_TRIP)
            logging.info(f"{name}: Sent ROUND_TRIP")

            # Start background tasks with websocket
            asyncio.create_task(self._handle_messages(self.websocket, name))
            asyncio.create_task(self._send_pings(self.websocket, name))

            return self.websocket

        except Exception as e:
            logging.error(f"{name}: Error occurred: {e}")
            return None

    async def _handle_messages(self, ws: ws.WebSocketClientProtocol, name: str):
        while True:
            try:
                message = await ws.recv()
                if isinstance(message, bytes):
                    message = message.decode('utf-8')

                # detect lobby entry
                if message.startswith("%xt%rlu%"):
                    logging.info(f"[{self.config.USERNAME}] in lobby, sending LLI_MSG...")
                    lli_msg = self.config.LLI_MSG_TEMPLATE.format(
                        username=self.config.USERNAME,
                        password=self.config.PASSWORD
                    )
                    await ws.send(lli_msg)

                # parse map packets
                if "%xt%gaa%" in message:
                    await self._parse_gaa_packet(ws, message)

            except ConnectionClosed:
                logging.warning(f"{name}: Connection closed.")
                break


    async def _send_pings(self, ws: ws.WebSocketClientProtocol, name: str, interval: int = 45):
        while True:
            try:
                await asyncio.sleep(interval)
                await ws.send(self.config.PING_MSG)
                logging.info(f"{name}: Sent ping")
            except ConnectionClosed:
                logging.warning(f"{name}: Connection closed.")
                break

    async def scan_map(self, ws: ws.WebSocketClientProtocol):
        green_jca_command = f'%xt%EmpireEx%jca%1%{{"CID":{self.config.MC_ID},"KID":{self.config.GREEN_ID}}}%'
        await ws.send(green_jca_command)
        await ws.send('%xt%EmpireEx%gbl%1%{}%')

        for y in range(0, self.config.MAX_Y, self.config.STEP * 2):
            for x in range(0, self.config.MAX_X, self.config.STEP):
                ax1, ay1 = x, y
                ax2, ay2 = x + self.config.STEP - 1, y + self.config.STEP - 1
                await ws.send(
                    f'%xt%EmpireEx%gaa%1%{{"KID":0,"AX1":{ax1},"AY1":{ay1},"AX2":{ax2},"AY2":{ay2}}}%'
                )

                ay1_2 = y + self.config.STEP
                ay2_2 = y + self.config.STEP * 2 - 1
                if ay1_2 < self.config.MAX_Y:
                    await ws.send(
                        f'%xt%EmpireEx%gaa%1%{{"KID":0,"AX1":{ax1},"AY1":{ay1_2},"AX2":{ax2},"AY2":{ay2_2}}}%'
                    )

                await asyncio.sleep(0.1)

    async def _parse_gaa_packet(self, ws: ws.WebSocketClientProtocol, message: str):
        if "%xt%gaa%" not in message:
            return

        try:
            json_match = re.sub(r'^%xt%gaa%1%0%|\%$', '', message)
            if not json_match:
                return
            data = json.loads(json_match)

            if "AI" not in data:
                return

            seen_ids = set()

            for entry in data["AI"]:
                if not isinstance(entry, list) or len(entry) < 3:
                    continue  # skip malformed

                type_id, x, y = entry[0], entry[1], entry[2]
                player_id = None
                player_name = None

                if type_id == 1:
                    # safer: check length before accessing index 4
                    if len(entry) > 4:
                        player_id = entry[4]

                    if not player_id or player_id in seen_ids:
                        continue

                    # Try to resolve player name from OI/AP
                    if "OI" in data and isinstance(data["OI"], list):
                        for player_entry in data["OI"]:
                            if not isinstance(player_entry, dict):
                                continue
                            aps = player_entry.get("AP", [])
                            for ap_entry in aps:
                                if (
                                    isinstance(ap_entry, list)
                                    and len(ap_entry) > 3
                                    and ap_entry[2] == x
                                    and ap_entry[3] == y
                                ):
                                    player_name = player_entry.get("N")
                                    break
                            if player_name:
                                break

                    logging.info(
                        f"Resolved: (x={x}, y={y}) → ID={player_id}, Name={player_name or 'Unknown'}"
                    )
                    map_entry = {
                        "type": player_name or "Unknown",
                        "x": x,
                        "y": y,
                        "player_id": player_id,
                    }
                    self.map_data.append(map_entry)
                    seen_ids.add(player_id)

        except Exception as e:
            logging.error(f"Failed to parse GAA packet: {e}")



        except Exception as e:
            logging.error(f"Failed to parse GAA packet: {e}")

    def save_map_data(self):
        with open("map_scan_results.json", "w") as f:
            json.dump(self.map_data, f, indent=2)