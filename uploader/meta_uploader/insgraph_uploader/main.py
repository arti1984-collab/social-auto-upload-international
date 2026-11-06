"""Instagram standalone web session plus photo, carousel and Reels publishing."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from patchright.async_api import Locator, Page, Playwright, TimeoutError as BrowserTimeoutError, async_playwright, expect

from utils.browser import (
    launch,
    launch_persistent,
    open_session,
    profile_directory,
    profile_mode,
    session_available,
)

INSTAGRAM_HOME_URL = "https://www.instagram.com/"
# Without an environment variable or --proxy the system connects directly.
INSTAGRAM_PROXY = os.environ.get("SAU_INSTAGRAM_PROXY")
# The create dialog's accept covers photos and MP4, so this attribute pins the media entry and excludes the cover input of the edit step.
INSTAGRAM_MEDIA_INPUT = 'input[type="file"][accept*="video/mp4"]'
# _ac76 is the wizard header shared by the crop, edit and caption steps in both locales; the main action has no SVG while back does.
INSTAGRAM_PRIMARY_ACTION = '._ac76 [role="button"]:not(:has(svg))'


async def _dismiss_optional_prompt(guide: Locator, dismiss_button: Locator) -> bool:
    """Dismiss only recognized optional prompts; absence may continue, but a failed action on a shown prompt must raise."""
    try:
        await guide.wait_for(state='visible', timeout=1500)
    except BrowserTimeoutError:
        return False
    await expect(dismiss_button).to_have_count(1)
    await dismiss_button.click()
    await guide.wait_for(state='hidden')
    return True


def _proxy_options(proxy: str | None) -> dict[str, str] | None:
    """Use the explicit environment configuration when no argument is given and connect directly otherwise; an empty string overrides it and connects directly."""
    address = (INSTAGRAM_PROXY if proxy is None else proxy) or ""
    address = address.strip()
    return {"server": address} if address else None


async def _open_instagram_page(playwright: Playwright, account_file: Path, *, proxy: str | None, headless: bool):
    """Use the project Chrome with a given storage state and let navigation errors propagate unchanged."""
    browser, context = await open_session(
        playwright, account_file, headless=headless, proxy=_proxy_options(proxy)
    )
    try:
        page = await context.new_page()
        page.set_default_timeout(30_000)
        await page.goto(INSTAGRAM_HOME_URL, wait_until="domcontentloaded", timeout=120_000)
        return browser, context, page
    except Exception:
        await browser.close()
        raise


async def _is_instagram_logged_out(page: Page) -> bool:
    """Wait for an explicit signed-in or signed-out area; a network or unknown-page timeout never means the cookie expired."""
    # The message entry is the signed-in nav whose href may carry extra hl parameters; the login form fields do not depend on translations.
    outcomes = page.locator('a[href^="/direct/inbox/"], input[name="username"], a[href^="/accounts/login/"]')
    await expect(outcomes).not_to_have_count(0, timeout=60_000)
    return not await page.locator('a[href^="/direct/inbox/"]').count()


async def instagram_identity(page: Page, account_file: Path) -> dict:
    """Compare the session's user id with the one bound to the account file and read that user's profile nav."""
    if await _is_instagram_logged_out(page):
        raise RuntimeError("Instagram is not signed in; run sau instagram login")
    current = {c['value'] for c in await page.context.cookies(INSTAGRAM_HOME_URL) if c['name'] == 'ds_user_id'}
    if account_file.is_file():
        state = json.loads(account_file.read_text(encoding="utf-8"))
        expected = {c['value'] for c in state['cookies'] if c['name'] == 'ds_user_id' and c['domain'].lstrip('.') == 'instagram.com'}
    else:
        # A persistent profile has no exported cookie file, so the live session is its own reference.
        expected = current
    if len(expected) != 1 or current != expected:
        raise RuntimeError("The signed-in Instagram user does not match the id bound to the account file")
    # The current user's nav avatar sits in an aria-selected icon container while feed and suggested avatars are never nav-selected.
    own_profile = page.locator('a[href]').filter(has=page.locator('[aria-selected] img'))
    await expect(own_profile).to_have_count(1)
    href = await own_profile.get_attribute('href')
    username = urlparse(href).path.strip('/')
    if not username or '/' in username:
        raise RuntimeError("The Instagram profile link structure is unexpected")
    return {"user_id": next(iter(expected)), "username": username}


async def instagram_cookie_auth(account_file: str | Path, *, proxy: str | None = None) -> bool:
    """Verify sign-in and account binding independently; unknown pages and network errors are reported as they are."""
    account_file = Path(account_file)
    if not session_available(account_file):
        return False
    async with async_playwright() as playwright:
        browser, context, page = await _open_instagram_page(playwright, account_file, proxy=proxy, headless=True)
        try:
            if await _is_instagram_logged_out(page):
                return False
            await instagram_identity(page, account_file)
            return True
        finally:
            await browser.close()


async def instagram_setup(account_file: str | Path, *, handle: bool = False, proxy: str | None = None,
                          headless: bool = False, return_detail: bool = False, timeout_seconds: int = 900):
    """Manual login in the project browser: export a candidate state, verify it in a fresh context, then replace the account file."""
    account_file = Path(account_file)
    account_file.parent.mkdir(parents=True, exist_ok=True)
    if await instagram_cookie_auth(account_file, proxy=proxy):
        result = {"success": True, "status": "cookie_valid", "account_file": str(account_file)}
        return result if return_detail else True
    if not handle:
        result = {"success": False, "status": "cookie_invalid", "account_file": str(account_file)}
        return result if return_detail else False
    async with async_playwright() as p:
        candidate = account_file.with_name(f'{account_file.stem}.{uuid4().hex}.pending.json')
        if profile_mode():
            # The profile is the session store, so nothing has to be exported or verified afterwards.
            browser = context = await launch_persistent(
                p, headless=headless, proxy=_proxy_options(proxy), args=["--start-maximized"],
                profile=profile_directory(account_file),
            )
        else:
            browser = await launch(p, headless=headless, proxy=_proxy_options(proxy), args=["--start-maximized"])
            context = None
        try:
            if context is None:
                context = await browser.new_context(no_viewport=not headless)
            page = await context.new_page()
            await page.goto(INSTAGRAM_HOME_URL + 'accounts/login/', wait_until='domcontentloaded', timeout=120_000)
            # The message entry appears only after manual login and any challenge; never declare success from a URL or a vanished form.
            await page.locator('a[href^="/direct/inbox/"]').wait_for(state='visible', timeout=timeout_seconds * 1000)
            if profile_mode():
                result = {"success": True, "status": "logged_in", "account_file": str(account_file)}
                return result if return_detail else True
            await context.storage_state(path=str(candidate))
            if not await instagram_cookie_auth(candidate, proxy=proxy):
                raise RuntimeError('The exported Instagram state failed verification in a new session')
            candidate.replace(account_file)
            result = {"success": True, "status": "logged_in", "account_file": str(account_file)}
            return result if return_detail else True
        finally:
            candidate.unlink(missing_ok=True)
            await browser.close()


def instagram_response_payload(body: str) -> dict:
    """Parse the observed plain JSON and Meta's JSON-hijacking prefix; any other format raises."""
    if body.startswith('for (;;);'):
        body = body[len('for (;;);'):]
    return json.loads(body)


def instagram_created_media(payload: dict, *, owner_id: str, caption: str) -> dict:
    """Accept only the final create response whose post matches user and caption; neither processing nor HTTP 200 is success."""
    envelope = payload
    payload = envelope.get('payload', envelope)
    if envelope.get('error') or payload.get('status') not in (None, 'ok') or ('statusCode' in payload and payload['statusCode'] != 200):
        raise RuntimeError(f"Instagram create did not succeed: {payload.get('message', payload.get('statusCode', payload.get('status')))}")
    media = payload.get('media') or {}
    if not media.get('code') or not media.get('id'):
        raise RuntimeError('The Instagram create response has no post id')
    if str((media.get('user') or {}).get('pk')) != owner_id:
        raise RuntimeError("The Instagram create response's author id does not match")
    if (media.get('caption') or {}).get('text') != caption:
        raise RuntimeError("The Instagram create response's caption does not match")
    return media


class InstagramUploader:
    """Publish immediately on the standalone site and return the post link once the final create response confirms it."""

    def __init__(self, account_file: str | Path, *, title: str, description: str = '', tags: list[str] | None = None,
                 video_file: str | Path | None = None, image_files: list[str | Path] | None = None,
                 thumbnail: str | Path | None = None,
                 proxy: str | None = None, headless: bool = False, result_file: str | Path | None = None):
        self.account_file = Path(account_file)
        self.title, self.description = title.strip(), description.strip()
        self.tags = [t.strip().lstrip('#') for t in (tags or []) if t.strip().lstrip('#')]
        self.video_file = Path(video_file) if video_file else None
        self.image_files = [Path(p) for p in (image_files or [])]
        self.thumbnail = Path(thumbnail) if thumbnail else None
        if self.thumbnail and not self.video_file:
            raise ValueError('An Instagram custom cover is only used for videos/Reels')
        if bool(self.video_file) == bool(self.image_files):
            raise ValueError('Exactly one video or image file is required')
        if not self.title:
            raise ValueError('Title must not be empty')
        self.proxy, self.headless = proxy, headless
        self.result_file = Path(result_file) if result_file else Path('.local/instagram-results') / f'{uuid4().hex}.json'
        self.result = {'platform': 'instagram', 'title': self.title, 'status': 'not_submitted'}
        self.stage = 'validation'
        if len(self._caption()) > 2200:
            raise ValueError('The Instagram caption (title, body and tags together) must not exceed 2200 characters')

    def _caption(self) -> str:
        """Instagram only has a caption, so the CLI title, body and tags are merged."""
        parts = [p for p in (self.title, self.description) if p]
        if self.tags:
            parts.append(' '.join(f'#{t}' for t in self.tags))
        return '\n\n'.join(parts)

    async def _upload_files(self, page: Page) -> None:
        """Open the create entry and wait for the crop step instead of inferring readiness from a fixed delay after upload."""
        # The real prompt uses this fixed icon and the _a9-z action area; its two items are enable and later,
        # so take the second direct child button; scoping by icon and local action area avoids translated labels or page-wide buttons.
        notifications = page.get_by_role('dialog').filter(
            has=page.locator('img[src^="/images/instagram/xig/ico/xxhdpi_launcher.png"]'))
        notification_buttons = notifications.locator('._a9-z > button')
        # Both locales show these four nav popovers: notifications, create, settings, Meta.
        # Assert the whole group and each entry's aria-selected icon before taking business item two instead of a page-wide nth.
        navigation_popups = page.locator('a._a6hd[href="#"]').filter(has=page.locator('[aria-selected]'))
        # The prompt can appear after the nav, so handle this known overlay during the action check instead of checking absence first
        # and racing the click; with no prompt the callback never runs and no fixed wait is added.
        await page.add_locator_handler(notifications, lambda: _dismiss_optional_prompt(notifications, notification_buttons.nth(1)))
        try:
            await expect(navigation_popups).to_have_count(4)
            await navigation_popups.nth(1).click()
        finally:
            await page.remove_locator_handler(notifications)
        dialog = page.get_by_role('dialog')
        await expect(dialog).to_have_count(1)
        file_input = dialog.locator(INSTAGRAM_MEDIA_INPUT)
        await expect(file_input).to_have_count(1)
        paths = [self.video_file] if self.video_file else self.image_files
        await file_input.set_input_files([str(p.resolve()) for p in paths])
        if self.video_file:
            # The real Reels intro uses reels_nux_icon; its learn-more action sits in a span
            # while the confirm button is a direct div child, so local parent/child structure is used instead of language or style hashes.
            reels_intro = page.get_by_role('dialog').filter(
                has=page.locator('img[src^="/images/instagram/clips/reels_nux_icon.png"]'))
            await _dismiss_optional_prompt(reels_intro, reels_intro.locator('._a9-z div > button'))
        # Advance only once the crop header's main action is really there; an upload failure or unknown dialog blocks and raises with the page kept.
        await expect(dialog.locator(INSTAGRAM_PRIMARY_ACTION)).to_have_count(1, timeout=60_000)

    async def _advance_media_editor(self, page: Page) -> None:
        """Wait for the title to change in the crop and edit steps, then confirm through the Lexical caption editor."""
        # One create dialog header spans all three steps; its local main action has no icon, excluding back and media tool buttons.
        dialog = page.get_by_role('dialog')
        heading = dialog.locator('._ac76 [role="heading"]')
        for step in range(2):
            if step == 1 and self.thumbnail:
                # In the video edit dialog the exact JPEG/PNG accept is the separate cover entry, excluding the initial video input.
                cover = dialog.locator('input[type="file"][accept="image/jpeg,image/png"]')
                # The main preview video sits next to the cover background layer; the right-hand filmstrip has one too, so it cannot verify a cover.
                poster = dialog.locator('video + div[style*="background-image"]')
                await expect(cover).to_have_count(1)
                await expect(poster).to_have_count(1)
                previous_style = await poster.get_attribute('style')
                await cover.set_input_files(str(self.thumbnail.resolve()))
                await expect(poster).not_to_have_attribute('style', previous_style, timeout=30_000)
                # The observed page swaps the cover with the original blob directly; compare and decode the real preview bytes, since a selected file proves nothing.
                preview = await asyncio.wait_for(poster.evaluate('''async element => {
                    const background = getComputedStyle(element).backgroundImage;
                    const url = background.slice(5, -2);
                    const blob = await (await fetch(url)).blob();
                    const bitmap = await createImageBitmap(blob);
                    const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
                    const result = {width: bitmap.width, height: bitmap.height,
                        sha256: Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('')};
                    bitmap.close();
                    return result;
                }'''), timeout=30)
                if not preview['width'] or not preview['height'] or preview['sha256'] != hashlib.sha256(self.thumbnail.read_bytes()).hexdigest():
                    raise RuntimeError('The Instagram cover preview does not match the given image')
            await expect(heading).to_have_count(1)
            previous = await heading.inner_text()
            action = dialog.locator(INSTAGRAM_PRIMARY_ACTION)
            await expect(action).to_have_count(1)
            await expect(action).to_be_enabled()
            await action.click()
            await expect(heading).not_to_have_text(previous, timeout=60_000)
        # data-lexical-editor marks the real caption editor; scope to the current create dialog to exclude comment boxes.
        await expect(dialog.locator('[contenteditable="true"][role="textbox"][data-lexical-editor="true"]')).to_have_count(1)

    async def _publish(self, page: Page, identity: dict) -> None:
        """Register the final-response listener before sharing; an unclear response is recorded as unknown and never resent."""
        # The caption step's unique Lexical editor; the header's single main action is now share, so no translated button name is used.
        dialog = page.get_by_role('dialog')
        editor = dialog.locator('[contenteditable="true"][role="textbox"][data-lexical-editor="true"]')
        caption = self._caption()
        await editor.fill(caption)
        await expect(editor).to_have_text(caption)
        action = dialog.locator(INSTAGRAM_PRIMARY_ACTION)
        await expect(action).to_have_count(1)
        await expect(action).to_be_enabled()
        self.result.update(identity, status='submission_unknown')
        self.result_file.parent.mkdir(parents=True, exist_ok=True)
        self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
        # A Reel answers 202 first while the browser keeps calling the same create endpoint and only later returns the real media.
        # Install the queued listener before submitting, consume this create's responses, click once, and never read an upload response or 202 as published.
        responses = asyncio.Queue()
        def on_response(response):
            if response.request.method == 'POST' and urlparse(response.url).path.startswith('/api/v1/media/configure'):
                responses.put_nowait(response)
        page.on('response', on_response)
        try:
            await action.click()
            deadline = asyncio.get_running_loop().time() + 180
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError('Instagram submitted but waiting for the final create response timed out')
                response = await asyncio.wait_for(responses.get(), timeout=remaining)
                remaining = deadline - asyncio.get_running_loop().time()
                payload = instagram_response_payload(await asyncio.wait_for(response.text(), timeout=max(remaining, 0)))
                body = payload.get('payload', payload)
                if body.get('statusCode') == 202:
                    self.result['status'] = 'processing'
                    self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
                    continue
                media = instagram_created_media(payload, owner_id=identity['user_id'], caption=caption)
                break
        finally:
            page.remove_listener('response', on_response)
        kind = 'reel' if self.video_file else 'p'
        self.result.update(status='published', content_id=media['id'], post_id=media['code'],
                           post_url=f"{INSTAGRAM_HOME_URL}{kind}/{media['code']}/", schedule=None,
                           media_count=len(media.get('carousel_media') or [media]))
        self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')

    async def upload(self) -> dict:
        """Verify identity, upload and publish in one session; on failure save the stage and local evidence."""
        if self.thumbnail:
            if not self.thumbnail.is_file():
                raise FileNotFoundError(f'Instagram cover not found: {self.thumbnail}')
            if self.thumbnail.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                raise ValueError('An Instagram cover must be JPG/JPEG/PNG')
        paths = [self.video_file] if self.video_file else self.image_files
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f'Instagram media not found: {path}')
            allowed = {'.mp4', '.mov'} if self.video_file else {'.jpg', '.jpeg', '.png', '.avif', '.heic', '.heif'}
            if path.suffix.lower() not in allowed:
                raise ValueError(f'Unsupported Instagram media type: {path.suffix}')
        async with async_playwright() as p:
            browser, context, page = await _open_instagram_page(p, self.account_file, proxy=self.proxy, headless=self.headless)
            try:
                self.stage = 'identity'
                identity = await instagram_identity(page, self.account_file)
                self.stage = 'upload'
                await self._upload_files(page)
                self.stage = 'edit'
                await self._advance_media_editor(page)
                self.stage = 'publish'
                await self._publish(page, identity)
                self.stage = 'save_session'
                await context.storage_state(path=str(self.account_file))
                return self.result
            except Exception as error:
                folder = Path('.local/instagram-errors') / uuid4().hex
                folder.mkdir(parents=True)
                self.result.update(stage=self.stage, error=str(error), evidence_dir=str(folder))
                self.result_file.parent.mkdir(parents=True, exist_ok=True)
                self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
                await page.screenshot(path=str(folder/'page.png'))
                (folder/'page.html').write_text(await page.content(), encoding='utf-8')
                raise RuntimeError(f'Instagram {self.stage} did not finish; result record: {self.result_file}; reason: {error}') from error
            finally:
                await browser.close()
