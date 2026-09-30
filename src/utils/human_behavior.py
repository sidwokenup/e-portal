import random
import asyncio
from playwright.async_api import Page

async def human_delay(min_ms: float = 300, max_ms: float = 800):
    """Introduce a small randomized delay to simulate natural human pacing."""
    delay = random.uniform(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)

async def human_type(page: Page, selector: str, text: str, min_delay_ms: float = 30, max_delay_ms: float = 100):
    """Type text into an input field character by character with variable human timing and exact value verification."""
    element = await page.wait_for_selector(selector, state="visible", timeout=15000)
    await element.click()
    await human_delay(100, 200)
    await element.fill("")  # Ensure field is clean and empty before typing
    await human_delay(100, 200)
    
    for char in text:
        await element.type(char, delay=random.uniform(min_delay_ms, max_delay_ms))
        if random.random() < 0.1:  # 10% chance of a minor pause
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
    await human_delay(200, 400)
    
    # Verify exact input match (critical for passwords containing special characters like '@')
    current_val = await element.input_value()
    if current_val != text:
        await element.fill(text)
        await human_delay(100, 300)
