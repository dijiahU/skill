from types import SimpleNamespace
from unittest.mock import Mock

from benchmarks.openagentsafety.scripts import chat_npc


def npc_config():
    return {
        "npc_api_key": "test-only",
        "npc_base_url": "http://example.test/v1",
        "default_npc_model": "Qwen/test-model",
        "npc_profiles": [{"name": "Mark", "data": {"occupation": "Director"}}],
        "npc_scenarios": [],
        "npc_extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    }


def test_npc_uses_bounded_requests_without_hidden_reasoning(monkeypatch):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Hello."), finish_reason="stop"
            )
        ]
    )
    client = Mock()
    client.chat.completions.create.return_value = response
    factory = Mock(return_value=client)
    monkeypatch.setattr(chat_npc.openai, "OpenAI", factory)
    assert chat_npc.chat_with_npc("Mark", "Hello", npc_config()) == "Hello."
    assert factory.call_args.kwargs["timeout"] == 60
    assert factory.call_args.kwargs["max_retries"] == 0
    call = client.chat.completions.create.call_args.kwargs
    assert call["max_tokens"] == 500
    assert call["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_npc_reports_reasoning_only_response(monkeypatch, capsys):
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None), finish_reason="length"
            )
        ]
    )
    monkeypatch.setattr(chat_npc.openai, "OpenAI", Mock(return_value=client))
    assert chat_npc.chat_with_npc("Mark", "Hello", npc_config()) is None
    assert "finish_reason=length" in capsys.readouterr().err
