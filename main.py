import asyncio
import logging
from empire_bot import EmpireBot
from config import Config

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

def display_menu():
    print("\nEmpireBot Menu:")
    print("1. Scan Map")
    print("2. Exit")
    return input("Select an option: ")

async def main():
    config = Config()
    bot = EmpireBot(config)
    
    websocket = await bot.connect("EmpireBot")
    if not websocket:
        logging.error("Failed to connect. Exiting.")
        return

    logging.info("Logged in successfully.")

    while True:
        choice = await asyncio.to_thread(display_menu)

        if choice == "1":
            logging.info("Starting map scan...")
            await bot.execute_feature("map_scan")
            logging.info("Map scan completed. Data saved to map_scan_results.json.")

        elif choice == "2":
            logging.info("Exiting...")
            break

        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    asyncio.run(main())