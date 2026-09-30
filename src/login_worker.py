import asyncio
import logging
import os
from pathlib import Path
# pyright: ignore [reportMissingImports]
from playwright.async_api import Browser, BrowserContext, Page
from src.config import UserCredential
from src.utils.human_behavior import human_delay, human_type

logger = logging.getLogger(__name__)

PORTAL_LOGIN_URL = "https://eportal.incometax.gov.in/iec/foservices/#/login"
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def login_user(browser: Browser, credential: UserCredential, keep_idle: bool = True) -> bool:
    """
    Executes isolated 2-step login workflow for a single user context.
    If keep_idle is True, keeps the context active after login instead of closing immediately.
    """
    # Create isolated browser context with standard desktop viewport & user-agent
    context: BrowserContext = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    page: Page = await context.new_page()
    logger.info(f"[{credential.user_id}] Initiating login session for PAN: {credential.pan_number}")

    try:
        # Step 1: Navigate to E-Portal Login Page
        try:
            await page.goto(PORTAL_LOGIN_URL, wait_until="commit", timeout=45000)
        except Exception:
            logger.warning(f"[{credential.user_id}] Initial navigation commit timeout, retrying domcontentloaded...")
            await page.goto(PORTAL_LOGIN_URL, wait_until="domcontentloaded", timeout=45000)

        await human_delay(1000, 2000)

        # Step 2: Fill User ID / PAN Input
        pan_input_selector = "input[aria-label*='PAN'], input[placeholder*='PAN'], input#panInput, input[type='text']"
        logger.info(f"[{credential.user_id}] Entering PAN / User ID...")
        await human_type(page, pan_input_selector, credential.pan_number)

        # Click Step 1 Continue button
        continue_btn_step1 = page.locator("button:has-text('Continue'), button[type='submit']")
        await continue_btn_step1.first.wait_for(state="visible", timeout=10000)
        await human_delay(400, 800)
        await continue_btn_step1.first.click()
        logger.info(f"[{credential.user_id}] Step 1 submitted, waiting for password screen...")

        # Step 3: Password & Secure Access Message Screen
        # In Angular Material (mat-checkbox), clicking the visible container/label triggers Angular's reactive form (change) listener.
        checkbox_container = page.locator("mat-checkbox, label:has-text('Please confirm your secure access message'), .mat-checkbox-layout").first
        await checkbox_container.wait_for(state="visible", timeout=15000)
        await human_delay(400, 800)

        # Verify if Angular Material has already marked the component as checked
        is_checked = await checkbox_container.evaluate(
            "el => el.classList.contains('mat-checkbox-checked') || el.getAttribute('aria-checked') === 'true' || (el.querySelector('input') && el.querySelector('input').checked)"
        )

        if not is_checked:
            logger.info(f"[{credential.user_id}] Clicking Secure Access Message checkbox to trigger Angular form change...")
            await checkbox_container.click()
            await human_delay(400, 800)

        # Step 4: Fill Password Field
        pwd_input_selector = "input[type='password']"
        logger.info(f"[{credential.user_id}] Entering password...")
        await human_type(page, pwd_input_selector, credential.password)

        # Trigger Angular reactive form event listeners (input, change, blur)
        pwd_element = page.locator(pwd_input_selector).first
        await pwd_element.dispatch_event("input")
        await pwd_element.dispatch_event("change")
        await pwd_element.dispatch_event("blur")
        await page.keyboard.press("Tab")
        await human_delay(500, 1000)

        # Step 5: Submit Final Login Form
        continue_btn_step2 = page.locator("button:has-text('Continue'), button[type='submit']").first
        await continue_btn_step2.wait_for(state="visible", timeout=10000)
        await continue_btn_step2.scroll_into_view_if_needed()
        await human_delay(500, 1000)

        logger.info(f"[{credential.user_id}] Submitting Step 2 Continue button...")
        await continue_btn_step2.click()
        logger.info(f"[{credential.user_id}] Step 2 submitted.")

        # Step 5a: Intercept "Request is not authenticated" Red Error Banner & Auto-Retry
        auth_error_banner = page.locator("div:has-text('Request is not authenticated'), span:has-text('Request is not authenticated'), label:has-text('Request is not authenticated')").first
        try:
            await auth_error_banner.wait_for(state="visible", timeout=3000)
            logger.warning(f"[{credential.user_id}] 'Request is not authenticated' banner detected. Waiting for Angular auth token and retrying submit...")
            await human_delay(1500, 2500)
            await continue_btn_step2.click()
            logger.info(f"[{credential.user_id}] Re-submitted Step 2 Continue button successfully.")
        except Exception:
            pass

        # Step 5b: Intercept & Handle "Dual Login Detected !" Popup Modal if present
        dual_login_modal = page.locator("div:has-text('Dual Login Detected !'), mat-dialog-container:has-text('Dual Login Detected !')").first
        try:
            await dual_login_modal.wait_for(state="visible", timeout=4000)
            logger.warning(f"[{credential.user_id}] Dual Login Detected popup appeared. Overriding prior session...")
            
            login_here_btn = page.locator("button:has-text('Login Here'), .mat-dialog-actions button:has-text('Login Here')").first
            await login_here_btn.wait_for(state="visible", timeout=5000)
            await human_delay(400, 800)
            await login_here_btn.click()
            logger.info(f"[{credential.user_id}] Clicked 'Login Here' on Dual Login modal. Prior session overridden.")
        except Exception:
            pass

        await human_delay(2000, 4000)
        
        # Save screenshot for verification
        screenshot_path = SCREENSHOT_DIR / f"login_result_{credential.user_id}.png"
        await page.screenshot(path=str(screenshot_path))
        logger.info(f"[{credential.user_id}] Login workflow executed successfully. Screenshot saved to {screenshot_path}")

        if keep_idle:
            logger.info(f"[{credential.user_id}] Session logged in. Keeping browser window active and idle...")
            while True:
                await asyncio.sleep(10)

        return True

    except asyncio.CancelledError:
        logger.info(f"[{credential.user_id}] Worker task cancelled.")
        return True
    except Exception as e:
        logger.error(f"[{credential.user_id}] Login workflow error: {e}", exc_info=True)
        try:
            err_path = SCREENSHOT_DIR / f"error_{credential.user_id}.png"
            await page.screenshot(path=str(err_path))
            logger.info(f"[{credential.user_id}] Error screenshot saved to {err_path}")
        except Exception:
            pass
        return False
    finally:
        if not keep_idle:
            await context.close()


