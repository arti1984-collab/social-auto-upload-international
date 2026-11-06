"""Publish videos to a Facebook profile through Patchright.

This uses the profile/home composer on the Facebook feed. Meta Business Suite's Page
publishing and scheduling need a different signed-in entity and permissions, so they are never mixed into the profile flow.
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from patchright.async_api import Page, Playwright, async_playwright, expect

from utils.browser import open_session, session_available
from utils.log import facebook_logger


FACEBOOK_HOME_URL = "https://www.facebook.com/"
# The proxy comes only from an explicit CLI flag or a user-set environment variable; unset means a direct connection.
FACEBOOK_PROXY = os.environ.get("SAU_FACEBOOK_PROXY")
FACEBOOK_LOGIN_INPUT = 'input[name="email"]'
# The feed composer accepts images and videos, while avatar/cover controls never expose this MIME set.
FACEBOOK_MEDIA_INPUT = 'input[type="file"][accept*="image/"][accept*="video/"]'
# The composer dialog's own submit action, per UI language of the account.
PUBLISH_LABELS = ("Posten", "Publish", "Post", "Teilen", "Share", "发布")
# The dialog that owns a composer text box; the live Reel composer carries no aria-modal attribute.
COMPOSER_DIALOG = '[role="dialog"]:has([contenteditable="true"][role="textbox"])'


def _proxy_options(proxy: str | None) -> dict[str, str] | None:
    """Use the explicit environment configuration when no argument is given and connect directly otherwise; an empty string overrides the environment and connects directly."""
    address = (FACEBOOK_PROXY if proxy is None else proxy) or ""
    address = address.strip()
    return {"server": address} if address else None


async def _is_logged_out(page: Page) -> bool:
    """Decide whether the session is valid from login-flow markers and the feed composer anchors."""
    current_url = page.url.lower()
    # two_step_verification is the 2FA page of the login flow, never the signed-in feed.
    if any(
        marker in current_url
        for marker in ("/login", "checkpoint", "two_step_verification", "/authentication/")
    ):
        return True
    email_input = page.locator(FACEBOOK_LOGIN_INPUT)
    if await email_input.count() and await email_input.first.is_visible():
        return True
    # The composer's file input proves the feed is mounted; a blank or signing-in page never counts as signed in.
    return await page.locator(FACEBOOK_MEDIA_INPUT).count() == 0


async def _open_facebook_page(playwright: Playwright, account_file: Path, *, proxy: str | None, headless: bool):
    """Open Facebook with a storage state and carry the proxy configuration into the browser process."""
    browser, context = await open_session(
        playwright, account_file, headless=headless, proxy=_proxy_options(proxy)
    )
    try:
        page = await context.new_page()
        page.set_default_timeout(30_000)
        await page.goto(FACEBOOK_HOME_URL, wait_until="domcontentloaded", timeout=90_000)
        await page.locator("body").wait_for(state="visible", timeout=30_000)
        return browser, context, page
    except Exception:
        # Once navigation or the storage state fails the browser belongs to this function, so release it before raising.
        await browser.close()
        raise


async def facebook_cookie_auth(account_file: str | Path, *, proxy: str | None = None) -> bool:
    """Check whether the saved Facebook storage state still reaches the signed-in feed."""
    account_file = Path(account_file)
    if not session_available(account_file):
        return False
    async with async_playwright() as playwright:
        browser, context, page = await _open_facebook_page(
            playwright, account_file, proxy=proxy, headless=True
        )
        try:
            return not await _is_logged_out(page)
        finally:
            await browser.close()


async def facebook_setup(
    account_file: str | Path,
    *,
    handle: bool = False,
    return_detail: bool = False,
    headless: bool = False,
    proxy: str | None = None,
    timeout_seconds: int = 600,
):
    """Validate the session; the login command waits in a visible browser until the user finishes signing in, then saves it."""
    account_file = Path(account_file)
    account_file.parent.mkdir(parents=True, exist_ok=True)
    valid = await facebook_cookie_auth(account_file, proxy=proxy)
    if valid:
        result = {
            "success": True,
            "status": "cookie_valid",
            "message": "Facebook session is valid",
            "account_file": str(account_file),
        }
        return result if return_detail else True
    if not handle:
        result = {
            "success": False,
            "status": "cookie_invalid",
            "message": "Facebook session missing or expired",
            "account_file": str(account_file),
        }
        return result if return_detail else False

    async with async_playwright() as playwright:
        browser, context = await open_session(
            playwright, account_file, headless=headless, proxy=_proxy_options(proxy)
        )
        try:
            page = await context.new_page()
            page.set_default_timeout(30_000)
            await page.goto(FACEBOOK_HOME_URL, wait_until="domcontentloaded", timeout=90_000)
            facebook_logger.info("Finish signing in in the opened Facebook browser; the session is saved automatically")
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            while asyncio.get_running_loop().time() < deadline:
                if not await _is_logged_out(page):
                    await context.storage_state(path=str(account_file))
                    result = {
                        "success": True,
                        "status": "logged_in",
                        "message": "Facebook sign-in succeeded, session saved",
                        "account_file": str(account_file),
                        "current_url": page.url,
                    }
                    return result if return_detail else True
                await page.wait_for_timeout(1000)
            result = {
                "success": False,
                "status": "timeout",
                "message": "Timed out waiting for the Facebook sign-in; session not saved",
                "account_file": str(account_file),
                "current_url": page.url,
            }
            return result if return_detail else False
        finally:
            await browser.close()


class FacebookPost:
    """Publish one video or a set of images through the profile composer."""

    def __init__(
        self,
        title: str,
        file_path: str | Path | list[Path],
        description: str,
        tags: list[str],
        account_file: str | Path,
        proxy: str | None = None,
        headless: bool = True,
    ):
        self.title = title.strip()
        self.files = [Path(item) for item in file_path] if isinstance(file_path, list) else [Path(file_path)]
        self.file_path = self.files[0] if self.files else Path()
        self.description = description.strip()
        self.tags = [tag.strip().lstrip("#") for tag in tags if tag.strip().lstrip("#")]
        self.account_file = Path(account_file)
        self.proxy = proxy
        self.headless = headless

    def _caption(self) -> str:
        """The Facebook feed has no separate video title field, so the title is merged into the text by project convention."""
        parts = [part for part in (self.title, self.description) if part]
        if self.tags:
            parts.append(" ".join(f"#{tag}" for tag in self.tags))
        return "\n\n".join(parts)

    async def _find_caption_editor(self, page: Page):
        # The composer dialog owns a text box and needs no aria-modal attribute; hidden templates and
        # the feed comment box never match this combination, so exactly one dialog stays.
        await expect(page.locator(COMPOSER_DIALOG)).to_have_count(1)
        editor = page.locator(COMPOSER_DIALOG).locator('[contenteditable="true"][role="textbox"]')
        await expect(editor).to_have_count(1)
        return editor

    async def _find_publish_button(self, page: Page):
        # The submit control carries the dialog's own label, so no position inside the form is guessed.
        dialog = page.locator(COMPOSER_DIALOG)
        await expect(dialog).to_have_count(1)
        for label in PUBLISH_LABELS:
            button = dialog.get_by_role('button', name=label, exact=True)
            if await button.count() == 1:
                await expect(button).to_be_visible()
                return button
        raise RuntimeError('Publish button not found in the composer dialog')

    async def _wait_until_publishable(self, page: Page) -> None:
        deadline = asyncio.get_running_loop().time() + 180
        while asyncio.get_running_loop().time() < deadline:
            error = page.locator('[role="dialog"] [role="alert"]')
            if await error.count() and await error.first.is_visible():
                message = (await error.first.inner_text()).strip()
                if message:
                    raise RuntimeError(f"Facebook upload failed: {message}")
            try:
                publish_button = await self._find_publish_button(page)
                if await publish_button.is_enabled():
                    return
            except RuntimeError as exc:
                if "Publish button not found" not in str(exc):
                    raise
            await page.wait_for_timeout(1000)
        raise TimeoutError("Facebook upload or processing timed out; the publish button never became ready")

    async def _publish_and_verify(self, page: Page) -> None:
        publish_button = await self._find_publish_button(page)
        # The verified success toast is a full sentence, so any "published" wording in the feed is not proof for this post.
        success_pattern = re.compile(r"^(?:你的帖子已成功分享给.+|你的帖子已发布|Your post has been published[.!]?)$", re.I)
        success_text = page.get_by_text(success_pattern)
        for index in range(await success_text.count()):
            if await success_text.nth(index).is_visible():
                raise RuntimeError("A success toast already existed before submitting, so this post's result is unknown; nothing was submitted")
        await publish_button.click()
        deadline = asyncio.get_running_loop().time() + 90
        while asyncio.get_running_loop().time() < deadline:
            # Only a status toast or success toast counts; a closed dialog alone does not prove the server accepted it.
            success_text = page.get_by_text(success_pattern)
            if await success_text.count():
                for index in range(await success_text.count()):
                    if await success_text.nth(index).is_visible():
                        return
            await page.wait_for_timeout(1000)
        raise TimeoutError("Clicked Facebook publish but never saw an explicit success state")

    async def upload(self, playwright: Playwright) -> None:
        if not self.files:
            raise ValueError("Facebook publish media must not be empty")
        for file in self.files:
            if not file.is_file():
                raise FileNotFoundError(f"Facebook media file not found: {file}")
        if not self.title:
            raise ValueError("Facebook video title must not be empty")
        if not self.account_file.is_file():
            raise RuntimeError(f"Facebook session file not found: {self.account_file}")

        browser, context, page = await _open_facebook_page(
            playwright, self.account_file, proxy=self.proxy, headless=self.headless
        )
        try:
            if await _is_logged_out(page):
                raise RuntimeError("Facebook session expired; run sau facebook login first")

            # The verified single mixed-media input on the feed; its accept list limits it to images and videos and excludes avatar controls.
            file_input = page.locator(FACEBOOK_MEDIA_INPUT)
            if await file_input.count() != 1:
                raise RuntimeError("The feed composer media input is not unique; nothing uploaded")
            await file_input.set_input_files([str(file) for file in self.files])

            # The composer mounts asynchronously after the file is chosen, so a same-turn count check cannot declare the input missing.
            await page.locator('[role="dialog"] [contenteditable="true"][role="textbox"]:visible').wait_for(timeout=30000)
            editor = await self._find_caption_editor(page)
            caption = self._caption()
            await editor.click()
            await editor.fill(caption)
            if (await editor.inner_text()).strip() != caption:
                raise RuntimeError("The Facebook text box did not read back the expected content")

            await self._wait_until_publishable(page)
            await self._publish_and_verify(page)
            await context.storage_state(path=str(self.account_file))
        finally:
            await browser.close()

    async def main(self) -> None:
        async with async_playwright() as playwright:
            await self.upload(playwright)


# Keep the class name video callers use; video and image posts share one form and no extra wrapper.
FacebookVideo = FacebookPost
