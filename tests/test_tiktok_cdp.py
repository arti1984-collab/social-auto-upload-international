"""Attaching to a running browser must never close the user's own session."""
import unittest

from uploader.tk_uploader.main_chrome import TiktokVideo


class CdpAttachTests(unittest.TestCase):
    def test_cdp_url_is_kept(self):
        app = TiktokVideo("Titel", "videos/tiktok-textvideo.mp4", [], 0, "konto.json",
                          cdp_url="http://127.0.0.1:9222")
        self.assertEqual(app.cdp_url, "http://127.0.0.1:9222")
        self.assertFalse(app.photo_post)

    def test_without_cdp_url_the_uploader_launches_a_browser(self):
        app = TiktokVideo("Titel", "videos/tiktok-textvideo.mp4", [], 0, "konto.json")
        self.assertIsNone(app.cdp_url)


if __name__ == "__main__":
    unittest.main()
