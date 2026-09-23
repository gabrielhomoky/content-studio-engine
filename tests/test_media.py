import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import _path  # noqa: F401
import media


class CommandTest(unittest.TestCase):
    def test_keyframe_times(self):
        self.assertEqual(media.keyframe_times(None), [0.5])
        self.assertEqual(media.keyframe_times(0.3), [0.5])
        self.assertEqual(media.keyframe_times(10), [0.5, 3.5, 6.5, 9.5])
        self.assertEqual(len(media.keyframe_times(120)), media.MAX_FRAMES)

    def test_commands(self):
        self.assertEqual(media.keyframe_cmd("v.mp4", 0.5, "f.jpg"),
                         ["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", "v.mp4",
                          "-frames:v", "1", "-vf", "scale=720:-2", "-q:v", "4", "f.jpg"])
        audio = media.audio_cmd("v.mp4", "a.mp3")
        self.assertIn("-ac", audio)
        self.assertEqual(audio[audio.index("-ar") + 1], "16000")
        self.assertEqual(media.probe_cmd("v.mp4")[0], "ffprobe")

    def test_video_duration_handles_failure(self):
        with mock.patch("media.run", side_effect=subprocess.CalledProcessError(1, "x")):
            self.assertIsNone(media.video_duration("v.mp4"))
        with mock.patch("media.run", return_value=mock.Mock(stdout="12.5\n")):
            self.assertEqual(media.video_duration("v.mp4"), 12.5)


def fake_download(path, target, query=None, **kw):
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_bytes(b"data")
    return 4


class ProcessTest(unittest.TestCase):
    def test_carousel_slides_and_upload(self):
        post = {"id": "C1", "type": "carousel", "slide_urls": ["u1", "u2", "u3"]}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch("media.ce.call_bytes_out", side_effect=fake_download), \
             mock.patch("media.ce.call_bytes_in", return_value={}) as up:
            m = media.process_post(post, Path(tmp), max_slides=2)
            self.assertEqual(len(m["files"]), 2)
            self.assertEqual(m["media_keys"], ["slides/C1/01.jpg", "slides/C1/02.jpg"])
            self.assertEqual(up.call_count, 2)
            self.assertTrue(Path(tmp, "C1", "manifest.json").exists())

    def test_reel_without_ffmpeg_falls_back_to_thumbnail(self):
        post = {"id": "R1", "type": "reel", "thumb_url": "t", "video_url": "v"}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch("media.have_ffmpeg", return_value=False), \
             mock.patch("media.ce.call_bytes_out", side_effect=fake_download):
            m = media.process_post(post, Path(tmp), upload_media=False)
            self.assertEqual(len(m["files"]), 1)
            self.assertTrue(any("ffmpeg" in e for e in m["errors"]))

    def test_reel_full_path(self):
        post = {"id": "R2", "type": "reel", "video_url": "v"}

        def fake_frames(video, outdir):
            f = outdir / "frame_01.jpg"
            f.write_bytes(b"j")
            return [f]

        def fake_audio(video, outdir):
            a = outdir / "audio.mp3"
            a.write_bytes(b"a")
            return a
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch("media.have_ffmpeg", return_value=True), \
             mock.patch("media.ce.call_bytes_out", side_effect=fake_download), \
             mock.patch("media.extract_frames", side_effect=fake_frames), \
             mock.patch("media.extract_audio", side_effect=fake_audio), \
             mock.patch("media.ce.call_bytes_in",
                        return_value={"text": "hello", "language": "en"}):
            m = media.process_post(post, Path(tmp), lang="en")
            self.assertEqual(m["transcript"], "hello")
            self.assertEqual(m["media_keys"], ["frames/R2/01.jpg"])
            self.assertFalse(Path(tmp, "R2", "video.mp4").exists())

    def test_download_errors_are_recorded(self):
        post = {"id": "I1", "type": "image", "thumb_url": "t"}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch("media.ce.call_bytes_out", side_effect=media.ce.ApiError("403")):
            m = media.process_post(post, Path(tmp))
            self.assertEqual(m["files"], [])
            self.assertIn("slide 1: 403", m["errors"])

    def test_cli(self):
        posts = [{"id": "I1", "type": "image", "thumb_url": "t"}]
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch("media.ce.call_bytes_out", side_effect=fake_download), \
             mock.patch("sys.stdout", new_callable=io.StringIO):
            src = Path(tmp, "p.json")
            src.write_text(json.dumps(posts))
            out = str(Path(tmp, "m"))
            self.assertEqual(media.main(["all", str(src), "--out", out, "--no-upload"]), 0)
            self.assertEqual(media.main(["pick", str(src), "--id", "I1", "--out", out,
                                         "--no-upload"]), 0)
            with mock.patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(media.main(["pick", str(src), "--id", "nope", "--out", out]), 2)


if __name__ == "__main__":
    unittest.main()
