from __future__ import annotations

import json
import unittest
import urllib.error
from unittest import mock

from starter.conversation_llm import DeepSeekConversationLLM


VALID_PAYLOAD = json.dumps(
    {
        "choices": [{"message": {"content": '{"ok": true}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
    }
)


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://api.deepseek.com/chat/completions",
        code,
        "error",
        {},
        None,
    )


class ConversationLLMResilienceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sleep_patcher = mock.patch("starter.conversation_llm.time.sleep")
        self.sleep_patcher.start()
        self.addCleanup(self.sleep_patcher.stop)

    def _client(self) -> DeepSeekConversationLLM:
        return DeepSeekConversationLLM(
            api_key="test-key",
            timeout_seconds=1.0,
            max_attempts=2,
            max_consecutive_failures=3,
        )

    def test_consecutive_failures_disable_llm(self) -> None:
        client = self._client()
        with mock.patch(
            "starter.conversation_llm.urllib.request.urlopen",
            side_effect=urllib.error.URLError("blocked"),
        ):
            for _ in range(2):
                payload, usage = client.interpret({}, None, "hi")
                self.assertIsNone(payload)
            self.assertFalse(client._disabled)
            client.interpret({}, None, "hi")
        self.assertTrue(client._disabled)

    def test_non_retryable_http_error_disables_immediately(self) -> None:
        client = self._client()
        with mock.patch(
            "starter.conversation_llm.urllib.request.urlopen",
            side_effect=_http_error(400),
        ):
            client.interpret({}, None, "hi")
        self.assertTrue(client._disabled)

    def test_success_resets_failure_count(self) -> None:
        client = self._client()
        with mock.patch(
            "starter.conversation_llm.urllib.request.urlopen",
            side_effect=urllib.error.URLError("blocked"),
        ):
            client.interpret({}, None, "hi")
            client.interpret({}, None, "hi")
        self.assertEqual(client._consecutive_failures, 2)
        with mock.patch(
            "starter.conversation_llm.urllib.request.urlopen",
            return_value=_FakeResponse(VALID_PAYLOAD),
        ):
            payload, usage = client.interpret({}, None, "hi")
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(client._consecutive_failures, 0)
        self.assertEqual(usage.prompt_tokens, 10)

    def test_malformed_content_counts_as_failure(self) -> None:
        client = self._client()
        broken = json.dumps(
            {
                "choices": [{"message": {"content": "not json"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            }
        )
        with mock.patch(
            "starter.conversation_llm.urllib.request.urlopen",
            return_value=_FakeResponse(broken),
        ):
            payload, usage = client.interpret({}, None, "hi")
        self.assertIsNone(payload)
        self.assertEqual(client._consecutive_failures, 1)
        self.assertFalse(client._disabled)
        self.assertEqual(usage.prompt_tokens, 5)


if __name__ == "__main__":
    unittest.main()
