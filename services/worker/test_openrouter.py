import io
import json
import logging
import unittest
import urllib.error
from http.client import HTTPMessage
from unittest import mock

from worker import OPENROUTER_URL, SYSTEM_PROMPT, reply_for_history, request_reply

FAKE_KEY = "test-key"
MODEL = "openai/gpt-4o-mini"
FALLBACK = "Модель сейчас не ответила. Попробуй ещё раз."


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class OpenRouterTest(unittest.TestCase):
    def setUp(self):
        self.logs = io.StringIO()
        self.handler = logging.StreamHandler(self.logs)
        self.handler.setLevel(logging.DEBUG)
        self.logger = logging.getLogger("worker")
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)
        self.previous_propagate = self.logger.propagate
        self.logger.propagate = False

    def tearDown(self):
        self.logger.removeHandler(self.handler)
        self.logger.propagate = self.previous_propagate

    def test_url_key_header_and_body(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            captured["timeout"] = timeout
            return FakeResponse(
                {"choices": [{"message": {"role": "assistant", "content": "Привет"}}]}
            )

        history = [{"role": "user", "content": "как дела"}]
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            text = request_reply(history, FAKE_KEY, MODEL)

        req = captured["req"]
        self.assertEqual(text, "Привет")
        self.assertEqual(captured["timeout"], 60)
        self.assertEqual(req.full_url, OPENROUTER_URL)
        self.assertEqual(req.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(req.get_method(), "POST")

        headers = {name.lower(): value for name, value in req.header_items()}
        self.assertEqual(headers["authorization"], "Bearer %s" % FAKE_KEY)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(headers["http-referer"], "https://localhost/bvs-chat")
        self.assertEqual(headers["x-title"], "bvs-chat")
        for name, value in req.header_items():
            if name.lower() != "authorization":
                self.assertNotIn(FAKE_KEY, value)

        body_text = req.data.decode("utf-8")
        self.assertNotIn(FAKE_KEY, body_text)
        body = json.loads(body_text)
        self.assertEqual(set(body), {"model", "messages"})
        self.assertEqual(body["model"], MODEL)
        self.assertEqual(body["messages"][0], {"role": "system", "content": SYSTEM_PROMPT})
        self.assertEqual(body["messages"][1], {"role": "user", "content": "как дела"})
        self.assertNotIn(FAKE_KEY, self.logs.getvalue())

    def test_long_reply_is_truncated(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(
                {"choices": [{"message": {"content": "я" * 4500}}]}
            )

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            text = request_reply(
                [{"role": "user", "content": "длинный"}],
                FAKE_KEY,
                MODEL,
            )
        self.assertEqual(text, "я" * 4000)
        self.assertNotIn(FAKE_KEY, self.logs.getvalue())

    def test_empty_reply_becomes_retry_phrase(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse({"choices": [{"message": {"content": "   "}}]})

        history = [{"role": "user", "content": "вопрос"}]
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(RuntimeError) as caught:
                request_reply(history, FAKE_KEY, MODEL)
            self.assertEqual(str(caught.exception), "openrouter code=empty")
            self.assertNotIn(FAKE_KEY, str(caught.exception))
            text = reply_for_history(history, FAKE_KEY, MODEL)

        self.assertEqual(text, FALLBACK)
        written = self.logs.getvalue()
        self.assertIn("code=empty", written)
        self.assertNotIn(FAKE_KEY, written)

    def test_http_error_hides_key_and_becomes_retry_phrase(self):
        def fake_urlopen(req, timeout=None):
            headers = HTTPMessage()
            headers["Authorization"] = "Bearer %s" % FAKE_KEY
            raise urllib.error.HTTPError(
                req.full_url,
                503,
                "unavailable",
                headers,
                io.BytesIO(b'{"error":"test-key","authorization":"Bearer test-key"}'),
            )

        history = [{"role": "user", "content": "вопрос"}]
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(RuntimeError) as caught:
                request_reply(history, FAKE_KEY, MODEL)
            self.assertEqual(str(caught.exception), "openrouter code=503")
            self.assertNotIn(FAKE_KEY, str(caught.exception))
            text = reply_for_history(history, FAKE_KEY, MODEL)

        self.assertEqual(text, FALLBACK)
        written = self.logs.getvalue()
        self.assertIn("code=503", written)
        self.assertNotIn(FAKE_KEY, written)
        self.assertNotIn("Authorization", written)


if __name__ == "__main__":
    unittest.main()
