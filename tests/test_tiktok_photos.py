"""TikTok photo posts: 1-35 images, and the uploader must tell photos from videos."""
import tempfile
import unittest
from pathlib import Path

from uploader.tk_uploader.main_chrome import (
    MAX_PHOTOS,
    is_photo_post,
    validate_photo_files,
)


class PhotoDetectionTests(unittest.TestCase):
    def test_single_image_is_a_photo_post(self):
        self.assertTrue(is_photo_post("a.png"))

    def test_image_list_is_a_photo_post(self):
        self.assertTrue(is_photo_post(["a.png", "b.jpg", "c.webp"]))

    def test_video_is_not_a_photo_post(self):
        self.assertFalse(is_photo_post("clip.mp4"))

    def test_mixed_list_is_not_a_photo_post(self):
        self.assertFalse(is_photo_post(["a.png", "clip.mp4"]))


class PhotoValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _image(self, name):
        path = self.root / name
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        return path

    def test_valid_images_are_returned_as_resolved_paths(self):
        paths = validate_photo_files([self._image("a.png"), self._image("b.jpg")])
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(path.is_absolute() for path in paths))

    def test_empty_list_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_photo_files([])

    def test_too_many_images_are_rejected(self):
        images = [str(self.root / f"img{index}.png") for index in range(MAX_PHOTOS + 1)]
        with self.assertRaises(ValueError) as caught:
            validate_photo_files(images)
        self.assertIn(str(MAX_PHOTOS), str(caught.exception))

    def test_unsupported_format_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_photo_files([self._image("clip.mp4")])

    def test_missing_file_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            validate_photo_files([self.root / "nope.png"])


if __name__ == "__main__":
    unittest.main()
