import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tests import _path  # noqa: F401
import ce


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def responder(payload, calls):
    def opener(req, timeout=None):
        calls.append((req, timeout))
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        return FakeResp(body)
    return opener


ENV = {"CE_API_URL": "https://studio.example.dev/", "CE_ENGINE_KEY": "k123"}


@mock.patch.dict(os.environ, ENV, clear=False)
class RequestTest(unittest.TestCase):
    def test_headers_and_query(self):
        req = ce.build_request("GET", "/api/engine/jobs", query={"status": "queued", "x": None})
        self.assertEqual(req.full_url, "https://studio.example.dev/api/engine/jobs?status=queued")
        self.assertEqual(req.get_header("Authorization"), "Bearer k123")
        self.assertEqual(req.get_header("User-agent"), ce.USER_AGENT)

    def test_no_key_means_no_auth_header(self):
        with mock.patch.dict(os.environ, {"CE_ENGINE_KEY": ""}):
            req = ce.build_request("GET", "/x")
            self.assertIsNone(req.get_header("Authorization"))

    def test_base_url_validation(self):
        with mock.patch.dict(os.environ, {"CE_API_URL": ""}):
            with self.assertRaises(ce.ApiError):
                ce.base_url()
        with mock.patch.dict(os.environ, {"CE_API_URL": "ftp://x"}):
            with self.assertRaises(ce.ApiError):
                ce.base_url()

    def test_call_json_unwraps_envelope_and_sends_body(self):
        calls = []
        data = ce.call_json("POST", "/api/engine/jobs", payload={"type": "ping"},
                            opener=responder({"ok": True, "data": {"id": "j1"}}, calls))
        self.assertEqual(data, {"id": "j1"})
        req, timeout = calls[0]
        self.assertEqual(json.loads(req.data), {"type": "ping"})
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(timeout, ce.DEFAULT_TIMEOUT)

    def test_ok_false_raises(self):
        with self.assertRaises(ce.ApiError):
            ce.call_json("GET", "/x", opener=responder({"ok": False, "error": "bad"}, []))

    def test_non_json_raises(self):
        with self.assertRaises(ce.ApiError):
            ce.call_json("GET", "/x", opener=responder(b"<html>", []))

    @mock.patch("ce.time.sleep")
    def test_retries_5xx_then_succeeds(self, sleep):
        attempts = []

        def opener(req, timeout=None):
            attempts.append(1)
            if len(attempts) < 3:
                raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO(b"{}"))
            return FakeResp(json.dumps({"ok": True, "data": 1}).encode())
        self.assertEqual(ce.call_json("GET", "/x", opener=opener), 1)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleep.call_count, 2)

    def test_4xx_not_retried_and_message(self):
        attempts = []

        def opener(req, timeout=None):
            attempts.append(1)
            raise urllib.error.HTTPError(req.full_url, 401, "nope", {},
                                         io.BytesIO(b'{"ok":false,"error":"bad key"}'))
        with self.assertRaises(ce.ApiError) as ctx:
            ce.call_json("GET", "/x", opener=opener)
        self.assertIn("401", str(ctx.exception))
        self.assertIn("bad key", str(ctx.exception))
        self.assertEqual(len(attempts), 1)

    @mock.patch("ce.time.sleep")
    def test_network_error_exhausts(self, sleep):
        def opener(req, timeout=None):
            raise urllib.error.URLError("down")
        with self.assertRaises(ce.ApiError):
            ce.call_json("GET", "/x", opener=opener)

    def test_bytes_out_and_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp, "sub", "f.bin")
            size = ce.call_bytes_out("/api/engine/proxy", out, query={"url": "u"},
                                     opener=responder(b"abc", []))
            self.assertEqual(size, 3)
            self.assertEqual(out.read_bytes(), b"abc")
        calls = []
        data = ce.call_bytes_in("PUT", "/m/k", b"x", "image/jpeg",
                                opener=responder({"ok": True, "data": {"key": "k"}}, calls))
        self.assertEqual(data, {"key": "k"})
        self.assertEqual(calls[0][0].get_header("Content-type"), "image/jpeg")


class HelperTest(unittest.TestCase):
    def test_load_json_arg(self):
        self.assertEqual(ce.load_json_arg('{"a":1}'), {"a": 1})
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp, "x.json")
            f.write_text("[1,2]")
            self.assertEqual(ce.load_json_arg(str(f)), [1, 2])
            self.assertEqual(ce.load_json_arg("@" + str(f)), [1, 2])
        with mock.patch("sys.stdin", io.StringIO('{"s":1}')):
            self.assertEqual(ce.load_json_arg("-"), {"s": 1})

    def test_as_items(self):
        self.assertEqual(ce.as_items({"items": [{"a": 1}]}), [{"a": 1}])
        self.assertEqual(ce.as_items([{"a": 1}]), [{"a": 1}])
        self.assertEqual(ce.as_items({"a": 1}), [{"a": 1}])
        with self.assertRaises(ValueError):
            ce.as_items([1])
        with self.assertRaises(ValueError):
            ce.as_items(3)

    def test_filters_and_collection(self):
        self.assertEqual(ce.parse_filters(["status=new", "is_pick=1"]),
                         {"status": "new", "is_pick": "1"})
        with self.assertRaises(ValueError):
            ce.parse_filters(["bad"])
        with self.assertRaises(ValueError):
            ce.check_collection("secrets")


@mock.patch.dict(os.environ, ENV, clear=False)
class CommandTest(unittest.TestCase):
    def run_cli(self, argv, result=None):
        with mock.patch("ce.call_json", return_value=result) as cj, \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = ce.main(argv)
        return code, cj, out.getvalue()

    def test_upsert_batches_of_50(self):
        items = json.dumps([{"id": str(i)} for i in range(120)])
        code, cj, out = self.run_cli(["upsert", "ideas", "--json", items], {"count": 1})
        self.assertEqual(code, 0)
        self.assertEqual(cj.call_count, 3)
        self.assertEqual(json.loads(out)["batches"], 3)
        self.assertEqual(cj.call_args_list[0].args[1], "/api/engine/upsert/ideas")

    def test_job_update_bilingual_summary(self):
        code, cj, _ = self.run_cli(["job-update", "job 1", "--status", "done",
                                    "--summary-uk", "Готово", "--summary-en", "Done"], {})
        self.assertEqual(code, 0)
        self.assertEqual(cj.call_args.args[1], "/api/engine/jobs/job%201")
        self.assertEqual(cj.call_args.kwargs["payload"],
                         {"status": "done", "summary": {"uk": "Готово", "en": "Done"}})

    def test_job_update_rejects_bad_status_and_empty(self):
        self.assertEqual(self.run_cli(["job-update", "j", "--status", "weird"])[0], 2)
        self.assertEqual(self.run_cli(["job-update", "j"])[0], 2)

    def test_other_commands_route(self):
        cases = [
            (["context"], "/api/engine/context"),
            (["jobs"], "/api/engine/jobs"),
            (["job-create", "weekly", "--params", "{}"], "/api/engine/jobs"),
            (["list", "posts", "--filter", "is_pick=1", "--limit", "5"], "/api/engine/list/posts"),
            (["apify", "apify~instagram-post-scraper", "--input", '{"username":["a"]}'],
             "/api/engine/apify"),
        ]
        for argv, path in cases:
            code, cj, _ = self.run_cli(argv, {})
            self.assertEqual(code, 0, argv)
            self.assertEqual(cj.call_args.args[1], path)

    def test_api_error_exit_code_and_out_file(self):
        with mock.patch("ce.call_json", side_effect=ce.ApiError("boom")), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(ce.main(["context"]), 1)
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp, "ctx.json"))
            code, _, out = self.run_cli(["--out", target, "context"], {"brand": {}})
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(Path(target).read_text()), {"brand": {}})
            after = str(Path(tmp, "after.json"))
            code, _, _ = self.run_cli(["jobs", "--out", after], [1])
            self.assertEqual(json.loads(Path(after).read_text()), [1])

    def test_binary_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp, "a.mp3")
            f.write_bytes(b"x")
            with mock.patch("ce.call_bytes_in", return_value={"text": "hi"}) as cb, \
                 mock.patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(ce.main(["transcribe", str(f), "--lang", "en"]), 0)
                self.assertEqual(cb.call_args.kwargs["query"], {"lang": "en"})
                self.assertEqual(ce.main(["media-put", "frames/x/01.jpg", str(f)]), 0)
                self.assertEqual(cb.call_args.args[1], "/api/engine/media/frames/x/01.jpg")
            with mock.patch("ce.call_bytes_out", return_value=5), \
                 mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(ce.main(["proxy-get", "https://a.cdninstagram.com/x",
                                          str(Path(tmp, "o"))]), 0)
                self.assertEqual(json.loads(out.getvalue())["bytes"], 5)


if __name__ == "__main__":
    unittest.main()
