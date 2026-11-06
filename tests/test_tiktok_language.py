"""Only the video flow needs the English UI; photo posts are matched by label."""
import unittest

from uploader.tk_uploader.main_chrome import needs_language_switch


class LanguageSwitchTests(unittest.TestCase):
    def test_photo_post_skips_the_switch(self):
        self.assertFalse(needs_language_switch(True))

    def test_video_post_needs_the_switch(self):
        self.assertTrue(needs_language_switch(False))


if __name__ == "__main__":
    unittest.main()
