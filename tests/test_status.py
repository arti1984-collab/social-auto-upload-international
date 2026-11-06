"""The status command merges cookie files and profiles into one overview."""
import asyncio
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sau_cli
from utils import browser as browser_module
from sau_commands import status as status_module


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.cookies = Path(self.folder.name) / "cookies"
        self.cookies.mkdir()
        browser_module.set_profile_root(Path(self.folder.name) / "profiles")
        patcher = patch(
            "sau_commands.status.cookie_directory", lambda: self.cookies
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        browser_module.set_profile_mode(None)
        browser_module.set_profile_root(None)
        browser_module.set_default_browser(None)
        browser_module.set_default_profile(None)

    def _profile(self, browser, account):
        directory = browser_module.profile_root() / browser / account
        (directory / "Default").mkdir(parents=True)
        (directory / "Default" / "Cookies").write_bytes(b"x")
        return directory

    def _run(self, *extra):
        args = sau_cli.build_parser().parse_args(["status", *extra])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = asyncio.run(sau_cli.dispatch(args))
        return code, out.getvalue()

    def test_merges_cookie_files_and_profiles(self):
        (self.cookies / "youtube_main.json").write_text("{}", encoding="utf-8")
        self._profile("chrome", "youtube_main")
        self._profile("firefox", "instagram_creator")

        rows = {
            (row["platform"], row["account"]): row
            for row in status_module.collect_accounts()
        }

        self.assertEqual(
            set(rows), {("youtube", "main"), ("instagram", "creator")}
        )
        self.assertIsNotNone(rows[("youtube", "main")]["cookie"])
        self.assertEqual(set(rows[("youtube", "main")]["profiles"]), {"chrome"})
        self.assertIsNone(rows[("instagram", "creator")]["cookie"])
        self.assertIsNotNone(rows[("instagram", "creator")]["last_used"])

    def test_cli_marks_the_default_profile(self):
        (self.cookies / "youtube_main.json").write_text("{}", encoding="utf-8")
        self._profile("chrome", "youtube_main")
        self._profile("firefox", "youtube_main")
        browser_module.set_default_profile("youtube_main")

        code, output = self._run()

        self.assertEqual(code, 0)
        self.assertIn("chrome*", output)
        self.assertIn("firefox", output)
        # Only the configured browser carries the marker, not every browser with that profile.
        self.assertNotIn("firefox*", output)
        self.assertIn("chrome/youtube_main", output)
        self.assertIn("yes", output)

    def test_account_without_cookie_shows_a_dash(self):
        self._profile("firefox", "instagram_creator")

        _, output = self._run()

        self.assertIn("instagram", output)
        self.assertIn("creator", output)
        row = next(line for line in output.splitlines() if "instagram" in line)
        self.assertIn("-", row)

    def test_pending_files_are_ignored_and_unknown_platforms_are_listed(self):
        (self.cookies / "youtube_main.abc.pending.json").write_text("{}", encoding="utf-8")
        (self.cookies / "tiktok_demo.json").write_text("{}", encoding="utf-8")

        _, output = self._run()

        self.assertNotIn("pending", output)
        self.assertIn("other", output)
        self.assertIn("tiktok_demo", output)

    def test_empty_state_explains_the_next_step(self):
        code, output = self._run()

        self.assertEqual(code, 0)
        self.assertIn("No accounts yet", output)

    def test_without_verify_no_browser_is_started(self):
        (self.cookies / "youtube_main.json").write_text("{}", encoding="utf-8")
        called = []

        def fake_checker(platform):
            called.append(platform)
            return None

        with patch("sau_commands.status.checker", fake_checker):
            _, output = self._run()

        self.assertEqual(called, [])
        self.assertNotIn("SESSION", output)

    def test_verify_reports_valid_invalid_and_errors_per_row(self):
        (self.cookies / "youtube_main.json").write_text("{}", encoding="utf-8")
        (self.cookies / "instagram_creator.json").write_text("{}", encoding="utf-8")
        seen_profile_mode = []

        async def fake_youtube(account):
            seen_profile_mode.append(browser_module.profile_mode())
            return True

        async def fake_instagram(account):
            raise RuntimeError("Instagram is not signed in")

        checks = {"youtube": fake_youtube, "instagram": fake_instagram}
        with patch("sau_commands.status.checker", lambda platform: checks.get(platform)):
            _, output = self._run("--verify")

        youtube_row = next(line for line in output.splitlines() if line.startswith("youtube"))
        instagram_row = next(line for line in output.splitlines() if line.startswith("instagram"))
        self.assertTrue(youtube_row.rstrip().endswith("valid"))
        self.assertTrue(instagram_row.rstrip().endswith("error"))
        # Expired sessions raise, so the reason belongs under the table instead of an abort.
        self.assertIn("Instagram is not signed in", output)
        # Profile-only sessions must be visible to the platform check.
        self.assertEqual(seen_profile_mode, [True])

    def test_verify_marks_profiles_without_a_check_as_unsupported(self):
        (self.cookies / "tiktok_demo.json").write_text("{}", encoding="utf-8")

        _, output = self._run("--verify")

        row = next(line for line in output.splitlines() if "tiktok_demo" in line)
        self.assertTrue(row.rstrip().endswith("-"))

    def test_verify_runs_checks_in_parallel_up_to_the_job_limit(self):
        for stem in ("youtube_a", "youtube_b", "youtube_c", "youtube_d"):
            (self.cookies / f"{stem}.json").write_text("{}", encoding="utf-8")
        active = {"now": 0, "peak": 0}

        async def fake_check(account):
            active["now"] += 1
            active["peak"] = max(active["peak"], active["now"])
            await asyncio.sleep(0.02)
            active["now"] -= 1
            return True

        with patch("sau_commands.status.checker", lambda platform: fake_check):
            _, output = self._run("--verify", "--verify-jobs", "2")

        self.assertEqual(active["peak"], 2)
        # Every row still gets its own result, in table order.
        self.assertEqual(output.count("valid"), 4)
        rows = [line.split()[1] for line in output.splitlines() if line.startswith("youtube")]
        self.assertEqual(rows, ["a", "b", "c", "d"])

    def test_verify_jobs_one_stays_sequential(self):
        for stem in ("youtube_a", "youtube_b"):
            (self.cookies / f"{stem}.json").write_text("{}", encoding="utf-8")
        active = {"now": 0, "peak": 0}

        async def fake_check(account):
            active["now"] += 1
            active["peak"] = max(active["peak"], active["now"])
            await asyncio.sleep(0.01)
            active["now"] -= 1
            return True

        with patch("sau_commands.status.checker", lambda platform: fake_check):
            self._run("--verify", "--verify-jobs", "1")

        self.assertEqual(active["peak"], 1)

    def test_verify_jobs_rejects_values_outside_the_range(self):
        for value in ("0", "17"):
            with self.assertRaises(SystemExit):
                sau_cli.build_parser().parse_args(["status", "--verify-jobs", value])

    def test_verify_restores_the_configured_profile_mode(self):
        (self.cookies / "youtube_main.json").write_text("{}", encoding="utf-8")

        async def fake_check(account):
            return False

        with patch("sau_commands.status.checker", lambda platform: fake_check):
            self._run("--verify")

        self.assertFalse(browser_module.profile_mode())


if __name__ == "__main__":
    unittest.main()
