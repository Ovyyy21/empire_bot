import asyncio
import logging
import websockets as ws
import json
import re
import time
from typing import Optional, Dict, Callable
from websockets.exceptions import ConnectionClosed

class Feature:
    def __init__(self, bot: 'EmpireBot'):
        self.bot = bot
        self.saves_data = False  # Default: feature doesn't save data

    async def handle_message(self, ws: ws.WebSocketClientProtocol, message: str) -> bool:
        return False

    async def execute(self, ws: ws.WebSocketClientProtocol, *args, **kwargs):
        pass

    def save_data(self):
        pass  # Default: do nothing

class MapScanner(Feature):
    """Feature for scanning the game map."""
    def __init__(self, bot: 'EmpireBot'):
        super().__init__(bot)
        self.map_data = []
        self.saves_data = True  # MapScanner saves data

    async def handle_message(self, ws: ws.WebSocketClientProtocol, message: str) -> bool:
        if "%xt%gaa%" in message:
            await self._parse_gaa_packet(ws, message)
            return True
        return False

    async def execute(self, ws: ws.WebSocketClientProtocol):
        green_jca_command = f'%xt%EmpireEx%jca%1%{{"CID":{self.bot.config.MC_ID},"KID":{self.bot.config.GREEN_ID}}}%'
        await ws.send(green_jca_command)
        await ws.send('%xt%EmpireEx%gbl%1%{}%')

        for y in range(0, self.bot.config.MAX_Y, self.bot.config.STEP * 2):
            for x in range(0, self.bot.config.MAX_X, self.bot.config.STEP):
                ax1, ay1 = x, y
                ax2, ay2 = x + self.bot.config.STEP - 1, y + self.bot.config.STEP - 1
                await ws.send(
                    f'%xt%EmpireEx%gaa%1%{{"KID":0,"AX1":{ax1},"AY1":{ay1},"AX2":{ax2},"AY2":{ay2}}}%'
                )
                ay1_2 = y + self.bot.config.STEP
                ay2_2 = y + self.bot.config.STEP * 2 - 1
                if ay1_2 < self.bot.config.MAX_Y:
                    await ws.send(
                        f'%xt%EmpireEx%gaa%1%{{"KID":0,"AX1":{ax1},"AY1":{ay1_2},"AX2":{ax2},"AY2":{ay2_2}}}%'
                    )
                await asyncio.sleep(0.1)

    async def _parse_gaa_packet(self, ws: ws.WebSocketClientProtocol, message: str):
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
                    continue
                type_id, x, y = entry[0], entry[1], entry[2]
                player_id = entry[4] if len(entry) > 4 else None

                if type_id == 1 and player_id and player_id not in seen_ids:
                    player_name = None
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

    def save_data(self):
        with open("map_scan_results.json", "w") as f:
            json.dump(self.map_data, f, indent=2)

class CommanderHandler:
    """Class to handle fetching commander movement data from gam messages during login."""
    def __init__(self, bot: 'EmpireBot'):
        self.bot = bot
        self.websocket = None
        self.saves_data = True  # This component saves data
        self.message_index = 0  # Index for gam message files

    def reset_index(self):
        """Reset message index at the start of a login session."""
        self.message_index = 0

    async def handle_message(self, message: str):
        """Handle and save responses starting with %xt%gam%1%0% to indexed files."""
        if message.startswith('%xt%gam%1%0%'):
            try:
                # Log the raw message for debugging
                logging.debug(f"Received gam message: {message[:200]}...")
                # Extract JSON from the gam packet
                json_data = re.sub(r'^%xt%gam%1%0%|\%$', '', message)
                if json_data:
                    data = json.loads(json_data)
                    # Log the parsed data
                    logging.debug(f"Parsed gam data: {json.dumps(data, indent=2)}")
                    # Skip saving if data is empty
                    if data.get("M") == [] and data.get("O") == []:
                        logging.info("Skipping empty gam data")
                        return
                    # Increment index and save to file
                    self.message_index += 1
                    filename = f"gam_{self.message_index}.json"
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    logging.info(f"Saved commander data to {filename}")
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode gam message JSON: {e} - Raw message: {message[:100]}...")
            except Exception as e:
                logging.error(f"Failed to save commander data: {e} - Context: {message[:100]}...")

class EmpireBot:
    def __init__(self, config):
        self.config = config
        self.websocket = None
        self.commander_handler = CommanderHandler(self)
        self.features: Dict[str, Feature] = {
            "map_scan": MapScanner(self)
        }
        self.message_handlers: Dict[str, Callable] = {
            "%xt%rlu%": self._handle_lobby_entry,
        }

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

                # Route to core handlers
                for pattern, handler in self.message_handlers.items():
                    if pattern in message:
                        await handler(ws, message)
                        break  # Stop after first core handler match

                await self.commander_handler.handle_message(message)

                # Route to features
                for feature in self.features.values():
                    if await feature.handle_message(ws, message):
                        break  # Stop if feature handled the message
            except ConnectionClosed:
                logging.warning(f"{name}: Connection closed.")
                break

    async def _handle_lobby_entry(self, ws: ws.WebSocketClientProtocol, message: str):
        logging.info(f"[{self.config.USERNAME}] in lobby, sending LLI_MSG...")
        lli_msg = self.config.LLI_MSG_TEMPLATE.format(
            username=self.config.USERNAME,
            password=self.config.PASSWORD
        )
        await ws.send(lli_msg)
        # Reset message index for new login session
        self.commander_handler.reset_index()

    async def _send_pings(self, ws: ws.WebSocketClientProtocol, name: str, interval: int = 45):
        while True:
            try:
                await asyncio.sleep(interval)
                await ws.send(self.config.PING_MSG)
                logging.info(f"{name}: Sent ping")
            except ConnectionClosed:
                logging.warning(f"{name}: Connection closed.")
                break

    async def execute_feature(self, feature_name: str, *args, **kwargs):
        feature = self.features.get(feature_name)
        if feature and self.websocket:
            await feature.execute(self.websocket, *args, **kwargs)
            if feature.saves_data:
                feature.save_data()