import json
import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401
import normalize

REEL = {"shortCode": "ABC123", "ownerUsername": "Studio.X", "type": "Video",
        "productType": "clips", "likesCount": 1200, "commentsCount": 45,
        "videoPlayCount": 90000, "timestamp": "2026-09-01T10:00:00.000Z",
        "caption": "  The one colour rule  ",
        "displayUrl": "https://scontent.cdninstagram.com/t.jpg",
        "videoUrl": "https://scontent.cdninstagram.com/v.mp4", "isPinned": False,
        "musicInfo": {"artist_name": "Artist", "song_name": "Song"}}
CAROUSEL = {"url": "https://www.instagram.com/p/XYZ789/", "owner": {"username": "other"},
            "type": "Sidecar", "likesCount": "300", "comments": [{"text": "hi"}],
            "childPosts": [{"displayUrl": "https://x.fbcdn.net/1.jpg"},
                           {"displayUrl": "https://x.fbcdn.net/2.jpg"},
                           {"displayUrl": "https://x.fbcdn.net/1.jpg"}]}


class PostTest(unittest.TestCase):
    def test_reel(self):
        p = normalize.normalize_post(REEL)
        self.assertEqual(p["id"], "ABC123")
        self.assertEqual(p["handle"], "studio.x")
        self.assertEqual(p["type"], "reel")
        self.assertEqual(p["caption"], "The one colour rule")
        self.assertEqual(p["views"], 90000)
        self.assertEqual(p["music"], "Artist - Song")
        self.assertEqual(p["url"], "https://www.instagram.com/p/ABC123/")

    def test_carousel_shortcode_from_url_and_comment_list(self):
        p = normalize.normalize_post(CAROUSEL)
        self.assertEqual(p["id"], "XYZ789")
        self.assertEqual(p["type"], "carousel")
        self.assertEqual(p["likes"], 300)
        self.assertIsNone(p["comments"])  # a sample list is not the count
        self.assertEqual(len(p["slide_urls"]), 2)

    def test_skips_errors_duplicates_and_unidentifiable(self):
        items = [REEL, dict(REEL), {"error": "not found"}, {"caption": "no id"}, "junk"]
        self.assertEqual(len(normalize.normalize_posts(items)), 1)

    def test_image_and_strip(self):
        p = normalize.normalize_post({"shortCode": "I1", "username": "a", "type": "Image",
                                      "displayUrl": "u"})
        self.assertEqual(p["type"], "image")
        self.assertNotIn("video_url", normalize.strip_transient(p))

    def test_reel_url_shortcode(self):
        p = normalize.normalize_post({"inputUrl": "https://www.instagram.com/reel/R1x/",
                                      "username": "a", "videoUrl": "v"})
        self.assertEqual(p["id"], "R1x")
        self.assertEqual(p["type"], "reel")

    def test_to_int(self):
        self.assertEqual(normalize.to_int("12.0"), 12)
        self.assertIsNone(normalize.to_int(True))
        self.assertIsNone(normalize.to_int("x"))


class ProfileTest(unittest.TestCase):
    def test_profile(self):
        a = normalize.normalize_profile({"username": "@Studio", "fullName": "S",
                                         "followersCount": 10, "biography": "b",
                                         "profilePicUrlHD": "pic"}, "own")
        self.assertEqual(a["handle"], "studio")
        self.assertEqual(a["role"], "own")
        self.assertEqual(a["followers"], 10)
        self.assertEqual(a["avatar_url"], "pic")
        self.assertIsNone(normalize.normalize_profile({"fullName": "no handle"}))


class CliTest(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "raw.json")
            src.write_text(json.dumps({"items": [REEL, CAROUSEL]}))
            out = Path(tmp, "out.json")
            self.assertEqual(normalize.main(["posts", str(src), str(out), "--upsert-ready"]), 0)
            data = json.loads(out.read_text())
            self.assertEqual(len(data), 2)
            self.assertNotIn("slide_urls", data[0])
            self.assertEqual(normalize.main(["profile", str(src), str(out)]), 0)
            src.write_text("42")
            self.assertEqual(normalize.main(["posts", str(src), str(out)]), 2)


if __name__ == "__main__":
    unittest.main()
