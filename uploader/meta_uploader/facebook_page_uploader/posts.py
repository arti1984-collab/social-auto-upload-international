"""Business Suite post lookup and deletion, keyed by content id rather than title."""

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from patchright.async_api import async_playwright, expect, TimeoutError as BrowserTimeoutError

from uploader.meta_uploader.facebook_page_uploader.main import _open_business_page


async def open_meta_post(page, *, list_url: str, page_name: str, expected_text: str,
                         content_id: str | None = None, schedule=None):
    """Look up the unique caption, check the Page and open the details; publishing and deletion share this verification."""
    # The platform search can still be empty for a fresh Reel, so read the raw list to sidestep search-index lag.
    # Only posts already in the list are covered; a timeout is reported, never a different post with the same caption.
    # The Reels create response is accepted first and only then reaches the content list, which may be a pre-processing snapshot.
    # Only refresh the lookup, never repost here; every read is bounded and stops as soon as a caption repeats.
    deadline = asyncio.get_running_loop().time() + 120
    row = page.get_by_role("row").filter(has_text=expected_text)
    while True:
        await page.goto(list_url, wait_until="domcontentloaded", timeout=90000)
        try:
            await row.wait_for(state='visible', timeout=10000)
        except BrowserTimeoutError:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('The post list holds no requested record; unverified, so do not repost')
        else:
            await expect(row).to_have_count(1)
            break
    await expect(row).to_contain_text(page_name)
    if parse_qs(urlparse(page.url).query).get('asset_id') != parse_qs(urlparse(list_url).query).get('asset_id'):
        raise RuntimeError("The list's Page ID differs from the request; nothing deleted")
    is_reel = 'Reels' in await row.inner_text()
    # In the published list the TITLE grid cell opens the details and metrics also carry aria-pressed, so they must not be mixed.
    # The scheduled list keeps the old layout where the title is the only clickable detail button.
    title = row.locator('[role="gridcell"][data-surface$=":TITLE"]') if '/published_posts' in list_url else row.locator('[role="button"][aria-pressed]')
    await expect(title).to_have_count(1)
    await title.click()
    if schedule:
        await expect(row).to_contain_text(f'{schedule.month}月{schedule.day}日 {schedule:%H:%M}')
    if '/published_posts' in list_url:
        # The new published list opens the performance details; the URL's content_id is the post id behind "copy post id".
        await page.wait_for_url('**/object_insights/**', timeout=30000)
        # The URL changes first while the old list may keep several menus; wait for the performance body, then scope to the visible menu.
        await page.locator('[data-surface$="BizWebObjectinsightsHeaderActionDropdown"] [aria-haspopup="menu"]').wait_for(timeout=120000)
        query = parse_qs(urlparse(page.url).query)
        ids = query.get('content_id', [])
        if len(ids) != 1 or not ids[0].isdigit() or query.get('asset_id') != parse_qs(urlparse(list_url).query).get('asset_id'):
            raise RuntimeError('Performance details lack a unique post id or the Page differs; nothing deleted')
        actual_id = ids[0]
    else:
        # The old detail panel links its h3 through aria-labelledby and the adjacent div holds the post id field.
        # Read the trailing digits instead of the localized label; title, caption and view counts never serve as the id.
        detail = page.locator('div[aria-labelledby]').filter(has=page.locator('[role="heading"][aria-level="3"] + div')).filter(visible=True)
        if await detail.count():
            await expect(detail).to_have_count(1, timeout=30000)
            number = detail.locator('[role="heading"][aria-level="3"] + div')
            await expect(number).to_have_count(1)
            number_text = await number.inner_text()
        else:
            # The controlled test page has no full detail container; the numeric field must still be unique and never fall back to title or row text.
            number = page.get_by_text(re.compile(r'^编号：\d+$'))
            await expect(number).to_have_count(1, timeout=30000)
            number_text = await number.inner_text()
        match = re.search(r'(\d+)$', number_text.strip())
        if not match:
            raise RuntimeError('The detail id field does not contain the post id; nothing deleted')
        actual_id = match.group(1)
    if content_id is not None and actual_id != content_id:
        raise RuntimeError(f'Post id mismatch: expected {content_id}, page shows {actual_id}; nothing deleted')
    return row, actual_id, is_reel


async def meta_post_action(account_file: Path, *, page_id: str, page_name: str,
                           content_id: str, expected_text: str, scheduled: bool = False,
                           delete: bool = False, proxy: str | None = None,
                           headless: bool = False) -> dict:
    """Check Page, content id and caption; scheduled posts are deleted permanently and published posts moved to the trash."""
    if not page_id.isdigit() or not content_id.isdigit() or not page_name.strip() or not expected_text.strip():
        raise ValueError("Needs numeric page-id/content-id, a Page name and a caption to verify")
    async with async_playwright() as playwright:
        browser, context, page = await _open_business_page(playwright, account_file, proxy=proxy, headless=headless)
        try:
            state = "scheduled_posts" if scheduled else "published_posts"
            list_url = f"https://business.facebook.com/latest/posts/{state}?asset_id={page_id}"
            row, actual_id, is_reel = await open_meta_post(page, list_url=list_url, page_name=page_name,
                                                   expected_text=expected_text, content_id=content_id)
            result = {"platform": "facebook-page", "page_id": page_id, "page_name": page_name,
                      "content_id": content_id, "expected_text": expected_text,
                      "status": "scheduled" if scheduled else "published"}
            if delete:
                # The published post's detail menu carries an explicit delete action marker and the title id is already verified,
                # so no translated dropdown or delete label is used and no same-named button is looked up page-wide.
                if scheduled:
                    # The old detail menu has no action surface of its own; scope to the panel holding the h3
                    # and exclude the aria-labelled post-preview menu. The five verified items are edit, copy, reschedule, move to drafts, delete.
                    detail = page.locator('div[aria-labelledby]').filter(has=page.locator('[role="heading"][aria-level="3"] + div')).filter(visible=True)
                    await expect(detail).to_have_count(1)
                    menu_button = detail.locator('[role="button"][aria-haspopup="menu"]:not([aria-label])')
                    await expect(menu_button).to_have_count(1)
                    await menu_button.click()
                    items = page.get_by_role('menu').get_by_role('menuitem')
                    count = await items.count()
                    if count not in (4, 5):
                        raise RuntimeError(f'Unrecognized scheduled-detail menu structure: {count} items, nothing deleted')
                    # Delete is always the last item; a localized menu or fewer permissions can omit "move to drafts".
                    await items.nth(count - 1).click()
                else:
                    dropdown = page.locator('[data-surface$="BizWebObjectinsightsHeaderActionDropdown"] [aria-haspopup="menu"]')
                    await expect(dropdown).to_have_count(1)
                    await dropdown.click()
                    action = page.locator('[data-surface$="match_container:TofuObjectInsightsDeleteAction"] [role="menuitem"]')
                    await expect(action).to_have_count(1)
                    await action.click()
                # The real confirmation has dialog/aria-labelledby/tabindex=-1, which an older implementation misread as no dialog.
                # The detail panel lacks these attributes. The confirmation's three items are close, cancel, main action,
                # so any change in count or scope stops us instead of picking localized text or the page's last button.
                dialog = page.locator('[role="dialog"][aria-labelledby][tabindex="-1"]').filter(visible=True)
                await expect(dialog).to_have_count(1)
                actions = dialog.get_by_role('button')
                await expect(actions).to_have_count(2)
                await actions.nth(1).click()
                await expect(dialog).to_have_count(0, timeout=30000)
                await expect(row).to_have_count(0, timeout=45000)
                if not scheduled:
                    # After deleting from performance details the platform navigates back, so wait it out to avoid a competing refresh and ERR_ABORTED.
                    await page.wait_for_url('**/posts/published_posts**', wait_until='domcontentloaded', timeout=90000)
                # Reload the server list after deleting instead of trusting an optimistic removal; look up only, never delete again.
                deadline = asyncio.get_running_loop().time() + 60
                while True:
                    await page.goto(list_url, wait_until="domcontentloaded", timeout=90000)
                    # The unfiltered list is loaded only with post rows or an explicit empty state; search-index lag does not prove deletion.
                    loaded = page.get_by_role('row').filter(has=page.locator('[role="button"][aria-pressed]')).or_(page.get_by_text('没有定时帖', exact=True))
                    try:
                        await expect(loaded).not_to_have_count(0, timeout=10000)
                        await expect(page.get_by_role('row').filter(has_text=expected_text)).to_have_count(0, timeout=10000)
                    except BrowserTimeoutError:
                        if asyncio.get_running_loop().time() >= deadline:
                            raise TimeoutError("Deletion submitted but the refreshed list has not confirmed the post is gone; look it up first and do not delete again")
                    else:
                        break
                result["status"] = "deleted" if scheduled else "trashed"
            result["checked_at"] = datetime.now(timezone.utc).isoformat()
            await context.storage_state(path=str(account_file))
            return result
        except Exception:
            # Keep the real page on failure to diagnose a redesign or unknown result; never retry the remote delete.
            directory = Path('.local/meta-errors') / uuid4().hex
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'page.txt').write_text(page.url + '\n' + await page.locator('body').inner_text(), encoding='utf-8')
            await page.screenshot(path=str(directory / 'page.png'))
            raise
        finally:
            await browser.close()
