# -*- coding: utf-8 -*-
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import Playwright, async_playwright
import os
import asyncio

from conf import BASE_DIR, LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS
from uploader.tk_uploader.tk_config import Tk_Locator
from utils.base_social_media import set_init_script
from utils.browser import open_session, session_available

from utils.log import tiktok_logger


def account_path(account_file, *, create: bool = False) -> Path:
    """The TikTok session file: ``cookies/tk_uploader/<name>`` unless an absolute path is given.

    Writing and reading must agree here; the uploader used to prefix ``tk_uploader/`` to whatever
    it was given, so a session stored at the documented path was never found again. Always returns
    a ``Path``, so callers can rely on ``.parent`` even when they passed a string.
    """
    path = Path(account_file)
    if not path.is_absolute():
        path = Path(BASE_DIR) / "cookies" / "tk_uploader" / path.name
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def _wait_for_login(page, context, *, timeout_s: int = 600, interval_s: int = 2) -> bool:
    """Signed in as soon as TikTok set its session cookie; the page itself may still be loading.

    The cookie is the signal, not the URL or a selector: TikTok redirects between feed and
    login in ways that differ per region and experiment.
    """
    polls = max(1, int(timeout_s) // max(1, int(interval_s)))
    for _ in range(polls):
        try:
            if any(cookie.get("name") == "sessionid" for cookie in await context.cookies()):
                return True
        except Exception:
            pass
        await page.wait_for_timeout(interval_s * 1000)
    return False


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser, context = await open_session(playwright, account_file, headless=LOCAL_CHROME_HEADLESS)
        context = await set_init_script(context)
        # open a new page
        page = await context.new_page()
        # go to the given URL
        await page.goto("https://www.tiktok.com/tiktokstudio/upload?lang=en")
        await page.wait_for_load_state('networkidle')
        try:
            # select every select element
            select_elements = await page.query_selector_all('select')
            for element in select_elements:
                class_name = await element.get_attribute('class')
                # match class names by regular expression
                if re.match(r'tiktok-.*-SelectFormContainer.*', class_name):
                    tiktok_logger.error("[+] cookie expired")
                    return False
            tiktok_logger.success("[+] cookie valid")
            return True
        except:
            tiktok_logger.success("[+] cookie valid")
            return True


async def tiktok_setup(account_file, handle=False, *, headless=False, timeout_s=600):
    account_file = account_path(account_file)
    if not session_available(account_file) or not await cookie_auth(account_file):
        if not handle:
            return False
        tiktok_logger.info('[+] cookie file is not existed or expired. Now open the browser auto. Please login with your way(gmail phone, whatever, the cookie file will generated after login')
        return await get_tiktok_cookie(account_file, headless=headless, timeout_s=timeout_s)
    return True


async def get_tiktok_cookie(account_file, *, headless=False, timeout_s=600):
    async with async_playwright() as playwright:
        # Make sure to run headed.
        browser, context = await open_session(
            playwright, account_file, headless=headless, args=["--lang en-GB"]
        )
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        account_file = account_path(account_file, create=True)
        await page.goto("https://www.tiktok.com/login?lang=en", wait_until="domcontentloaded")
        tiktok_logger.info("[+] Sign in to TikTok in the opened browser; the session is saved afterwards")
        ok = await _wait_for_login(page, context, timeout_s=timeout_s)
        # click continue in the debugger and save the cookie
        if ok:
            await context.storage_state(path=str(account_file))
            tiktok_logger.success(f"[+] TikTok session saved: {account_file}")
        else:
            tiktok_logger.error("[+] No TikTok sign-in detected; the session was not saved")
        await browser.close()
        return ok


# TikTok localizes the audience labels and renders them inside a combobox, not a <select>.
VISIBILITY_LABELS = {
    "public": ("Alle", "Everyone", "Öffentlich", "Public"),
    "friends": ("Freund*innen", "Freunde", "Friends"),
    "private": ("Nur du", "Only you", "Only me", "Nur ich"),
}


def normalize_visibility(visibility) -> str:
    key = (visibility or "public").strip().lower()
    if key not in VISIBILITY_LABELS:
        raise ValueError(
            f"unsupported visibility '{visibility}', use one of: {', '.join(sorted(VISIBILITY_LABELS))}"
        )
    return key


def pick_visibility_option(option_texts, visibility) -> str:
    """The option label TikTok offers for the requested audience; raises when it is missing.

    Matching is by label, never by position, because the composer lists the audience in the
    session's language ("Alle" / "Nur du" vs "Everyone" / "Only me"). The friends label carries a
    second line, so a label is accepted as a prefix too.
    """
    labels = [label.casefold() for label in VISIBILITY_LABELS[normalize_visibility(visibility)]]
    for text in option_texts:
        flat = " ".join(str(text).split()).casefold()
        if any(flat == label or flat.startswith(label + " ") for label in labels):
            return str(text)
    raise RuntimeError(
        f"TikTok does not offer visibility '{visibility}' here (options: {option_texts}); "
        "refusing to post"
    )


PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MAX_PHOTOS = 35


def validate_photo_files(files) -> list[Path]:
    """TikTok photo posts take 1-35 images (jpg/png/webp/heic)."""
    items = files if isinstance(files, (list, tuple)) else [files]
    paths = [Path(str(item)).expanduser().resolve() for item in items]
    if not paths:
        raise ValueError("a TikTok photo post needs at least one image")
    if len(paths) > MAX_PHOTOS:
        raise ValueError(f"TikTok accepts at most {MAX_PHOTOS} images, got {len(paths)}")
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")
        if path.suffix.lower() not in PHOTO_EXTENSIONS:
            raise ValueError(
                f"unsupported image format: {path.suffix}, "
                f"supported: {', '.join(sorted(PHOTO_EXTENSIONS))}"
            )
    return paths


def is_photo_post(files) -> bool:
    items = files if isinstance(files, (list, tuple)) else [files]
    return bool(items) and all(
        Path(str(item)).suffix.lower() in PHOTO_EXTENSIONS for item in items)


def needs_language_switch(photo_post: bool) -> bool:
    """Only the video flow depends on the English UI ("Select video"); photos are label-matched."""
    return not photo_post


async def _js_click(locator) -> None:
    """Click through the element itself; TikTok's modals intercept Playwright's pointer events."""
    await locator.first.evaluate("el => { el.scrollIntoView({block: 'center'}); el.click(); }")


async def _dismiss_overlays(page, rounds: int = 2) -> None:
    """Close whatever dialog TikTok put on top of the page (cookie notice, login nudge)."""
    for _ in range(rounds):
        overlay = page.locator(
            "#tux-portal-container [role=dialog], #tux-portal-container div[class*=ModalContentContainer]"
        ).first
        try:
            if not await overlay.count() or not await overlay.is_visible():
                return
        except Exception:
            return
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(600)
        for selector in (
            'button[aria-label="Close"]',
            'button[aria-label="Schließen"]',
            'div[class*=ModalContentContainer] button',
        ):
            close = overlay.locator(selector).first
            try:
                if await close.count():
                    await close.evaluate("el => el.click()")
                    break
            except Exception:
                continue
        await page.wait_for_timeout(700)


async def _dismiss_joyride(page) -> None:
    """TikTok Studio's onboarding tour lays a react-joyride overlay over the composer.

    The overlay swallows every click ("react-joyride__overlay ... intercepts pointer events"),
    which blocked the title editor. Skipping and removing the portal is enough; the tour is
    cosmetic and reappears only for a fresh session.
    """
    try:
        await page.evaluate("""() => {
            // Removing the portal alone is not enough: React mounts the tour again right after it
            // becomes visible, so a stylesheet keeps it out of the way for good.
            if (!document.getElementById('sau-joyride-off')) {
                const style = document.createElement('style');
                style.id = 'sau-joyride-off';
                style.textContent = '#react-joyride-portal { display: none !important; pointer-events: none !important; }';
                document.head.appendChild(style);
            }
            const portal = document.getElementById('react-joyride-portal');
            if (!portal) return;
            const skip = portal.querySelector(
                'button[data-action="skip"], button[aria-label*="Skip"], button[aria-label*="Überspringen"], button[title*="Skip"]');
            if (skip) skip.click();
            portal.remove();
        }""")
    except Exception:
        pass


async def _hide_covers(page) -> None:
    """Make Studio's floating modal overlays click-through.

    They sit above the composer and swallow pointer events ("TUXModal-overlay ... intercepts
    pointer events"), which blocked the Post button for minutes. Hidden, not removed, so the
    dialog stays readable in the window.
    """
    try:
        await page.evaluate("""() => {
            if (document.getElementById('sau-modal-off')) return;
            const style = document.createElement('style');
            style.id = 'sau-modal-off';
            style.textContent = '[data-floating-ui-portal] .TUXModal-overlay, #tux-portal-container .TUXModal-overlay { pointer-events: none !important; }';
            document.head.appendChild(style);
        }""")
    except Exception:
        pass


async def _click_button_by_text(page, labels) -> bool:
    """Click a button by its exact visible label, straight on the element.

    TikTok's onboarding tour renders buttons inside the composer and its overlays intercept
    pointer events, which defeats Playwright clicks and role lookups.
    """
    return bool(await page.evaluate("""(labels) => {
        const buttons = Array.from(document.querySelectorAll('button'));
        for (const label of labels) {
            const hit = buttons.find((b) => (b.innerText || '').trim() === label);
            if (hit) { hit.scrollIntoView({block: 'center'}); hit.click(); return true; }
        }
        return false;
    }""", list(labels)))


async def _post_button_state(page):
    """(found, enabled) for Studio's Post button, matched by label in any UI language.

    Role lookups do not resolve this button (the tour renders its own buttons nearby), so the
    state is read from the DOM directly.
    """
    state = await page.evaluate("""(labels) => {
        const buttons = Array.from(document.querySelectorAll('button'));
        for (const label of labels) {
            const hit = buttons.find((b) => (b.innerText || '').trim() === label);
            if (hit) return {found: true, disabled: !!hit.disabled};
        }
        return {found: false, disabled: true};
    }""", ["Post", "Posten", "Publish"])
    return bool(state.get("found")), not state.get("disabled", True)


STUDIO_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"


class TiktokVideo(object):
    def __init__(self, title, file_path, tags, publish_date, account_file, thumbnail_path=None,
                 visibility="public", cdp_url=None):
        self.title = title
        self.file_path = file_path
        self.file_paths = list(file_path) if isinstance(file_path, (list, tuple)) else [file_path]
        self.photo_post = is_photo_post(file_path)
        self.tags = tags
        self.publish_date = publish_date
        self.thumbnail_path = thumbnail_path
        self.account_file = account_file
        self.visibility = normalize_visibility(visibility)
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = LOCAL_CHROME_HEADLESS
        self.cdp_url = cdp_url or None
        self.locator_base = None

    async def set_schedule_time(self, page, publish_date):
        schedule_input_element = self.locator_base.get_by_label('Schedule')
        await schedule_input_element.wait_for(state='visible')  # make sure the button is visible

        await schedule_input_element.click(force=True)
        if await self.locator_base.locator('div.TUXButton-content >> text=Allow').count():
            await self.locator_base.locator('div.TUXButton-content >> text=Allow').click()

        scheduled_picker = self.locator_base.locator('div.scheduled-picker')
        await scheduled_picker.locator('div.TUXInputBox').nth(1).click()

        calendar_month = await self.locator_base.locator(
            'div.calendar-wrapper span.month-title').inner_text()

        n_calendar_month = datetime.strptime(calendar_month, '%B').month

        schedule_month = publish_date.month

        if n_calendar_month != schedule_month:
            if n_calendar_month < schedule_month:
                arrow = self.locator_base.locator('div.calendar-wrapper span.arrow').nth(-1)
            else:
                arrow = self.locator_base.locator('div.calendar-wrapper span.arrow').nth(0)
            await arrow.click()

        # day set
        valid_days_locator = self.locator_base.locator(
            'div.calendar-wrapper span.day.valid')
        valid_days = await valid_days_locator.count()
        for i in range(valid_days):
            day_element = valid_days_locator.nth(i)
            text = await day_element.inner_text()
            if text.strip() == str(publish_date.day):
                await day_element.click()
                break
        # time set
        await scheduled_picker.locator('div.TUXInputBox').nth(0).click()

        hour_str = publish_date.strftime("%H")
        correct_minute = int(publish_date.minute / 5)
        minute_str = f"{correct_minute:02d}"

        hour_selector = f"span.tiktok-timepicker-left:has-text('{hour_str}')"
        minute_selector = f"span.tiktok-timepicker-right:has-text('{minute_str}')"

        # pick hour first
        await page.wait_for_timeout(1000)  # wait 500 ms
        await self.locator_base.locator(hour_selector).click()
        # click time button again
        await page.wait_for_timeout(1000)  # wait 500 ms
        # pick minutes after
        await self.locator_base.locator(minute_selector).click()

        # click title to remove the focus.
        # await self.locator_base.locator("h1:has-text('Upload video')").click()

    async def handle_upload_error(self, page):
        tiktok_logger.info("video upload error retrying.")
        select_file_button = self.locator_base.locator('button[aria-label="Select file"]')
        async with page.expect_file_chooser() as fc_info:
            await select_file_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_paths)

    @staticmethod
    def _find_studio_page(context):
        """The studio tab the user already has open, or None."""
        for candidate in context.pages:
            try:
                if STUDIO_UPLOAD_URL in (candidate.url or "") and not candidate.is_closed():
                    return candidate
            except Exception:
                continue
        return None

    @staticmethod
    async def _raise_if_blocked(page) -> None:
        """Studio serves an Akamai 'Access Denied' page instead of the composer; say so plainly."""
        try:
            text = (await page.inner_text("body"))[:400]
        except Exception:
            return
        if "Access Denied" in text:
            raise RuntimeError(
                "TikTok answered with 'Access Denied' (Akamai) for the studio page, so nothing "
                "was uploaded. Open https://www.tiktok.com/tiktokstudio/upload in the browser "
                "once; the uploader then reuses that tab instead of loading it again."
            )

    async def upload(self, playwright: Playwright) -> None:
        reused_page = None
        if self.cdp_url:
            # Attach to the user's own browser instead of launching a new one: TikTok's bot
            # detection blocks the launched Chromium while the real browser passes.
            browser = await playwright.chromium.connect_over_cdp(self.cdp_url)
            if not browser.contexts:
                raise RuntimeError(
                    f"{self.cdp_url} has no open browser context; open a window in that browser first"
                )
            context = browser.contexts[0]
            # The studio page loads in the user's window but not under automation on this
            # machine, so an already open tab is used as it is: no reload, no language switch.
            reused_page = self._find_studio_page(context)
            page = reused_page or await context.new_page()
        else:
            browser, context = await open_session(
                playwright,
                self.account_file,
                headless=self.headless,
                executable_path=self.local_executable_path or None,
            )
            page = await context.new_page()

        if reused_page is None:
            # change language to eng first
            if needs_language_switch(self.photo_post):
                # Photo posts need no English UI (upload input and Post button are found by label),
                # and every extra page load is one more request TikTok rate limits.
                await self.change_language(page)
            await page.goto(STUDIO_UPLOAD_URL)
            await page.wait_for_url(STUDIO_UPLOAD_URL, timeout=10000)
        else:
            tiktok_logger.info("[+] using the studio tab that is already open in the browser")

        tiktok_logger.info(f'[+]Uploading-------{self.title}.mp4')
        await self._raise_if_blocked(page)

        try:
            await page.wait_for_selector(
                'iframe[data-tt="Upload_index_iframe"], div.upload-container, input[type=file]',
                timeout=15000)
            tiktok_logger.info("Upload composer is there.")
        except Exception as e:
            tiktok_logger.error("Neither iframe nor div appeared within the timeout.")

        await self.choose_base_locator(page)
        await _dismiss_joyride(page)

        if self.photo_post:
            # Photo posts (1-35 images, carousel) attach through the upload input directly; the
            # "Select video" button and its file chooser only exist for video uploads.
            paths = validate_photo_files(self.file_paths)
            tiktok_logger.info(f"[+] Uploading {len(paths)} photo(s)")
            await page.locator("input[type=file]").first.set_input_files([str(p) for p in paths])
        elif self.cdp_url:
            # In the attached browser the composer is already rendered: its file input takes the
            # video directly, so no click, no native dialog and no English label needed.
            await page.locator("input[type=file]").first.set_input_files(self.file_path)
            tiktok_logger.info("[+] video handed to the studio file input")
        else:
            upload_button = self.locator_base.locator(
                'button:has-text("Select video"):visible')
            await upload_button.wait_for(state='visible')  # make sure the button is visible

            async with page.expect_file_chooser() as fc_info:
                await upload_button.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.file_path)

        await self.add_title_tags(page)
        # detect upload status
        await self.detect_upload_status(page)
        if self.thumbnail_path:
            tiktok_logger.info(f'[+] Uploading thumbnail file {self.title}.png')
            await self.upload_thumbnails(page)

        if self.publish_date != 0:
            await self.set_schedule_time(page, self.publish_date)

        await self.set_visibility(page)
        await self.click_publish(page)
        tiktok_logger.success(f"video_id: {await self.get_last_video_id(page)}")

        if self.cdp_url:
            # The attached browser belongs to the user: leave it and its tab running.
            if reused_page is None:
                await page.close()
            tiktok_logger.info('  [-] detached, the attached browser keeps running')
            return

        await context.storage_state(path=f"{self.account_file}")  # save cookie
        tiktok_logger.info('  [-] update cookie!')
        await asyncio.sleep(2)  # close delay for look the video status
        # close all
        await context.close()
        await browser.close()

    async def add_title_tags(self, page):

        editor_locator = self.locator_base.locator('div.public-DraftEditor-content')
        await _dismiss_joyride(page)
        try:
            await editor_locator.click(timeout=10000)
        except Exception as exc:
            # The onboarding overlay can still be on top for a moment; focusing the Draft.js editor
            # is enough for the keyboard input that follows.
            tiktok_logger.warning(
                f"[+] editor click blocked ({str(exc).splitlines()[0][:60]}); focusing it instead")
            await editor_locator.first.evaluate("el => el.focus()")

        await page.keyboard.press("End")

        await page.keyboard.press("Control+A")

        await page.keyboard.press("Delete")

        await page.keyboard.press("End")

        await page.wait_for_timeout(1000)  # wait 1 s

        await page.keyboard.insert_text(self.title)
        await page.wait_for_timeout(1000)  # wait 1 s
        await page.keyboard.press("End")

        await page.keyboard.press("Enter")

        # tag part
        for index, tag in enumerate(self.tags, start=1):
            tiktok_logger.info("Setting the %s tag" % index)
            await page.keyboard.press("End")
            await page.wait_for_timeout(1000)  # wait 1 s
            await page.keyboard.insert_text("#" + tag + " ")
            await page.keyboard.press("Space")
            await page.wait_for_timeout(1000)  # wait 1 s

            await page.keyboard.press("Backspace")
            await page.keyboard.press("End")

    async def upload_thumbnails(self, page):
        await self.locator_base.locator(".cover-container").click()
        await self.locator_base.locator(".cover-edit-container >> text=Upload cover").click()
        async with page.expect_file_chooser() as fc_info:
            await self.locator_base.locator(".upload-image-upload-area").click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.thumbnail_path)
        await self.locator_base.locator('div.cover-edit-panel:not(.hide-panel)').get_by_role(
            "button", name="Confirm").click()
        await page.wait_for_timeout(3000)  # wait 3s, fix it later

    async def change_language(self, page):
        # set the language to english
        await page.goto("https://www.tiktok.com")
        await page.wait_for_load_state('domcontentloaded')
        if "Access Denied" in (await page.inner_text("body"))[:300]:
            # Akamai blocks the whole domain for a while; without this the run dies in a selector
            # timeout that looks like a layout change.
            raise RuntimeError(
                "TikTok answered with 'Access Denied' (Akamai) for this machine, so nothing was "
                "uploaded. Try again later."
            )
        await page.wait_for_selector('[data-e2e="nav-more-menu"]')
        # already set to English, this step is skipped
        if await page.locator('[data-e2e="nav-more-menu"]').text_content() == "More":
            return

        # A modal on tiktok.com intercepts pointer events, so the plain clicks timed out; the later
        # selectors of this uploader are English ("Select video", "Post"), so the switch is required.
        await _dismiss_overlays(page)
        await _js_click(page.locator('[data-e2e="nav-more-menu"]'))
        await page.wait_for_timeout(1200)
        language_item = page.locator('[data-e2e="language-select"]')
        if not await language_item.count():
            raise RuntimeError("TikTok language menu did not open; cannot switch the UI to English")
        await _js_click(language_item)
        await page.wait_for_timeout(1200)
        await _js_click(page.locator('#creator-tools-selection-menu-header >> text=English (US)'))
        await page.wait_for_timeout(1500)
        tiktok_logger.info("[+] switched the TikTok UI to English")

    async def set_visibility(self, page):
        """Select the requested audience and prove it took effect before anything is posted.

        The control is a combobox (``[data-e2e="video_visibility_container"]``) whose trigger and
        options a plain Playwright click cannot reach, so both go through the element's own
        ``click()``. A missing option or an unconfirmed label raises, and ``upload()`` only
        publishes after this returns.
        """
        container = self.locator_base.locator('[data-e2e="video_visibility_container"]').first
        await container.wait_for(state="visible", timeout=20000)
        trigger = container.locator("button[role=combobox]").first
        if not await trigger.count():
            raise RuntimeError("TikTok composer has no visibility control; refusing to post")

        wanted = [label.casefold() for label in VISIBILITY_LABELS[self.visibility]]
        current = " ".join((await trigger.inner_text()).split())
        if any(current.casefold() == label for label in wanted):
            tiktok_logger.info(f"[+] visibility is already '{current}'")
            return

        await trigger.evaluate("el => { el.scrollIntoView({block: 'center'}); el.click(); }")
        options = self.locator_base.locator("[role=option]")
        await options.first.wait_for(state="visible", timeout=10000)
        texts = [(await options.nth(i).inner_text()).strip() for i in range(await options.count())]
        chosen = pick_visibility_option(texts, self.visibility)

        for index, text in enumerate(texts):
            if text == chosen:
                await options.nth(index).evaluate("el => el.click()")
                break

        await page.wait_for_timeout(1500)
        shown = " ".join((await trigger.inner_text()).split())
        if not any(shown.casefold() == label for label in wanted):
            raise RuntimeError(
                f"visibility '{self.visibility}' was not applied (shows '{shown}'); refusing to post"
            )
        tiktok_logger.success(f"[+] visibility set to '{shown}'")

    async def click_publish(self, page):
        """Publish with a bounded retry, clicking the real Post button.

        Studio's tour renders its own buttons inside the composer and its overlays intercept
        pointer events, so the Post button is found by its exact label and clicked on the element
        itself. Studio navigates to the content page once the post is accepted.
        """
        for attempt in range(20):
            await _dismiss_joyride(page)
            await _hide_covers(page)
            if not await _click_button_by_text(page, ("Post", "Posten", "Publish")):
                tiktok_logger.info("  [-] Post button not available yet")
            try:
                await page.wait_for_url(
                    "https://www.tiktok.com/tiktokstudio/content", timeout=8000)
                tiktok_logger.success("  [-] video published success")
                return
            except Exception:
                tiktok_logger.info(f"  [-] video publishing (attempt {attempt + 1}/20)")
                await page.wait_for_timeout(2000)
        raise RuntimeError("TikTok did not confirm publishing; check the composer manually")


    async def get_last_video_id(self, page):
        await page.wait_for_selector('div[data-tt="components_PostTable_Container"]')
        video_list_locator = self.locator_base.locator('div[data-tt="components_PostTable_Container"] div[data-tt="components_PostInfoCell_Container"] a')
        if await video_list_locator.count():
            first_video_obj = await video_list_locator.nth(0).get_attribute('href')
            video_id = re.search(r'video/(\d+)', first_video_obj).group(1) if first_video_obj else None
            return video_id


    async def detect_upload_status(self, page):
        """Wait until Studio enables the Post button.

        Bounded and language tolerant: the old loop ran forever, swallowed every exception and
        only knew the English label, so a German UI or a missing button hung the run.
        """
        for attempt in range(90):
            found, enabled = await _post_button_state(page)
            if found and enabled:
                tiktok_logger.info("  [-] upload finished, Post button ready")
                return
            if attempt % 5 == 0:
                tiktok_logger.info("  [-] uploading...")
            await page.wait_for_timeout(2000)
            if await self.locator_base.locator('button[aria-label="Select file"]').count():
                tiktok_logger.info("  [-] found some error while uploading now retry...")
                await self.handle_upload_error(page)
        raise RuntimeError("TikTok never enabled the Post button; nothing was published")

    async def choose_base_locator(self, page):
        # await page.wait_for_selector('div.upload-container')
        if await page.locator('iframe[data-tt="Upload_index_iframe"]').count():
            self.locator_base = page.frame_locator(Tk_Locator.tk_iframe)
        else:
            self.locator_base = page.locator(Tk_Locator.default) 

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
