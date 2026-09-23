import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tests import _path  # noqa: F401
import rank


def post(pid, handle, likes, **kw):
    return {"id": pid, "handle": handle, "likes": likes, "type": kw.pop("type", "reel"), **kw}


class AnnotateTest(unittest.TestCase):
    def test_breakout_uses_median_excluding_pinned(self):
        posts = [post(f"a{i}", "a", 100) for i in range(6)]
        posts.append(post("hit", "a", 1000))
        posts.append(post("pin", "a", 50000, pinned=True))
        out = {p["id"]: p for p in rank.annotate(posts)}
        self.assertEqual(out["hit"]["median_likes"], 100.0)
        self.assertEqual(out["hit"]["breakout"], 10.0)
        self.assertEqual(out["hit"]["confidence"], "high")
        self.assertEqual(out["a0"]["confidence"], "medium")

    def test_missing_likes_never_invented(self):
        out = {p["id"]: p for p in rank.annotate([post("x", "b", None), post("y", "b", 10)])}
        self.assertIsNone(out["x"]["breakout"])
        self.assertEqual(out["x"]["confidence"], "none")
        self.assertEqual(out["y"]["confidence"], "low")  # sample < 6

    def test_zero_median_gives_none(self):
        out = rank.annotate([post("z", "c", 0), post("w", "c", 0)])
        self.assertTrue(all(p["breakout"] is None for p in out))


class SelectTest(unittest.TestCase):
    def test_top_per_handle_and_pool(self):
        posts = [post(f"a{i}", "a", 100 + i) for i in range(8)]
        posts += [post(f"b{i}", "b", 10) for i in range(7)] + [post("bhit", "b", 500)]
        picks = rank.select(posts, top_per_handle=2, pool=3)
        self.assertEqual(len(picks), 3)
        self.assertEqual(picks[0]["id"], "bhit")
        self.assertEqual([p["rank"] for p in picks], [1, 2, 3])
        self.assertTrue(all(p["is_pick"] for p in picks))

    def test_pinned_excluded_unless_included(self):
        posts = [post(f"a{i}", "a", 100) for i in range(6)] + [post("pin", "a", 9999, pinned=True)]
        self.assertNotIn("pin", [p["id"] for p in rank.select(posts)])
        self.assertIn("pin", [p["id"] for p in rank.select(posts, include_pinned=True)])


class StatsTest(unittest.TestCase):
    def test_handle_stats(self):
        items = [
            post("1", "a", 100, comments=10, views=1000, posted_at="2026-09-01T00:00:00Z"),
            post("2", "a", 200, comments=20, type="carousel", posted_at="2026-09-08T00:00:00Z"),
            post("3", "a", 300, comments=30, posted_at="2026-09-15T00:00:00.000Z"),
        ]
        s = rank.stats(items, {"a": 1000})["a"]
        self.assertEqual(s["median_likes"], 200.0)
        self.assertEqual(s["median_comments"], 20.0)
        self.assertEqual(s["median_views"], 1000.0)
        self.assertEqual(s["reel_share"], 0.67)
        self.assertEqual(s["carousel_share"], 0.33)
        self.assertEqual(s["posts_per_week"], 1.0)
        self.assertEqual(s["er_pct"], 22.0)
        self.assertEqual(s["last_post_at"], "2026-09-15T00:00:00Z")

    def test_stats_without_data(self):
        s = rank.handle_stats([post("1", "a", None)])
        self.assertIsNone(s["median_likes"])
        self.assertIsNone(s["posts_per_week"])
        self.assertIsNone(s["er_pct"])


class WindowAndCliTest(unittest.TestCase):
    def test_window_filter(self):
        now = datetime(2026, 9, 23, tzinfo=timezone.utc)
        posts = [post("old", "a", 1, posted_at="2025-01-01T00:00:00Z"),
                 post("new", "a", 1, posted_at="2026-09-20T00:00:00Z"),
                 post("nodate", "a", 1)]
        self.assertEqual([p["id"] for p in rank.within_window(posts, 90, now)], ["new", "nodate"])
        self.assertEqual(len(rank.within_window(posts, 0)), 3)

    def test_parse_time_variants(self):
        self.assertIsNotNone(rank.parse_time(1700000000))
        self.assertIsNone(rank.parse_time("not a date"))
        self.assertIsNotNone(rank.parse_time("2026-09-01T10:00:00"))

    def test_cli_modes(self):
        posts = [post(f"a{i}", "a", 100 + i, posted_at=f"2026-09-{i + 1:02d}T00:00:00Z")
                 for i in range(7)]
        with tempfile.TemporaryDirectory() as tmp:
            src, acc = Path(tmp, "p.json"), Path(tmp, "a.json")
            src.write_text(json.dumps(posts))
            acc.write_text(json.dumps([{"handle": "a", "followers": 5000}]))
            for mode in ("annotate", "select", "stats"):
                out = Path(tmp, f"{mode}.json")
                extra = ["--accounts", str(acc)] if mode == "stats" else []
                self.assertEqual(rank.main([mode, str(src), str(out)] + extra), 0)
                self.assertTrue(json.loads(out.read_text()))
            self.assertEqual(rank.main(["select", str(Path(tmp, "missing.json")), str(out)]), 2)


if __name__ == "__main__":
    unittest.main()
