"""Deletion cannot be undone, so the key check is that a mismatched identity never reaches it."""

import asyncio
import unittest

from patchright.async_api import async_playwright

from tests.browser import launch_test_browser

from uploader.meta_uploader.facebook_uploader.posts import facebook_post_id, find_facebook_post
from uploader.meta_uploader.facebook_page_uploader.posts import open_meta_post


class FacebookPostIdentityTests(unittest.TestCase):
    def test_accepts_reel_and_photo_post_permalink(self):
        self.assertEqual(facebook_post_id('https://www.facebook.com/reel/123/'), '123')
        self.assertEqual(facebook_post_id('https://www.facebook.com/permalink.php?story_fbid=pfbidABC123&id=42'), 'pfbidABC123')

    def test_rejects_profile_external_site_and_ambiguous_id(self):
        for url in ('https://www.facebook.com/profile.php?id=42', 'https://facebook.com.evil/reel/123/',
                    'http://www.facebook.com/reel/123/', 'https://www.facebook.com/permalink.php?story_fbid=1&story_fbid=2'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                facebook_post_id(url)

    def test_same_caption_cannot_select_another_post(self):
        async def scenario():
            async with async_playwright() as p:
                browser = await launch_test_browser(p)
                context = await browser.new_context()
                await context.add_cookies([{'name': 'c_user', 'value': '42', 'domain': '.facebook.com', 'path': '/'}])
                page = await context.new_page()
                html = '''<article role="article"><span>same caption</span><a href="/profile.php?id=42">Author</a><a href="/reel/111/">old</a></article>
                <article role="article"><span>same caption</span><a href="/profile.php?id=42">Author</a><a href="/reel/222/">target</a></article>'''
                await page.route('https://www.facebook.com/**', lambda route: route.fulfill(body=html, content_type='text/html'))
                try:
                    article = await find_facebook_post(page, post_url='https://www.facebook.com/reel/222/', owner_id='42', expected_text='same caption')
                    self.assertIn('target', await article.inner_text())
                    self.assertNotIn('old', await article.inner_text())
                    with self.assertRaisesRegex(RuntimeError, 'Signed-in'):
                        await find_facebook_post(page, post_url='https://www.facebook.com/reel/222/', owner_id='99', expected_text='same caption')
                finally:
                    await browser.close()
        asyncio.run(scenario())


class MetaPostIdentityTests(unittest.TestCase):
    def test_page_content_number_mismatch_stops_before_delete(self):
        """Even with the right caption and Page, a post with a different id must be rejected."""
        async def scenario():
            async with async_playwright() as p:
                browser = await launch_test_browser(p)
                page = await browser.new_page()
                html = '''<input placeholder="按编号或配文搜索">
                <div role="row">Page name
                  <div role="button" aria-pressed="false" onclick="document.getElementById('detail').hidden=false">caption</div>
                </div><div id="detail" hidden>编号：123</div>'''
                await page.route('https://business.facebook.com/**', lambda route: route.fulfill(body=html, content_type='text/html; charset=utf-8'))
                try:
                    with self.assertRaisesRegex(RuntimeError, 'id mismatch'):
                        await open_meta_post(page, list_url='https://business.facebook.com/latest/posts/scheduled_posts?asset_id=42',
                            page_name='Page name', expected_text='caption', content_id='999')
                finally:
                    await browser.close()
        asyncio.run(scenario())
