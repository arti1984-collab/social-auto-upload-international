"""Instagram post verification and moving to recently deleted."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from patchright.async_api import Page, async_playwright, expect

from .main import _open_instagram_page, instagram_identity, instagram_response_payload


def instagram_post_id(post_url: str) -> str:
    """Accept the short and author-qualified links the site really serves; reject foreign domains and non-post URLs."""
    parsed = urlparse(post_url)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.instagram.com', 'instagram.com'} or parsed.username or parsed.password or parsed.port:
        raise ValueError('An Instagram post must be an official HTTPS link')
    match = re.fullmatch(r'/(?:[A-Za-z0-9_.]+/)?(?:p|reel)/([A-Za-z0-9_-]+)/?', parsed.path)
    if not match:
        raise ValueError('The Instagram post link must contain /p/<id>/ or /reel/<id>/')
    return match.group(1)


async def find_instagram_post(page: Page, *, post_url: str, expected_text: str, owner_id: str) -> dict:
    """Check the details' canonical link, author id and text, then return the post's numeric id."""
    shortcode = instagram_post_id(post_url)
    if not expected_text.strip():
        raise ValueError('expected_text must not be empty')
    # Open details through /p/ so the /reel/ route never lands in a fullscreen player with other posts.
    await page.goto(f'https://www.instagram.com/p/{shortcode}/', wait_until='domcontentloaded', timeout=120_000)
    # og:url and instapp:owner_user_id in the page head are the platform's own canonical link and author metadata,
    # so the author is never guessed from recommendations or a matching caption; the text is scoped to main, excluding nav and other windows.
    canonical = page.locator('meta[property="og:url"]')
    owner = page.locator('meta[property="instapp:owner_user_id"]')
    await expect(canonical).to_have_count(1)
    await expect(owner).to_have_count(1)
    if instagram_post_id(await canonical.get_attribute('content')) != shortcode:
        raise RuntimeError('The current Instagram post id does not match')
    if await owner.get_attribute('content') != owner_id:
        raise RuntimeError('The Instagram post author does not match the signed-in user')
    main = page.locator('main')
    await expect(main).to_have_count(1)
    await expect(main).to_contain_text(expected_text, timeout=60_000)
    # The meta description carries the post caption and comments never enter it; the double check stops a sentence that only appears in a comment.
    caption_metadata = page.locator('meta[name="description"]')
    await expect(caption_metadata).to_have_count(1)
    if expected_text not in (await caption_metadata.get_attribute('content') or ''):
        raise RuntimeError('The Instagram caption metadata lacks the expected text; verify with a short phrase from the original caption')
    # Photo, carousel and Reel details all emit the same app deep-link metadata holding the current numeric id.
    # Use the platform's own identity field instead of recommendation or internal query-variable differences.
    deep_link = page.locator('meta[property="al:ios:url"]')
    await expect(deep_link).to_have_count(1)
    match = re.fullmatch(r'instagram://media\?id=(\d+)', await deep_link.get_attribute('content'))
    if not match:
        raise RuntimeError('The Instagram details page exposes no numeric id for the current post')
    return {'post_id': shortcode, 'content_id': f'{match.group(1)}_{owner_id}', 'post_url': post_url,
            'owner_id': owner_id, 'expected_text': expected_text, 'status': 'published'}


async def instagram_post_action(account_file: Path, *, post_url: str, expected_text: str, delete: bool = False,
                                proxy: str | None = None, headless: bool = False,
                                result_file: str | Path | None = None) -> dict:
    """Verify the post, delete once and accept only a did_delete response for the target id."""
    instagram_post_id(post_url)
    result_file = Path(result_file) if result_file else Path('.local/instagram-results') / f'{uuid4().hex}.json'
    result = {'platform': 'instagram', 'post_url': post_url, 'status': 'not_submitted'}
    async with async_playwright() as p:
        browser, context, page = await _open_instagram_page(p, account_file, proxy=proxy, headless=headless)
        try:
            identity = await instagram_identity(page, account_file)
            result.update(await find_instagram_post(page, post_url=post_url, expected_text=expected_text, owner_id=identity['user_id']))
            if delete:
                # The details' single three-dot menu carries aria-haspopup=dialog while comment reaction menus have no circle,
                # a structure seen in localized photo, carousel and Reel details, so no translated aria-label is used.
                menu_button = page.locator('[role="button"][aria-haspopup="dialog"]').filter(has=page.locator('svg circle'))
                await expect(menu_button).to_have_count(1)
                await menu_button.click()
                menu = page.get_by_role('dialog')
                buttons = menu.get_by_role('button')
                # The own-post menu has a fixed eight items with delete first, and the role covers native and non-native buttons.
                # The count assertion plus the verified author and post identity turn any structural change into an error instead of another menu.
                await expect(buttons).to_have_count(8, timeout=30_000)
                # A mouse activation sometimes only closes the popup, while this role=button accepts Enter and opens the confirmation by keyboard.
                await buttons.nth(0).press('Enter')
                # The confirmation is a titled modal dialog with exactly delete and cancel, delete first.
                # Keep it strictly apart from the previous menu and never treat a closed menu as deleted.
                confirm = page.locator('[role="dialog"][aria-modal="true"]').filter(has=page.get_by_role('heading'))
                await expect(confirm).to_have_count(1, timeout=60_000)
                confirm_buttons = confirm.get_by_role('button')
                await expect(confirm_buttons).to_have_count(2)
                result['status'] = 'deletion_unknown'
                result_file.parent.mkdir(parents=True, exist_ok=True)
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                target = f"/api/v1/web/create/{result['content_id']}/delete/"
                async with page.expect_response(lambda r: urlparse(r.url).path == target and r.request.method == 'POST', timeout=60_000) as event:
                    await confirm_buttons.nth(0).press('Enter')
                payload = instagram_response_payload(await (await event.value).text())
                if payload.get('payload', {}).get('did_delete') is not True:
                    raise RuntimeError('Instagram did not confirm the target post was deleted')
                result['status'] = 'deleted'
            result_file.parent.mkdir(parents=True, exist_ok=True)
            result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            await context.storage_state(path=str(account_file))
            return result
        except Exception as error:
            folder = Path('.local/instagram-errors') / uuid4().hex
            folder.mkdir(parents=True)
            result.update(error=str(error), evidence_dir=str(folder))
            result_file.parent.mkdir(parents=True, exist_ok=True)
            result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            await page.screenshot(path=str(folder/'page.png'))
            (folder/'page.html').write_text(await page.content(), encoding='utf-8')
            raise RuntimeError(f'Instagram post operation did not finish; result record: {result_file}; reason: {error}') from error
        finally:
            await browser.close()
