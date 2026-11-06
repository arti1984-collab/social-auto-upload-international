"""Persistent profiles: listing, removal and the profile CLI command."""
import argparse
import asyncio
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sau_cli
from sau_commands.arguments import apply_use_profile
from utils import browser as browser_module
from utils.conf_settings import set_conf_values


class ProfileCommandTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        browser_module.set_profile_root(self.folder.name)
        browser_module.set_profile_mode(True)

    def tearDown(self):
        browser_module.set_profile_mode(None)
        browser_module.set_profile_root(None)
        browser_module.set_default_browser(None)
        browser_module.set_default_profile(None)

    def _make(self, browser, account, payload=b"x" * 2048):
        directory = Path(self.folder.name) / browser / account
        (directory / "Default").mkdir(parents=True)
        (directory / "Default" / "Cookies").write_bytes(payload)
        return directory

    def test_list_reports_browser_account_and_size(self):
        self._make("chrome", "youtube_main")
        self._make("firefox", "instagram_creator", b"y" * 1024)

        entries = {entry["account"]: entry for entry in browser_module.list_profiles()}

        self.assertEqual(set(entries), {"youtube_main", "instagram_creator"})
        self.assertEqual(entries["youtube_main"]["browser"], "chrome")
        self.assertGreaterEqual(entries["youtube_main"]["bytes"], 2048)
        self.assertIsNotNone(entries["youtube_main"]["last_used"])

    def test_list_can_be_limited_to_one_browser(self):
        self._make("chrome", "youtube_main")
        self._make("firefox", "instagram_creator")

        accounts = [entry["account"] for entry in browser_module.list_profiles("firefox")]

        self.assertEqual(accounts, ["instagram_creator"])

    def test_remove_deletes_only_the_requested_profile(self):
        target = self._make("chrome", "youtube_main")
        other = self._make("chrome", "facebook_main")

        result = browser_module.remove_profile("youtube_main", browser="chrome")

        self.assertFalse(target.exists())
        self.assertTrue(other.exists())
        self.assertGreaterEqual(result["bytes"], 2048)

    def test_remove_reports_a_missing_profile(self):
        with self.assertRaises(FileNotFoundError):
            browser_module.remove_profile("nothing_here", browser="chrome")

    def test_list_marks_the_stored_default(self):
        self._make("chrome", "youtube_main")
        browser_module.set_default_profile("youtube_main")
        args = sau_cli.build_parser().parse_args(["profile", "list"])
        out = io.StringIO()

        with contextlib.redirect_stdout(out):
            self.assertEqual(asyncio.run(sau_cli.dispatch(args)), 0)

        self.assertIn("DEFAULT", out.getvalue())
        self.assertIn("yes", out.getvalue())

    def test_use_writes_browser_profile_mode_and_default(self):
        self._make("firefox", "youtube_main")
        recorded = {}
        args = sau_cli.build_parser().parse_args(["profile", "use", "firefox/youtube_main"])

        with patch("sau_commands.profile.set_conf_values", lambda values: recorded.update(values)):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(asyncio.run(sau_cli.dispatch(args)), 0)

        self.assertEqual(recorded["LOCAL_BROWSER"], '"firefox"')
        self.assertEqual(recorded["LOCAL_BROWSER_PROFILE"], "True")
        self.assertEqual(recorded["DEFAULT_PROFILE"], '"youtube_main"')

    def test_use_clear_empties_only_the_default(self):
        recorded = {}
        args = sau_cli.build_parser().parse_args(["profile", "use", "--clear"])

        with patch("sau_commands.profile.set_conf_values", lambda values: recorded.update(values)):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(asyncio.run(sau_cli.dispatch(args)), 0)

        self.assertEqual(recorded, {"DEFAULT_PROFILE": '""'})

    def test_cli_list_prints_the_table(self):
        self._make("chrome", "youtube_main")
        args = sau_cli.build_parser().parse_args(["profile", "list"])
        out = io.StringIO()

        with contextlib.redirect_stdout(out):
            self.assertEqual(asyncio.run(sau_cli.dispatch(args)), 0)

        self.assertIn("BROWSER", out.getvalue())
        self.assertIn("youtube_main", out.getvalue())

    def test_cli_remove_accepts_a_platform_prefix(self):
        target = self._make("chrome", "youtube_main")
        args = sau_cli.build_parser().parse_args(
            ["profile", "remove", "--platform", "youtube", "--account", "main", "--browser", "chrome"]
        )

        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(asyncio.run(sau_cli.dispatch(args)), 0)

        self.assertFalse(target.exists())
        self.assertIn("Removed", out.getvalue())

    def test_cli_reports_an_unknown_profile(self):
        args = sau_cli.build_parser().parse_args(
            ["profile", "remove", "--account", "nope", "--browser", "chrome"]
        )

        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(FileNotFoundError):
                asyncio.run(sau_cli.dispatch(args))


class UseProfileTests(unittest.TestCase):
    """--use-profile replaces --browser and --account with one stored profile."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        browser_module.set_profile_root(self.folder.name)

    def tearDown(self):
        browser_module.set_profile_mode(None)
        browser_module.set_profile_root(None)
        browser_module.set_default_browser(None)
        browser_module.set_default_profile(None)

    def _make(self, browser, account):
        directory = Path(self.folder.name) / browser / account
        (directory / "Default").mkdir(parents=True)
        (directory / "Default" / "Cookies").write_bytes(b"x")
        return directory

    def _video(self):
        path = Path(self.folder.name) / "clip.mp4"
        path.write_bytes(b"x")
        return path

    def test_sets_browser_account_and_profile_mode(self):
        self._make("firefox", "youtube_main")
        args = argparse.Namespace(
            use_profile="firefox/youtube_main", account=None, platform="youtube"
        )

        apply_use_profile(args)

        self.assertEqual(args.account, "main")
        self.assertEqual(browser_module.default_browser(), "firefox")
        self.assertTrue(browser_module.profile_mode())

    def test_accepts_an_account_name_that_exists_once(self):
        self._make("chrome", "youtube_main")
        args = argparse.Namespace(use_profile="youtube_main", account=None, platform="youtube")

        apply_use_profile(args)

        self.assertEqual(args.account, "main")
        self.assertEqual(browser_module.default_browser(), "chrome")

    def test_reports_ambiguity_and_unknown_profiles(self):
        self._make("chrome", "youtube_main")
        self._make("firefox", "youtube_main")

        with self.assertRaises(ValueError):
            browser_module.find_profile("youtube_main")
        with self.assertRaises(FileNotFoundError):
            browser_module.find_profile("chrome/unknown")

    def test_rejects_a_profile_of_another_platform(self):
        self._make("chrome", "facebook_main")
        args = argparse.Namespace(
            use_profile="chrome/facebook_main", account=None, platform="youtube"
        )

        with self.assertRaises(ValueError):
            apply_use_profile(args)

    def test_cli_accepts_use_profile_without_account(self):
        self._make("chrome", "youtube_main")
        args = sau_cli.build_parser().parse_args(
            [
                "youtube",
                "upload-video",
                "--use-profile",
                "chrome/youtube_main",
                "--file",
                str(self._video()),
                "--title",
                "Titel",
            ]
        )

        self.assertIsNone(args.account)
        apply_use_profile(args)
        self.assertEqual(args.account, "main")

    def test_stored_default_fills_the_account_of_its_platform(self):
        browser_module.set_default_profile("youtube_main")
        args = argparse.Namespace(use_profile=None, account=None, platform="youtube")

        apply_use_profile(args)

        self.assertEqual(args.account, "main")
        self.assertTrue(browser_module.profile_mode())

    def test_stored_default_is_ignored_for_other_platforms(self):
        browser_module.set_default_profile("youtube_main")
        args = argparse.Namespace(use_profile=None, account=None, platform="instagram")

        apply_use_profile(args)

        self.assertIsNone(args.account)

    def test_check_actions_accept_use_profile(self):
        self._make("firefox", "youtube_main")
        args = sau_cli.build_parser().parse_args(
            ["youtube", "check", "--use-profile", "firefox/youtube_main"]
        )

        apply_use_profile(args)

        self.assertEqual(args.account, "main")
        self.assertEqual(browser_module.default_browser(), "firefox")

    def test_cli_reports_a_missing_account(self):
        args = sau_cli.build_parser().parse_args(
            ["youtube", "upload-video", "--file", str(self._video()), "--title", "Titel"]
        )

        with self.assertRaises(RuntimeError):
            asyncio.run(sau_cli.dispatch(args))


class _StubPlatform:
    """Stand-in for a platform module: records whether profile mode was on."""

    def __init__(self, code=0):
        self.code = code
        self.profile_mode = None

    async def run(self, args):
        self.profile_mode = browser_module.profile_mode()
        return self.code


class LoginProfileTests(unittest.TestCase):
    """A login runs in a persistent profile and stores it as the default."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        browser_module.set_profile_root(self.folder.name)

    def tearDown(self):
        browser_module.set_profile_mode(None)
        browser_module.set_profile_root(None)
        browser_module.set_default_browser(None)
        browser_module.set_default_profile(None)

    def test_login_uses_profile_mode_and_stores_the_default(self):
        stub = _StubPlatform()
        recorded = {}
        args = sau_cli.build_parser().parse_args(["youtube", "login", "--account", "main"])

        with patch.dict(sau_cli.PLATFORMS, {"youtube": stub}), patch(
            "sau_cli.remember_default_profile",
            lambda browser, key: recorded.update(browser=browser, key=key) or Path("conf.py"),
        ):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(asyncio.run(sau_cli.dispatch(args)), 0)

        self.assertTrue(stub.profile_mode)
        self.assertEqual(recorded["key"], "youtube_main")
        self.assertIn("youtube_main", out.getvalue())

    def test_upload_keeps_the_previous_default(self):
        stub = _StubPlatform()
        recorded = {}
        video = Path(self.folder.name) / "clip.mp4"
        video.write_bytes(b"x")
        args = sau_cli.build_parser().parse_args(
            ["youtube", "upload-video", "--account", "main", "--file", str(video), "--title", "T"]
        )

        with patch.dict(sau_cli.PLATFORMS, {"youtube": stub}), patch(
            "sau_cli.remember_default_profile", lambda browser, key: recorded.update(key=key)
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                asyncio.run(sau_cli.dispatch(args))

        self.assertFalse(stub.profile_mode)
        self.assertEqual(recorded, {})

    def test_failed_login_stores_nothing(self):
        stub = _StubPlatform(code=1)
        recorded = {}
        args = sau_cli.build_parser().parse_args(["youtube", "login", "--account", "main"])

        with patch.dict(sau_cli.PLATFORMS, {"youtube": stub}), patch(
            "sau_cli.remember_default_profile", lambda browser, key: recorded.update(key=key)
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(asyncio.run(sau_cli.dispatch(args)), 1)

        self.assertEqual(recorded, {})


class ConfSettingsTests(unittest.TestCase):
    """conf.py is edited in place: only the named assignments change."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "conf.py"

    def test_updates_existing_values_and_keeps_comments(self):
        self.path.write_text(
            '# LOCAL_BROWSER = "edge"\nLOCAL_BROWSER = "chrome"\n'
            "LOCAL_BROWSER_PROFILE = False\nOTHER = 1\n",
            encoding="utf-8",
        )

        set_conf_values(
            {
                "LOCAL_BROWSER": '"firefox"',
                "LOCAL_BROWSER_PROFILE": "True",
                "DEFAULT_PROFILE": '"youtube_main"',
            },
            path=self.path,
        )

        text = self.path.read_text(encoding="utf-8")
        self.assertIn('LOCAL_BROWSER = "firefox"', text)
        self.assertIn('# LOCAL_BROWSER = "edge"', text)
        self.assertIn("LOCAL_BROWSER_PROFILE = True", text)
        self.assertIn('DEFAULT_PROFILE = "youtube_main"', text)
        self.assertIn("OTHER = 1", text)

    def test_repeated_updates_do_not_duplicate_a_setting(self):
        set_conf_values({"DEFAULT_PROFILE": '"youtube_main"'}, path=self.path)
        set_conf_values({"DEFAULT_PROFILE": '"facebook_main"'}, path=self.path)

        text = self.path.read_text(encoding="utf-8")
        self.assertEqual(text.count("DEFAULT_PROFILE"), 1)
        self.assertIn('DEFAULT_PROFILE = "facebook_main"', text)


if __name__ == "__main__":
    unittest.main()
