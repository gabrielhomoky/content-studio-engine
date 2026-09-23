import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401
import media


class PostIdTest(unittest.TestCase):
    def test_accepts_shortcodes(self):
        self.assertEqual(media.safe_post_id("DbTX3qGDQ9e"), "DbTX3qGDQ9e")
        self.assertEqual(media.safe_post_id("a_b-c.d"), "a_b-c.d")

    def test_rejects_path_tricks(self):
        for bad in ["../etc", "a/b", "..", ".", "", None, "a\b", "x" * 121, "id with space"]:
            with self.assertRaises(ValueError, msg=repr(bad)):
                media.safe_post_id(bad)

    def test_process_post_refuses_unsafe_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                media.process_post({"id": "../../x", "type": "image"}, Path(tmp), upload_media=False)

    def test_main_skips_unsafe_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            picks = Path(tmp) / "picks.json"
            picks.write_text('[{"id": "../evil", "type": "image"}]', encoding="utf-8")
            code = media.main(["all", str(picks), "--out", str(Path(tmp) / "out"), "--no-upload"])
            self.assertEqual(code, 0)
            self.assertFalse((Path(tmp) / "evil").exists())


class TranscriptTest(unittest.TestCase):
    def test_short_or_hallucinated_is_no_speech(self):
        self.assertIsNone(media.clean_transcript("Thank you. Thank you."))
        self.assertIsNone(media.clean_transcript(""))
        self.assertIsNone(media.clean_transcript(None))
        self.assertIsNone(media.clean_transcript("Thank you. Thank you. Thank you. Thank you. Thank you."))
        self.assertIsNone(media.clean_transcript("Дякую за перегляд! Дякую за перегляд! Дякую!"))

    def test_real_speech_is_kept(self):
        text = "My favourite projects almost always start with something that looks like a problem."
        self.assertEqual(media.clean_transcript(text), text)


if __name__ == "__main__":
    unittest.main()
