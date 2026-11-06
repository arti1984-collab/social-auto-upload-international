"""Headless browser for the DOM tests.

The uploaders drive an installed Chrome by default. On a machine without Chrome
the driver's own Chromium build still exists, so the DOM, event and byte checks
run against it instead of being skipped.
"""
from utils.browser import launch, set_default_browser

FALLBACK = "chromium"


async def launch_test_browser(playwright, browser: str = "chrome"):
    """Launch the requested browser, falling back to the bundled Chromium build."""
    set_default_browser(browser)
    try:
        return await launch(playwright, headless=True)
    except Exception:
        set_default_browser(FALLBACK)
        return await launch(playwright, headless=True)
