"""Check authentication, history forwarding and failure semantics offline."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api_benchmarks.responses_bridge import create_app


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = Path(self.directory.name) / "requests.jsonl"
        self.client = TestClient(
            create_app(
                {
                    "BRIDGE_TOKEN": "local-token",
                    "BRIDGE_MODEL": "org/glm",
                    "BRIDGE_UPSTREAM_URL": "https://provider.example/v1",
                    "BRIDGE_UPSTREAM_KEY": "provider-secret",
                    "BRIDGE_LOG": str(self.log),
                }
            )
        )
        self.headers = {"Authorization": "Bearer local-token"}
        self.body = {"model": "org/glm", "stream": True, "input": "hello"}

    def test_auth_and_fixed_model_reject_before_provider(self):
        with patch("litellm.aresponses", new_callable=AsyncMock) as upstream:
            self.assertEqual(
                self.client.post("/v1/responses", json=self.body).status_code, 401
            )
            for change in (
                {"model": "another/model"},
                {"previous_response_id": "other-trial"},
                {"stream": False},
            ):
                result = self.client.post(
                    "/v1/responses", headers=self.headers, json={**self.body, **change}
                )
                self.assertEqual(result.status_code, 400)
            upstream.assert_not_awaited()

    def test_full_tool_history_and_host_credentials_are_forwarded(self):
        async def events():
            yield {
                "type": "response.completed",
                "response": {
                    "status": "completed",
                    "output": [],
                    "usage": {"input_tokens": 5},
                },
            }

        history = [
            {"role": "user", "content": "private-task-prompt"},
            {
                "type": "function_call",
                "call_id": "call1",
                "name": "lookup",
                "arguments": "{}",
            },
            {"type": "function_call_output", "call_id": "call1", "output": "7319"},
        ]
        body = {
            **self.body,
            "input": history,
            "api_base": "https://untrusted.example",
            "instructions": "original instructions",
            "tools": [
                {"type": "function", "name": "lookup", "parameters": {"type": "object"}}
            ],
        }
        with patch(
            "litellm.aresponses", new_callable=AsyncMock, return_value=events()
        ) as upstream:
            result = self.client.post("/v1/responses", headers=self.headers, json=body)
            self.assertIn("response.completed", result.text)
            kwargs = upstream.call_args.kwargs
            self.assertEqual(kwargs["input"], history)
            self.assertEqual(kwargs["tools"], body["tools"])
            self.assertEqual(kwargs["instructions"], body["instructions"])
            self.assertEqual(kwargs["api_base"], "https://provider.example/v1")
            self.assertEqual(kwargs["api_key"], "provider-secret")
            self.assertEqual(kwargs["extra_body"], {"enable_thinking": False})
        for secret in ("provider-secret", "local-token", "private-task-prompt"):
            self.assertNotIn(secret, self.log.read_text())
            self.assertNotIn(secret, result.text)

    def test_stream_failure_is_not_completed(self):
        async def events():
            yield {"type": "response.created", "response": {"status": "in_progress"}}
            raise RuntimeError("provider-secret")

        with patch("litellm.aresponses", new_callable=AsyncMock, return_value=events()):
            result = self.client.post(
                "/v1/responses", headers=self.headers, json=self.body
            )
            self.assertIn("response.failed", result.text)
            self.assertNotIn("response.completed", result.text)
            self.assertNotIn("provider-secret", result.text + self.log.read_text())
            for line in self.log.read_text().splitlines():
                json.loads(line)


if __name__ == "__main__":
    unittest.main()
