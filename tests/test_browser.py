"""Browser selection: engine, channel, executable and launch keyword handling."""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from utils import browser as browser_module


class FakeBrowser:
    def __init__(self):
        self.new_context = AsyncMock(return_value="cookie-context")


class FakeEngine:
    def __init__(self):
        self.browser = FakeBrowser()
        self.launch = AsyncMock(return_value=self.browser)
        self.launch_persistent_context = AsyncMock(return_value="profile-context")


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeEngine()
        self.firefox = FakeEngine()


class BrowserSelectionTests(unittest.TestCase):
    def tearDown(self):
        browser_module.set_default_browser(None)
        os.environ.pop("SAU_BROWSER", None)

    def test_chrome_and_edge_use_installed_chromium_channels(self):
        self.assertEqual(browser_module.browser_spec("chrome").channel, "chrome")
        edge = browser_module.browser_spec("edge")
        self.assertEqual(edge.channel, "msedge")
        self.assertEqual(edge.engine, "chromium")

    def test_opera_gx_has_no_channel_and_needs_its_own_executable(self):
        spec = browser_module.browser_spec("opera-gx")
        self.assertEqual(spec.engine, "chromium")
        self.assertIsNone(spec.channel)
        self.assertTrue(spec.needs_executable)

    def test_firefox_switches_to_the_firefox_engine(self):
        engine, options = browser_module.launch_options(browser="firefox", headless=True)
        self.assertEqual(engine, "firefox")
        self.assertNotIn("channel", options)

    def test_unknown_browser_names_the_alternatives(self):
        with self.assertRaises(ValueError) as caught:
            browser_module.browser_spec("safari")
        message = str(caught.exception)
        for name in ("chrome", "edge", "opera-gx", "firefox"):
            self.assertIn(name, message)

    def test_aliases_are_accepted(self):
        self.assertEqual(browser_module.browser_spec("msedge").name, "edge")
        self.assertEqual(browser_module.browser_spec("Opera GX").name, "opera-gx")
        self.assertEqual(browser_module.browser_spec("opera").name, "opera-gx")

    def test_environment_selects_the_default_browser(self):
        os.environ["SAU_BROWSER"] = "firefox"
        self.assertEqual(browser_module.default_browser(), "firefox")
        self.assertEqual(browser_module.browser_spec().engine, "firefox")

    def test_explicit_flag_wins_over_the_environment(self):
        os.environ["SAU_BROWSER"] = "firefox"
        browser_module.set_default_browser("edge")
        self.assertEqual(browser_module.default_browser(), "edge")

    def test_explicit_path_overrides_the_opera_gx_lookup(self):
        _, options = browser_module.launch_options(
            browser="opera-gx", executable_path="C:/Opera GX/opera.exe"
        )
        self.assertEqual(options["executable_path"], "C:/Opera GX/opera.exe")

    def test_launch_forwards_headless_channel_and_proxy(self):
        playwright = FakePlaywright()
        browser_module.set_default_browser("edge")

        result = asyncio.run(
            browser_module.launch(
                playwright, headless=False, proxy={"server": "http://127.0.0.1:7890"}
            )
        )

        self.assertIs(result, playwright.chromium.browser)
        playwright.chromium.launch.assert_awaited_once_with(
            headless=False,
            channel="msedge",
            proxy={"server": "http://127.0.0.1:7890"},
            args=list(browser_module.ANTI_THROTTLE_ARGS),
        )
        playwright.firefox.launch.assert_not_awaited()

    def test_chromium_keeps_running_in_the_background_with_caller_args(self):
        engine, options = browser_module.launch_options(
            browser="chrome", args=["--lang=en-GB", "--disable-background-timer-throttling"]
        )

        self.assertEqual(engine, "chromium")
        self.assertEqual(
            options["args"],
            [
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=CalculateNativeWinOcclusion",
                "--lang=en-GB",
            ],
        )

    def test_firefox_is_spared_the_chromium_switches(self):
        _, options = browser_module.launch_options(browser="firefox")

        self.assertNotIn("args", options)

    def test_launch_runs_firefox_on_its_own_driver(self):
        playwright = FakePlaywright()
        starter = AsyncMock(return_value="firefox-browser")

        with patch.object(browser_module, "_launch_on_own_driver", starter):
            result = asyncio.run(
                browser_module.launch(playwright, browser="firefox", args=["--kiosk"])
            )

        self.assertEqual(result, "firefox-browser")
        starter.assert_awaited_once_with(False, {"headless": True, "args": ["--kiosk"]})
        playwright.firefox.launch.assert_not_awaited()
        playwright.chromium.launch.assert_not_awaited()


class PersistentProfileTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        browser_module.set_profile_root(self.folder.name)
        browser_module.set_profile_mode(True)

    def tearDown(self):
        browser_module.set_profile_mode(None)
        browser_module.set_profile_root(None)
        browser_module.set_default_browser(None)
        os.environ.pop("SAU_BROWSER", None)

    def test_profiles_are_separated_per_browser_and_account(self):
        chrome = browser_module.profile_directory("cookies/youtube_main.json")
        browser_module.set_default_browser("firefox")
        firefox = browser_module.profile_directory("cookies/youtube_main.json")

        self.assertEqual(chrome.relative_to(self.folder.name), Path("chrome") / "youtube_main")
        self.assertEqual(firefox.relative_to(self.folder.name), Path("firefox") / "youtube_main")

    def test_open_session_hands_the_persistent_context_back_as_browser(self):
        playwright = FakePlaywright()

        browser, context = asyncio.run(
            browser_module.open_session(playwright, "cookies/instagram_creator.json", headless=True)
        )

        self.assertIs(browser, context)
        self.assertEqual(context, "profile-context")
        playwright.chromium.launch.assert_not_awaited()
        _, options = playwright.chromium.launch_persistent_context.await_args
        self.assertTrue(options["user_data_dir"].endswith(os.path.join("chrome", "instagram_creator")))

    def test_cookie_files_are_used_when_profiles_are_off(self):
        browser_module.set_profile_mode(False)
        playwright = FakePlaywright()

        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "account.json"
            state.write_text("{}", encoding="utf-8")
            browser, context = asyncio.run(browser_module.open_session(playwright, state, headless=True))

        self.assertEqual(context, "cookie-context")
        playwright.chromium.browser.new_context.assert_awaited_once_with(storage_state=str(state))

    def test_session_available_needs_a_cookie_file_or_a_filled_profile(self):
        account = "cookies/facebook_main.json"
        self.assertFalse(browser_module.session_available(account))

        directory = browser_module.profile_directory(account)
        directory.mkdir(parents=True)
        self.assertFalse(browser_module.session_available(account))

        (directory / "Default").mkdir()
        self.assertTrue(browser_module.session_available(account))

    def test_cli_exposes_the_profile_flags(self):
        import sau_cli

        args = sau_cli.build_parser().parse_args(
            ["youtube", "login", "--account", "main", "--profile", "--profile-dir", "D:/profiles"]
        )

        self.assertTrue(args.profile)
        self.assertEqual(args.profile_dir, "D:/profiles")


if __name__ == "__main__":
    unittest.main()
