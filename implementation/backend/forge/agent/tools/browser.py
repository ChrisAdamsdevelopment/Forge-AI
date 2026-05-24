from __future__ import annotations

import base64
from typing import Any

_playwright = None
_browser: Any = None
_context: Any = None
_page: Any = None


async def _get_page() -> Any:
    global _playwright, _browser, _context, _page
    from playwright.async_api import async_playwright
    if _page and not _page.is_closed():
        return _page

    if _playwright is None:
        _playwright = await async_playwright().start()

    if _browser is None or not _browser.is_connected():
        _browser = await _playwright.chromium.launch(headless=False)

    if _context is None:
        _context = await _browser.new_context()

    _page = await _context.new_page()
    return _page


async def browser_navigate(url: str) -> dict[str, str]:
    """Navigate browser to the provided URL."""
    page = await _get_page()
    response = await page.goto(url, wait_until="domcontentloaded")
    title = await page.title()
    status = str(response.status) if response else "unknown"
    return {"url": page.url, "title": title, "status": status}


async def browser_screenshot() -> dict[str, str]:
    """Capture a screenshot for the current page and return it as base64."""
    page = await _get_page()
    png_bytes = await page.screenshot(full_page=True)
    encoded = base64.b64encode(png_bytes).decode("utf-8")
    return {"screenshot_base64": encoded, "url": page.url}


async def browser_click(selector: str) -> dict[str, str]:
    """Click a page element using a CSS selector."""
    page = await _get_page()
    await page.click(selector)
    return {"status": "ok", "selector": selector, "url": page.url}


async def browser_type(selector: str, text: str) -> dict[str, str]:
    """Type text into an input selected by CSS selector."""
    page = await _get_page()
    await page.fill(selector, text)
    return {"status": "ok", "selector": selector, "url": page.url}


async def browser_get_content() -> dict[str, Any]:
    """Return visible page text and basic interactive element metadata."""
    page = await _get_page()
    body_text = await page.locator("body").inner_text()
    buttons = await page.eval_on_selector_all(
        "button, input[type='button'], input[type='submit']",
        """els => els.map(e => ({text: (e.innerText || e.value || '').trim(), selector: e.tagName.toLowerCase()}))""",
    )
    inputs = await page.eval_on_selector_all(
        "input, textarea",
        """els => els.map(e => ({name: e.name || '', type: e.type || e.tagName.toLowerCase(), placeholder: e.placeholder || ''}))""",
    )
    return {"url": page.url, "text": body_text, "buttons": buttons, "inputs": inputs}
