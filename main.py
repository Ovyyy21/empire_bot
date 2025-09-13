import asyncio
import logging
from empire_bot import EmpireBot
from config import Config

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

async def main():
    config = Config()
    bot = EmpireBot(config)
    
    websocket = await bot.connect("EmpireBot")
    if websocket:
        logging.info("Logged in successfully. Ready to scan map.")
        
        print("Press ENTER to start map scan...")
        await asyncio.to_thread(input)
        
        await bot.scan_map(websocket)
        await asyncio.sleep(0.5)
        bot.save_map_data()
        logging.info("Map data saved to map_scan_results.json.")
        
        # Keep alive forever
        while True:
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())