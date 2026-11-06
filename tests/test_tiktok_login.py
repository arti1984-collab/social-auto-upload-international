"""TikTok login: one session path for writing and reading, plus the wait loop instead of page.pause()."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from conf import BASE_DIR
from uploader.tk_uploader import main_chrome
from utils import browser as browser_module


class AccountPathTests(unittest.TestCase):
    def test_relative_name_lands_in_the_documented_folder(self):
        self.assertEqual(
            main_chrome.account_path("account.json"),
            Path(BASE_DIR) / "cookies" / "tk_uploader" / "account.json",
        )

    def test_documented_relative_path_maps_to_the_same_file(self):
        self.assertEqual(
            main_chrome.account_path("cookies/tk_uploader/account.json"),
            Path(BASE_DIR) / "cookies" / "tk_uploader" / "account.json",
        )

    def test_absolute_path_is_used_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "session.json"
            self.assertEqual(main_chrome.account_path(str(target)), target)

    def test_returns_a_path_even_for_a_string(self):
        # get_tiktok_cookie relies on .parent, which a str does not have.
        self.assertIsInstance(main_chrome.account_path("account.json"), Path)

    def test_create_makes_the_parent_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "nested" / "session.json"
            created = main_chrome.account_path(str(target), create=True)
            self.assertTrue(created.parent.is_dir())
            self.assertFalse(created.exists())


class _FakePage:
    def __init__(self):
        self.polls = 0

    async def wait_for_timeout(self, milliseconds):
        self.polls += 1


class _FakeContext:
    """Returns no session cookie until ``signed_in_after`` polls have passed."""

    def __init__(self, signed_in_after=None):
        self.signed_in_after = signed_in_after
        self.calls = 0

    async def cookies(self):
        self.calls += 1
        if self.signed_in_after is not None and self.calls > self.signed_in_after:
            return [{"name": "sessionid", "value": "x"}]
        return [{"name": "tt_csrf_token", "value": "y"}]


class WaitForLoginTests(unittest.TestCase):
    def _wait(self, context, timeout_s=6, interval_s=2):
        page = _FakePage()
        result = asyncio.run(
            main_chrome._wait_for_login(page, context, timeout_s=timeout_s, interval_s=interval_s)
        )
        return result, page

    def test_signed_in_immediately(self):
        result, page = self._wait(_FakeContext(signed_in_after=0))

        self.assertTrue(result)
        self.assertEqual(page.polls, 0)

    def test_signed_in_after_two_polls(self):
        result, page = self._wait(_FakeContext(signed_in_after=2))

        self.assertTrue(result)
        self.assertEqual(page.polls, 2)

    def test_timeout_without_sign_in(self):
        result, page = self._wait(_FakeContext())

        self.assertFalse(result)
        self.assertEqual(page.polls, 3)  # 6 s / 2 s


class TiktokSetupTests(unittest.TestCase):
    def test_missing_session_without_handle_returns_false_and_starts_no_browser(self):
        calls = []

        async def fake_cookie_auth(account_file):
            calls.append(account_file)
            return True

        with tempfile.TemporaryDirectory() as folder:
            browser_module.set_profile_root(Path(folder) / "profiles")
            try:
                with patch.object(main_chrome, "cookie_auth", fake_cookie_auth):
                    result = asyncio.run(main_chrome.tiktok_setup("missing.json", handle=False))
            finally:
                browser_module.set_profile_root(None)

        self.assertFalse(result)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
