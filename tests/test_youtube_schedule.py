"""A requested YouTube schedule must fail loudly instead of publishing right away."""
import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from sau_commands import youtube


def _request(schedule):
    return youtube.YouTubeVideoUploadRequest(
        account_name="test",
        video_file=Path("videos/demo.mp4"),
        title="Titel",
        description="",
        tags=[],
        schedule=schedule,
    )


class ScheduleGuardTests(unittest.TestCase):
    def test_schedule_is_rejected_before_any_browser_starts(self):
        async def must_not_run(*args, **kwargs):
            raise AssertionError("youtube_setup must not run for a scheduled upload")

        with patch.object(youtube, "youtube_setup", must_not_run):
            with self.assertRaises(RuntimeError) as caught:
                asyncio.run(youtube.upload_youtube_video(_request(1700000000)))

        self.assertIn("not implemented", str(caught.exception))

    def test_immediate_upload_reaches_the_session_check(self):
        async def reached(*args, **kwargs):
            raise AssertionError("session check reached")

        with patch.object(youtube, "youtube_setup", reached):
            with self.assertRaises(AssertionError):
                asyncio.run(youtube.upload_youtube_video(_request(0)))


if __name__ == "__main__":
    unittest.main()
