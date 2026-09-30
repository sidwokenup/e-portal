import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from src.config import load_credentials
from src.login_worker import login_user

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("MainEngine")

def parse_args():
    parser = argparse.ArgumentParser(description="E-Portal Automation Engine")
    parser.add_argument(
        "--user-id",
        type=str,
        default=os.getenv("TARGET_USER_ID"),
        help="Target a specific user_id (e.g. user_1) from config or env"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes"),
        help="Run browser in headless mode (default true in Docker)"
    )
    parser.add_argument(
        "--no-keep-idle",
        action="store_true",
        default=os.getenv("KEEP_IDLE", "true").lower() not in ("true", "1", "yes"),
        help="Exit immediately after login test completes without keeping idle"
    )
    return parser.parse_args()

async def main():
    args = parse_args()
    keep_idle = not args.no_keep_idle

    # Auto-initialize config/users.json from example if needed
    config_file = Path("config/users.json")
    if not config_file.exists() and not (os.getenv("PAN_NUMBER") and os.getenv("PASSWORD")):
        example_config = Path("config/users.example.json")
        if example_config.exists():
            logger.info("config/users.json not found. Initializing from config/users.example.json...")
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(example_config.read_text(encoding="utf-8"), encoding="utf-8")

    try:
        credentials = load_credentials("config/users.json", target_user_id=args.user_id)
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        sys.exit(1)

    if not credentials:
        logger.error("No valid credentials found via environment variables or config/users.json!")
        sys.exit(1)

    logger.info(
        f"Starting engine | Users: {[c.user_id for c in credentials]} | "
        f"Headless: {args.headless} | Keep Idle: {keep_idle}"
    )

    # Chromium flags optimized for Docker containers and evasion
    chromium_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=args.headless,
            args=chromium_args
        )

        tasks = []
        for idx, cred in enumerate(credentials):
            if idx > 0:
                await asyncio.sleep(2.5)
            tasks.append(asyncio.create_task(login_user(browser, cred, keep_idle=keep_idle)))

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            all_success = True
            for cred, res in zip(credentials, results):
                is_success = res is True
                status = "SUCCESS" if is_success else f"FAILED ({res})"
                logger.info(f"User [{cred.user_id}] ({cred.pan_number}): {status}")
                if not is_success:
                    all_success = False

            if not all_success:
                sys.exit(1)

        except asyncio.CancelledError:
            logger.info("Automation process interrupted. Closing browser...")
        except Exception as e:
            logger.error(f"Execution error: {e}")
            sys.exit(1)
        finally:
            try:
                await browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process stopped cleanly by user (Ctrl+C). Exiting.")


