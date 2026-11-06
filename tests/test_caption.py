import unittest

import sau_cli
from utils.caption import (
    PLATFORM_LIMITS,
    apply_caption,
    build,
    merge_tags,
    normalize_tag,
)


class CaptionBuildTests(unittest.TestCase):
    def test_hashtags_come_from_title_and_notes(self):
        result = build("instagram", "Kaffee richtig brühen", "Wassertemperatur und Mahlgrad")
        self.assertIn("kaffee", result["tags"])
        self.assertIn("bruehen", result["tags"])
        self.assertTrue(all(tag.startswith("#") for tag in result["hashtags"]))

    def test_normalize_transliterates_umlauts(self):
        self.assertEqual(normalize_tag("Prüfung"), "pruefung")
        self.assertEqual(normalize_tag("Straße!"), "strasse")

    def test_notes_are_kept_and_a_call_to_action_is_added(self):
        result = build("facebook", "Titel", "Mein Text", "de")
        self.assertTrue(result["description"].startswith("Mein Text"))
        self.assertIn("kommentieren", result["description"])

    def test_instagram_caption_stays_within_limit(self):
        result = build("instagram", "Titel " * 400, "Notiz " * 200)
        self.assertLessEqual(len(result["caption"]), PLATFORM_LIMITS["instagram"]["caption"])

    def test_youtube_title_is_trimmed_to_its_limit(self):
        result = build("youtube", "W" * 50 + " " + "W" * 80)
        self.assertLessEqual(len(result["title"]), PLATFORM_LIMITS["youtube"]["title"])

    def test_english_wording_differs_from_german(self):
        german = build("tiktok", "Kaffee", "", "de")["description"]
        english = build("tiktok", "Kaffee", "", "en")["description"]
        self.assertNotEqual(german, english)

    def test_unknown_platform_and_language_are_rejected(self):
        with self.assertRaises(ValueError):
            build("myspace", "Titel")
        with self.assertRaises(ValueError):
            build("tiktok", "Titel", "", "fr")


class CaptionMergeTests(unittest.TestCase):
    def test_explicit_text_wins_over_generated_text(self):
        text, tags = apply_caption(
            "tiktok", "Kaffee", "Mein Text", ["kaffee"], auto_desc=True, auto_tags=True
        )
        self.assertEqual(text, "Mein Text")
        self.assertEqual(tags[0], "kaffee")
        self.assertEqual(tags.count("kaffee"), 1)

    def test_missing_text_and_tags_are_filled(self):
        text, tags = apply_caption(
            "facebook", "Kaffee richtig brühen", "", [], auto_desc=True, auto_tags=True
        )
        self.assertTrue(text)
        self.assertIn("kaffee", tags)

    def test_without_flags_nothing_changes(self):
        text, tags = apply_caption("instagram", "Titel", "", [])
        self.assertEqual(text, "")
        self.assertEqual(tags, [])

    def test_merge_drops_duplicates_case_insensitively_and_caps(self):
        self.assertEqual(merge_tags(["Kaffee"], ["kaffee", "bruehen"], 5), ["Kaffee", "bruehen"])
        self.assertEqual(len(merge_tags([], ["a", "b", "c"], 2)), 2)


class CaptionCliTests(unittest.TestCase):
    def test_caption_command_parses_language_and_target(self):
        args = sau_cli.build_parser().parse_args(
            ["caption", "--title", "Titel", "--lang", "en", "--for", "tiktok"]
        )
        self.assertEqual(args.platform, "caption")
        self.assertEqual(args.caption_lang, "en")
        self.assertEqual(args.target, "tiktok")

    def test_upload_commands_accept_the_auto_flags(self):
        for argv in (
            ["youtube", "upload-video", "--account", "main", "--file", __file__, "--title", "T"],
            ["facebook", "upload-note", "--account", "main", "--images", __file__, "--title", "T"],
            [
                "facebook-page",
                "upload-video",
                "--account",
                "main",
                "--file",
                __file__,
                "--title",
                "T",
            ],
            ["instagram", "upload-video", "--account", "main", "--file", __file__, "--title", "T"],
        ):
            args = sau_cli.build_parser().parse_args(argv + ["--auto-desc", "--auto-tags", "--lang", "en"])
            self.assertTrue(args.auto_desc)
            self.assertTrue(args.auto_tags)
            self.assertEqual(args.caption_lang, "en")


if __name__ == "__main__":
    unittest.main()
