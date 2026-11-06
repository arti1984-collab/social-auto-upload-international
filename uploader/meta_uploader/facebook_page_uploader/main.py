"""Publish Facebook Page content through Meta Business Suite."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from patchright.async_api import Page, Playwright, async_playwright, expect, TimeoutError as BrowserTimeoutError

from uploader.base_video import BaseVideoUploader
from utils.browser import open_session, session_available


META_BUSINESS_URL = "https://business.facebook.com/latest/composer/"
META_PLATFORMS = {"facebook-page"}
# Without an environment variable or --proxy the system connects directly.
FACEBOOK_PAGE_PROXY = os.environ.get("SAU_FACEBOOK_PAGE_PROXY")


def meta_account_file(platform: str, account_name: str) -> Path:
    if platform not in META_PLATFORMS:
        raise ValueError(f"Unsupported Meta Business platform: {platform}")
    return Path("cookies") / f"{platform}_{account_name}.json"


def _proxy_options(proxy: str | None) -> dict[str, str] | None:
    address = (FACEBOOK_PAGE_PROXY if proxy is None else proxy) or ""
    address = address.strip()
    return {"server": address} if address else None


async def _open_business_page(
    playwright: Playwright,
    account_file: Path,
    *,
    proxy: str | None,
    headless: bool,
):
    browser, context = await open_session(
        playwright, account_file, headless=headless, proxy=_proxy_options(proxy)
    )
    try:
        page = await context.new_page()
        page.set_default_timeout(30_000)
        await page.goto(META_BUSINESS_URL, wait_until="domcontentloaded", timeout=120_000)
        await page.locator("body").wait_for(state="visible", timeout=30_000)
        return browser, context, page
    except Exception:
        await browser.close()
        raise


async def dismiss_guidance_cards(page: Page) -> None:
    """Dismiss the guidance card with an explicit GeoGuidanceCard marker and ignore unknown dialogs."""
    # The close button of these localized cards has no aria-label while learn-more has one, so no translated close label is used.
    close_buttons = page.locator('[data-surface$="lib:GeoGuidanceCard"] [role="button"]:not([aria-label]):visible')
    # data-surface can sit on both wrapper and log nodes; pick its descendant button and let CSS deduplicate.
    for close in await close_buttons.all():
        await close.click()
        await expect(close).to_be_hidden()


async def _is_business_logged_out(page: Page) -> bool:
    url = page.url.lower()
    if "/login" in url or "checkpoint" in url or "two_step_verification" in url:
        return True
    if await page.locator('input[name="email"]').count() and await page.locator('input[name="email"]').first.is_visible():
        return True
    # Nav href and page surfaces are independent of the display language; a blank page never proves a session.
    navigation = page.locator('a[href*="/latest/home"]')
    return not await navigation.filter(visible=True).count()



async def meta_cookie_auth(account_file: str | Path, *, proxy: str | None = None) -> bool:
    account_file = Path(account_file)
    if not session_available(account_file):
        return False
    async with async_playwright() as playwright:
        browser, context, page = await _open_business_page(
            playwright, account_file, proxy=proxy, headless=True
        )
        try:
            return not await _is_business_logged_out(page)
        finally:
            await browser.close()


async def meta_setup(
    account_file: str | Path,
    *,
    handle: bool = False,
    proxy: str | None = None,
    headless: bool = False,
    return_detail: bool = False,
):
    account_file = Path(account_file)
    account_file.parent.mkdir(parents=True, exist_ok=True)
    if await meta_cookie_auth(account_file, proxy=proxy):
        result = {"success": True, "status": "cookie_valid", "account_file": str(account_file)}
        return result if return_detail else True
    if not handle:
        result = {"success": False, "status": "cookie_invalid", "account_file": str(account_file)}
        return result if return_detail else False

    async with async_playwright() as playwright:
        browser, context = await open_session(
            playwright, account_file, headless=headless, proxy=_proxy_options(proxy)
        )
        try:
            page = await context.new_page()
            page.set_default_timeout(30_000)
            await page.goto(META_BUSINESS_URL, wait_until="domcontentloaded", timeout=120_000)
            deadline = asyncio.get_running_loop().time() + 600
            while asyncio.get_running_loop().time() < deadline:
                if not await _is_business_logged_out(page):
                    await context.storage_state(path=str(account_file))
                    result = {
                        "success": True,
                        "status": "logged_in",
                        "account_file": str(account_file),
                        "current_url": page.url,
                    }
                    return result if return_detail else True
                await page.wait_for_timeout(1000)
            result = {"success": False, "status": "timeout", "account_file": str(account_file)}
            return result if return_detail else False
        finally:
            await browser.close()


class MetaBusinessUploader(BaseVideoUploader):
    """Facebook Page video and image publisher inside Business Suite."""

    def __init__(
        self,
        platform: str,
        account_file: str | Path,
        *,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        video_file: str | Path | None = None,
        image_files: list[str | Path] | None = None,
        schedule: datetime | int = 0,
        page_name: str | None = None,
        proxy: str | None = None,
        headless: bool = False,
        result_file: str | Path | None = None,
    ):
        if platform not in META_PLATFORMS:
            raise ValueError(f"Unsupported Meta Business platform: {platform}")
        if not title.strip():
            raise ValueError("Title must not be empty")
        if bool(video_file) == bool(image_files):
            raise ValueError("Exactly one video or image file is required")
        self.platform = platform
        self.account_file = Path(account_file)
        self.title = title.strip()
        self.description = description.strip()
        self.tags = [tag.strip().lstrip("#") for tag in (tags or []) if tag.strip().lstrip("#")]
        self.video_file = Path(video_file) if video_file else None
        self.image_files = [Path(item) for item in (image_files or [])]
        self.schedule = self.validate_publish_date(schedule)
        self.page_name = page_name.strip() if page_name else None
        self.proxy = proxy
        self.headless = headless
        self.timezone: str | None = None
        self.result_file = Path(result_file) if result_file else Path('.local/meta-results') / f'{uuid4().hex}.json'
        self.result = {"platform": platform, "title": self.title, "status": "not_submitted"}

    def _caption(self) -> str:
        parts = [self.title, self.description] if self.description else [self.title]
        if self.tags:
            parts.append(" ".join(f"#{tag}" for tag in self.tags))
        return "\n\n".join(parts)

    async def _select_publish_location(self, page: Page) -> None:
        # The publish-target accessible name differs from the text and CTA comboboxes, so no page-wide order is used.
        # The publisher selector carries the Facebook brand mark that the CTA dropdown and text box lack.
        # Both locales keep this brand alt, so no localized post-to label is needed.
        combo = page.locator('[data-surface$="bizweb_create_post:left_panel"] [role="combobox"][aria-haspopup="listbox"]').filter(has=page.locator('img[alt="Facebook"]'))
        await combo.wait_for(state="visible")
        if self.page_name and self.page_name not in await combo.inner_text():
            await combo.click()
            option = page.get_by_role("option", name=self.page_name, exact=True)
            if not await option.count():
                raise RuntimeError(f"Business Suite did not find the publisher: {self.page_name}")
            await option.click()
        if self.page_name:
            await expect(combo).to_contain_text(self.page_name)
        else:
            self.page_name = (await combo.inner_text()).replace('\u200b', '').strip()
        assets = parse_qs(urlparse(page.url).query).get('asset_id', [])
        if len(assets) != 1 or not assets[0].isdigit():
            raise RuntimeError("Cannot verify the current Page asset_id; nothing submitted")
        self.result.update(page_id=assets[0], page_name=self.page_name, expected_text=self.title)

    async def _upload_files(self, page: Page) -> None:
        # The page may keep hidden responsive layouts; button semantics plus visible pin the real upload entry.
        # An empty media area offers local media upload then optional AI generation, with 1 or 2 entries depending on locale.
        # Only those two empty-area structures are accepted; edit/remove actions created after upload never mix in, and no translated label or icon path is matched.
        media = page.locator('[data-surface$="lib:bizweb_create_post:media"]')
        await expect(media.locator('img')).to_have_count(0)
        entries = media.get_by_role('button')
        if await entries.count() not in (1, 2):
            raise RuntimeError('Unrecognized empty media area; nothing uploaded')
        trigger = entries.nth(0)
        files = [str(self.video_file)] if self.video_file else [str(path) for path in self.image_files]
        async with page.expect_file_chooser() as chooser_info:
            await trigger.click()
        await (await chooser_info.value).set_files(files)
        # In the new Business Suite a video enters the create-Reels wizard and renders no video tag,
        # while an image stays in the composer. Both states wait for the filename or the wizard's own title.
        if self.video_file:
            await page.get_by_text(self.video_file.name, exact=True).wait_for(state="visible", timeout=180_000)
            # The new Reel wizard has its own surface, so no localized create-reel title is used.
            await page.locator('[data-surface$="lib:bizweb_create_reel"]').wait_for()
            await dismiss_guidance_cards(page)
            await page.get_by_text('100%', exact=True).wait_for(state='visible', timeout=180000)
        else:
            # Uploading yields a server preview with pixel size, so no localized remove-photo label or caption box stands for completion.
            await expect(media.locator('img')).to_have_count(len(files), timeout=180000)
            await expect(media.get_by_text(re.compile(r"^\d+ x \d+$")).filter(visible=True)).to_have_count(len(files), timeout=180000)

    async def _fill_caption(self, page: Page) -> None:
        # The Reel title is the only plain text input in left_panel; keyword input has the combobox role instead.
        reels_title = page.locator('[data-surface$="bizweb_create_reel:left_panel"] input[type="text"]:not([role]):visible')
        separate_title = self.video_file and await reels_title.count() and await reels_title.is_visible()
        if separate_title:
            await reels_title.fill(self.title)
        # A hidden textbox shares the name with the visible combobox, so match only the visible text box of the current wizard to avoid filling an old layout.
        # The visible contenteditable is the text box while the hidden textbox belongs to the old layout, and roles change between image and Reel.
        editor = page.locator('[contenteditable="true"]:visible')
        await expect(editor).to_have_count(1)
        await editor.wait_for(state="visible", timeout=30_000)
        caption = self.description if separate_title else self._caption()
        if self.tags and separate_title:
            caption = f"{caption}\n\n{' '.join(f'#{tag}' for tag in self.tags)}" if caption else " ".join(f"#{tag}" for tag in self.tags)
        if not caption and not self.video_file:
            caption = self._caption()
        await editor.fill(caption)
        if (await editor.inner_text()).strip() != caption:
            raise RuntimeError("The Business Suite text box did not read back the expected content")

    async def _advance_reels(self, page: Page) -> None:
        if not self.video_file:
            return
        root = page.locator('[data-surface$="lib:bizweb_create_reel"]')
        # The wizard's three steps have aria-labelledby and the current one aria-current, which thumbnail switching lacks.
        steps = root.locator('[role="button"][aria-labelledby]:not([aria-haspopup])')
        await expect(steps).to_have_count(3)
        # Both next clicks come from the footer, never the thumbnail arrows; the aria-labelled one is feedback.
        # The create, edit and share footers all hold exactly back/cancel plus one main action.
        for index in (0, 1):
            await expect(steps.nth(index)).to_have_attribute('aria-current', 'step')
            actions = page.locator('[data-surface$="bizweb_create_reel:footer"] [role="button"]:not([aria-label])')
            await expect(actions).to_have_count(2)
            await expect(actions.nth(1)).to_be_enabled(timeout=180000)
            await actions.nth(1).click()
            await expect(steps.nth(index + 1)).to_have_attribute('aria-current', 'step')
        # The story toggle shares one switch group with the current Page's Facebook mark while other switches have no brand image.
        story = page.locator('[data-surface$="bizweb_create_reel:left_panel"] input[role="switch"]').locator(
            'xpath=self::input[ancestor::div[.//img[@alt="Facebook"] and count(.//input[@role="switch"])=1]]')
        await expect(story).to_have_count(1)
        if await story.is_checked():
            await story.click()
            # Once is a real platform option and only skips sharing this one story, while Always changes later defaults.
            dialog = page.get_by_role('dialog').filter(has=page.locator('input[type="radio"][value="Once"]'))
            await expect(dialog).to_have_count(1)
            await dialog.locator('input[value="Once"]').check()
            actions = dialog.get_by_role('button')
            # The verified confirmation holds exactly close, cancel, confirm; check the count before using that order.
            await expect(actions).to_have_count(3)
            await actions.nth(2).click()
            await expect(dialog).to_have_count(0)
            await expect(story).not_to_be_checked()

    async def _fill_schedule(self, page: Page) -> None:
        if not self.schedule:
            return
        # The form reads the typed digits in the browser's own zone, so the time is local wall-clock time.
        # The zone recorded in upload() is only reported in the result; no fixed zone is assumed here.
        if self.schedule.tzinfo is not None:
            raise ValueError("Meta scheduling takes the browser's local time; pass a time without a zone suffix")
        if self.video_file:
            region = page.locator('[data-surface$="bizweb_create_reel:left_panel"]')
            # The share step's three modes are now, scheduled and draft; their aria-pressed marks a mode, not a submit.
            modes = region.locator('[role="button"][aria-pressed]').locator('xpath=self::*[not(ancestor::*[@role="grid"])]')
            await expect(modes).to_have_count(3)
            await modes.nth(1).click()
            await expect(modes.nth(1)).to_have_attribute('aria-pressed', 'true')
        else:
            region = page.locator('[data-surface$="lib:bizweb_create_post:publishing_options"]')
            await region.locator('input[role="switch"]').check()
        # The date is the only plain input with a placeholder in the scheduling area, and hours/minutes differ by numeric range.
        date_input = region.locator('input[placeholder]:not([role])')
        await expect(date_input).to_have_count(1)
        await date_input.click()
        grid = region.locator('[role="grid"][aria-labelledby]')
        await expect(grid).to_have_count(1)
        # The calendar's aria-labelledby holds month and year with a js_* prefix that changes per session, so parse only the date suffix.
        month_id = await grid.get_attribute('aria-labelledby')
        match = re.search(r'-(\d{1,2})-(\d{4})$', month_id or '')
        if not match:
            raise RuntimeError('Cannot read the calendar month/year; nothing submitted')
        month, year = map(int, match.groups())
        month_delta = (self.schedule.year - year) * 12 + self.schedule.month - month
        if abs(month_delta) > 12:
            raise ValueError('The scheduled date is outside the verified calendar range')
        # The calendar's two non-grid buttons are previous/next month while day buttons are gridcells and excluded.
        calendar = grid.locator('xpath=ancestor::div[.//*[@role="button"][@aria-busy]][1]')
        navigation = calendar.locator('[role="button"][aria-busy]')
        await expect(navigation).to_have_count(2)
        for _ in range(abs(month_delta)):
            await navigation.nth(1 if month_delta > 0 else 0).click()
        await expect(grid).to_have_attribute('aria-labelledby', re.compile(fr'-{self.schedule.month}-{self.schedule.year}$'))
        # With month and year verified, pick by day number instead of relying on localized weekday or month names.
        day = grid.get_by_role('button').filter(has_text=re.compile(fr'^{self.schedule.day}$'))
        await expect(day).to_have_count(1)
        if await day.get_attribute('aria-disabled') == 'true':
            raise ValueError('The platform calendar rejects the chosen day; nothing submitted')
        await day.click()
        hour = region.locator('[role="spinbutton"][aria-valuemax="23"], [role="spinbutton"][aria-valuemax="12"]')
        await expect(hour).to_have_count(1)
        twelve_hour = await hour.get_attribute('aria-valuemax') == '12'
        value_hour = (self.schedule.hour % 12 or 12) if twelve_hour else self.schedule.hour
        for control, value in ((hour, value_hour), (region.locator('[role="spinbutton"][aria-valuemax="59"]'), self.schedule.minute)):
            await control.click()
            for digit in f'{value:02d}':
                await control.press(digit)
            await control.press('Tab')
            await expect(control).to_have_attribute('aria-valuenow', str(value))
        if twelve_hour:
            # AM/PM really are 0/1; toggle by key and read back rather than filling hours alone and drifting 12 hours.
            period = region.locator('[role="spinbutton"][aria-valuemax="1"]')
            target = str(int(self.schedule.hour >= 12))
            if await period.get_attribute('aria-valuenow') != target:
                await period.press('ArrowUp')
            await expect(period).to_have_attribute('aria-valuenow', target)
        # The date control reads back day, month and year digits in every locale; separators may localize but month names are never guessed.
        parts = [int(part) for part in re.findall(r'\d+', await date_input.input_value())]
        if parts != [self.schedule.year, self.schedule.month, self.schedule.day]:
            raise RuntimeError(f'Date did not read back the requested value: {await date_input.input_value()}')

    async def _publish(self, page: Page) -> None:
        # The image footer's actions are cancel, save draft and final submit; scope to the footer and check all three,
        # using that order only in an observed layout and stopping when it changes, never page-wide same-named buttons or guessed labels.
        if not self.video_file:
            actions = page.locator('[data-surface$="lib:bizweb_create_post:footer"] [role="button"]')
            await expect(actions).to_have_count(3)
            button = actions.nth(2)
        else:
            # The share step is still back plus the final action, never the Share step in the top nav.
            actions = page.locator('[data-surface$="bizweb_create_reel:footer"] [role="button"]:not([aria-label])')
            await expect(actions).to_have_count(2)
            button = actions.nth(1)
        await expect(button).to_be_enabled()
        self.result['status'] = 'submission_unknown'
        self.result_file.parent.mkdir(parents=True, exist_ok=True)
        self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
        # Capture only the create response this click triggers; neither media ids nor story ids in ad suggestions replace the content id.
        async with page.expect_response(lambda response: '/api/graphql' in response.url and
                parse_qs(response.request.post_data or '').get('fb_api_req_friendly_name') == ['BusinessComposerStoryCreationMutation'], timeout=90000) as response_info:
            await button.click()
        payload = await (await response_info.value).json()
        if payload.get('errors'):
            raise RuntimeError("The platform's create response contains an error; check the original record instead of resubmitting")
        creation = payload.get('data', {}).get('xfamily_content_create', {})
        if any(creation.get('errors', {}).values()):
            raise RuntimeError('The platform returned a create error; check the original record instead of resubmitting')
        items = creation.get('items')
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list) or len(items) != 1:
            raise RuntimeError('Submitted but no unique content id was returned; result pending lookup')
        # The verified Reels response has an empty pending_publish_content_id, so the post is looked up after the success confirmation.
        pending_id = items[0].get('pending_publish_content_id')
        if pending_id:
            self.result['content_id'] = str(pending_id)
        self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
        if self.video_file:
            # After the create response the page keeps publishing, so never navigate away; the verified done dialog shows this title,
            # a post preview and two actions, close and done. The title is a request parameter, not a localized success message.
            completion = page.locator('[role="dialog"][aria-labelledby][tabindex="-1"]').filter(has_text=self.title)
            await expect(completion).to_have_count(1, timeout=120000)
            await expect(completion.get_by_role('heading')).to_have_count(1)
            await expect(completion.get_by_role('button')).to_have_count(2)
            # Both done-dialog actions are close/done; clicking the last one records that the platform accepted this Reel.
            await completion.get_by_role('button').last.click()
            await expect(completion).to_have_count(0)
            if not self.schedule:
                # The verified Reel create response may lack pending_publish_content_id and the post list may hide posts while the video processes.
                # The done dialog plus an error-free create response already prove "submitted, processing"; the id only serves later verification and deletion and must not block the result.
                self.result['status'] = 'processing'
                self.result['schedule'] = None
                self.result['timezone'] = self.timezone
                self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
                return
        # Once the create response accepts the post, look it up by Page and id instead of any localized success toast.
        # A scheduled post must read back its schedule and an immediate image post must read back the post itself; a dialog alone decides neither.
        from uploader.meta_uploader.facebook_page_uploader.posts import open_meta_post
        state = 'scheduled_posts' if self.schedule else 'published_posts'
        list_url = f'https://business.facebook.com/latest/posts/{state}?asset_id={self.result["page_id"]}'
        _, content_id, _ = await open_meta_post(page, list_url=list_url, page_name=self.page_name,
            expected_text=self.title, content_id=self.result.get('content_id'), schedule=self.schedule)
        self.result['content_id'] = content_id
        self.result['status'] = 'scheduled' if self.schedule else ('processing' if self.video_file else 'published')
        self.result['schedule'] = self.schedule.isoformat() if self.schedule else None
        self.result['timezone'] = self.timezone

    async def upload(self) -> dict:
        if self.video_file:
            self.validate_video_file(self.video_file)
        for path in self.image_files:
            self.validate_image_file(path)
        async with async_playwright() as playwright:
            browser, context, page = await _open_business_page(
                playwright, self.account_file, proxy=self.proxy, headless=self.headless
            )
            try:
                if await _is_business_logged_out(page):
                    raise RuntimeError("The Business Suite session expired; run the matching platform login first")
                self.timezone = await page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
                await dismiss_guidance_cards(page)
                await self._select_publish_location(page)
                await self._upload_files(page)
                await self._fill_caption(page)
                await self._advance_reels(page)
                await self._fill_schedule(page)
                await self._publish(page)
                await context.storage_state(path=str(self.account_file))
                return self.result
            finally:
                self.result_file.parent.mkdir(parents=True, exist_ok=True)
                self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
                await browser.close()
