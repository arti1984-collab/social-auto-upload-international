"""Studio's progress label is localized, so completion must not depend on English text."""
import unittest

from uploader.youtube_uploader.main import _upload_finished


class UploadFinishedTests(unittest.TestCase):
    def test_german_checks_done(self):
        self.assertTrue(_upload_finished("Vorabprüfung abgeschlossen. Keine Probleme gefunden"))

    def test_german_upload_done_but_processing_pending(self):
        self.assertFalse(_upload_finished("Upload abgeschlossen ... Verarbeitung steht aus"))

    def test_german_checks_running(self):
        self.assertFalse(_upload_finished("Wird geprüft: 2 % ... Noch 5 Minuten"))

    def test_german_hd_processing(self):
        self.assertFalse(_upload_finished("Verarbeitung bis zu HD ... Noch 3 Minuten"))

    def test_english_done(self):
        self.assertTrue(_upload_finished("Checks complete. No issues found."))

    def test_empty_label(self):
        self.assertFalse(_upload_finished(""))


if __name__ == "__main__":
    unittest.main()
