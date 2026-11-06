"""TikTok localizes the audience labels, and the choice must be proven before posting."""
import unittest

from uploader.tk_uploader.main_chrome import (
    normalize_visibility,
    pick_visibility_option,
)

GERMAN = ["Alle", "Freund*innen\nFollower*innen, denen du ebenfalls folgst", "Nur du"]
# The labels TikTok actually renders in the English UI ("Only you", not "Only me").
ENGLISH = ["Everyone", "Friends\nFollowers you follow back", "Only you"]


class NormalizeVisibilityTests(unittest.TestCase):
    def test_known_values(self):
        for value in ("public", "friends", "private"):
            self.assertEqual(normalize_visibility(value), value)

    def test_case_and_default(self):
        self.assertEqual(normalize_visibility("PRIVATE"), "private")
        self.assertEqual(normalize_visibility(None), "public")

    def test_unknown_value_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_visibility("unlisted")


class PickVisibilityOptionTests(unittest.TestCase):
    def test_private_german(self):
        self.assertEqual(pick_visibility_option(GERMAN, "private"), "Nur du")

    def test_private_english(self):
        self.assertEqual(pick_visibility_option(ENGLISH, "private"), "Only you")

    def test_private_english_legacy_label(self):
        self.assertEqual(
            pick_visibility_option(["Everyone", "Friends", "Only me"], "private"), "Only me")

    def test_public_is_never_confused_with_private(self):
        self.assertEqual(pick_visibility_option(GERMAN, "public"), "Alle")

    def test_friends_matches_multiline_label(self):
        chosen = pick_visibility_option(GERMAN, "friends")
        self.assertEqual(chosen.splitlines()[0], "Freund*innen")

    def test_missing_option_refuses_to_post(self):
        with self.assertRaises(RuntimeError) as caught:
            pick_visibility_option(["Alle"], "private")
        self.assertIn("refusing to post", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
