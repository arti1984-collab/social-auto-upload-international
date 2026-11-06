"""Look up a profile post and move the verified post id to the trash."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path

from patchright.async_api import Page, async_playwright, expect

from uploader.meta_uploader.facebook_uploader.main import _open_facebook_page


def facebook_post_id(url: str) -> str:
    """Accept only Facebook post links; a profile URL or an external URL is never a delete target."""
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.facebook.com", "facebook.com"}:
        raise ValueError("The post link must be a post under https://www.facebook.com/")
    match = re.fullmatch(r"/(?:reel|posts|videos)/(\d+|pfbid[A-Za-z0-9]+)/?", parsed.path)
    if not match:
        match = re.fullmatch(r"/[A-Za-z0-9._-]+/(?:posts|videos)/(\d+|pfbid[A-Za-z0-9]+)/?", parsed.path)
    if match:
        return match.group(1)
    if parsed.path == "/permalink.php":
        ids = parse_qs(parsed.query).get("story_fbid", [])
        if len(ids) == 1 and re.fullmatch(r'\d+|pfbid[A-Za-z0-9]+', ids[0]):
            return ids[0]
    raise ValueError("No unambiguous post id could be read from the post link")


async def find_facebook_post(page: Page, *, post_url: str, owner_id: str, expected_text: str):
    """Cross-check text, author and post link on the signed-in user's own profile."""
    post_id = facebook_post_id(post_url)
    if not owner_id.isdigit() or not expected_text.strip():
        raise ValueError("Verifying a post needs a numeric owner-id and a non-empty expected-text")
    # c_user is the browser's signed-in identity; never delete on a given profile from another account.
    cookies = await page.context.cookies("https://www.facebook.com/")
    users = {cookie["value"] for cookie in cookies if cookie["name"] == "c_user"}
    if users != {owner_id}:
        raise RuntimeError("Signed-in Facebook user does not match owner-id")
    await page.goto(f"https://www.facebook.com/profile.php?id={owner_id}", wait_until="domcontentloaded", timeout=90000)
    # article is the profile's post card; the text only narrows the search while identity rests on the post id and author link.
    articles = page.get_by_role("article").filter(has_text=expected_text)
    deadline = asyncio.get_running_loop().time() + 45
    while asyncio.get_running_loop().time() < deadline:
        matches = []
        for article in await articles.all():
            links = await article.locator("a[href]").evaluate_all("els => els.map(e => e.href)")
            ids = set()
            for link in links:
                try:
                    ids.add(facebook_post_id(link))
                except ValueError:
                    continue
            if post_id not in ids:
                continue
            from urllib.parse import parse_qs, urlparse
            authors = [link for link in links if urlparse(link).path == "/profile.php"
                       and parse_qs(urlparse(link).query).get("id") == [owner_id]]
            if not authors:
                raise RuntimeError("The post id matches but the author identity was not verified")
            matches.append(article)
        if len(matches) > 1:
            raise RuntimeError("Several posts on the profile share this id; stopping")
        if matches:
            return matches[0]
        # Only scroll the existing profile: never repost, and never read "not found" as deleted.
        await page.mouse.wheel(0, 650)
        await page.wait_for_timeout(1000)
    raise RuntimeError("No profile post matched text, author and id; nothing was deleted")


async def find_trashed_facebook_post(page: Page, *, post_url: str, owner_id: str, expected_text: str):
    """Verify the post through the trash record's view link instead of guessing identity from a title."""
    post_id = facebook_post_id(post_url)
    # This URL comes from the real "activity log -> trash" navigation; category_key pins the trash.
    await page.goto(f"https://www.facebook.com/{owner_id}/allactivity?activity_history=false&category_key=TRASH&manage_mode=true&should_load_landing_page=false",
                    wait_until="domcontentloaded", timeout=90000)
    # The view link keeps the post id; the nearest ancestor holding the "more options" button is the single record.
    link = page.get_by_role('link', name='查看', exact=True).locator(f'xpath=self::a[contains(@href,"/{post_id}/") or contains(@href,"story_fbid={post_id}")]')
    await expect(link).to_have_count(1, timeout=30000)
    if facebook_post_id(await link.get_attribute('href')) != post_id:
        raise RuntimeError("The trash view link carries a different post id")
    row = link.locator('xpath=ancestor::div[.//a[contains(@href,"profile.php?id=")] and .//*[@role="button" and contains(@aria-label,"的更多选项")]][1]')
    await expect(row).to_have_count(1)
    await expect(row).to_contain_text(expected_text)
    author = row.locator(f'a[href="https://www.facebook.com/profile.php?id={owner_id}"]')
    await expect(author).to_have_count(1)
    return row


async def trash_facebook_post(page: Page, article, *, post_url: str, owner_id: str, expected_text: str) -> str:
    """Reach the trash through the verified post menu; submit once and wait for explicit platform confirmation."""
    # The menu button lives in the verified post card and its aria-label names the post, so like/share actions are excluded.
    menu_button = article.get_by_role("button", name=re.compile(r"^可对.+的这篇帖子执行的操作$"))
    await expect(menu_button).to_have_count(1)
    await menu_button.click()
    menu = page.get_by_role("menu")
    await expect(menu).to_have_count(1)
    await menu.get_by_role("menuitem").filter(has_text="移至垃圾箱").click()
    # The confirmation dialog's move button is the real submit action; never click a same-named button elsewhere.
    dialog = page.get_by_role("dialog").filter(has_text="移至垃圾箱？")
    await expect(dialog).to_have_count(1)
    await dialog.get_by_role("button", name="转移", exact=True).click()
    # No success toast exists; wait for the dialog and card to disappear, then look the id up in the trash instead of guessing a message.
    await expect(dialog).to_have_count(0, timeout=30000)
    await expect(article).to_have_count(0, timeout=30000)
    await find_trashed_facebook_post(page, post_url=post_url, owner_id=owner_id, expected_text=expected_text)
    return "trashed"


async def verify_facebook_deletion(page: Page, *, owner_id: str, post_url: str) -> None:
    """Permanent deletion lets the background list lag, so poll the lookup only and never resubmit the delete."""
    post_id = facebook_post_id(post_url)
    deadline = asyncio.get_running_loop().time() + 90
    while asyncio.get_running_loop().time() < deadline:
        await page.goto(f"https://www.facebook.com/{owner_id}/allactivity?activity_history=false&category_key=TRASH&manage_mode=true&should_load_landing_page=false",
                        wait_until="domcontentloaded", timeout=90000)
        await page.get_by_text("只有你能看到垃圾箱里的内容。", exact=True).wait_for(timeout=30000)
        # The heading appears before the records; wait for the empty-state text or a real record link, never treat loading as deleted.
        empty = page.get_by_text("好冷清，一片落叶飘过~", exact=True)
        records = page.get_by_role("link", name="查看", exact=True)
        for _ in range(30):
            if await empty.is_visible() or await records.count():
                break
            await page.wait_for_timeout(500)
        else:
            raise RuntimeError("Trash records never loaded, so the permanent deletion is unverified; look the post up instead of deleting again")
        ids = set()
        for link in await records.evaluate_all("es => es.map(e => e.href)"):
            try:
                ids.add(facebook_post_id(link))
            except ValueError:
                continue
        if post_id not in ids:
            return
        await page.wait_for_timeout(3000)
    raise TimeoutError("Permanent deletion was submitted but the trash still holds the id; unverified, so never retry automatically")


async def facebook_post_action(account_file: Path, *, post_url: str, owner_id: str,
                               expected_text: str, delete: bool = False,
                               permanent: bool = False, from_trash: bool = False, deleted: bool = False,
                               proxy: str | None = None, headless: bool = False) -> dict:
    """CLI entry point for looking up and deleting a post; success is returned only on explicit platform feedback."""
    facebook_post_id(post_url)
    async with async_playwright() as playwright:
        browser, context, page = await _open_facebook_page(playwright, account_file, proxy=proxy, headless=headless)
        try:
            cookies = await context.cookies("https://www.facebook.com/")
            if {c["value"] for c in cookies if c["name"] == "c_user"} != {owner_id}:
                raise RuntimeError("Signed-in Facebook user does not match owner-id")
            if not owner_id.isdigit() or not expected_text.strip():
                raise ValueError("owner-id must be numeric and expected-text must not be empty")
            if deleted:
                if delete:
                    raise ValueError("Verifying a permanent deletion cannot run another delete")
                await verify_facebook_deletion(page, owner_id=owner_id, post_url=post_url)
            elif from_trash:
                article = await find_trashed_facebook_post(page, post_url=post_url, owner_id=owner_id, expected_text=expected_text)
            else:
                article = await find_facebook_post(page, post_url=post_url, owner_id=owner_id, expected_text=expected_text)
            result = {"platform": "facebook", "owner_id": owner_id,
                      "post_id": facebook_post_id(post_url), "post_url": post_url,
                      "expected_text": expected_text, "status": "absent_from_trash" if deleted else "trashed" if from_trash else "found"}
            if delete:
                if not from_trash:
                    result["status"] = await trash_facebook_post(page, article, post_url=post_url, owner_id=owner_id, expected_text=expected_text)
                if permanent:
                    row = await find_trashed_facebook_post(page, post_url=post_url, owner_id=owner_id, expected_text=expected_text)
                    # A single trash record's menu is isolated from bulk deletion; never touch the "all" checkbox.
                    await row.get_by_role("button", name=re.compile(r"^针对.+的更多选项$")).click()
                    await page.get_by_role("menu").get_by_role("menuitem", name="删除", exact=True).click()
                    dialog = page.get_by_role("dialog").filter(has_text="确定删除？")
                    await expect(dialog).to_contain_text("你删除的内容将无法恢复。")
                    await dialog.get_by_role("button", name="删除", exact=True).click()
                    await expect(dialog).to_have_count(0, timeout=30000)
                    await expect(row).to_have_count(0, timeout=30000)
                    await verify_facebook_deletion(page, owner_id=owner_id, post_url=post_url)
                    result["status"] = "deleted"
            result["checked_at"] = datetime.now(timezone.utc).isoformat()
            await context.storage_state(path=str(account_file))
            return result
        finally:
            await browser.close()
