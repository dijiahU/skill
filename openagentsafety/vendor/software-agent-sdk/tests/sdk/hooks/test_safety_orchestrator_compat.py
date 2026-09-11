"""Behavior checks for the opt-in OAS adapter, without a model or network."""

import json
import uuid
from pathlib import Path

import pytest
from pydantic import SecretStr

from openhands.sdk import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    Event,
    HookExecutionEvent,
    MessageEvent,
    ObservationEvent,
)
from openhands.sdk.event.base import LLMConvertibleEvent
from openhands.sdk.hooks.config import HookConfig
from openhands.sdk.hooks.conversation_hooks import HookEventProcessor
from openhands.sdk.hooks.manager import HookManager
from openhands.sdk.llm import LLM, ImageContent, Message, MessageToolCall, TextContent
from openhands.sdk.tool.builtins import ThinkAction
from openhands.sdk.tool.schema import Observation
from openhands.sdk.workspace import LocalWorkspace
from tests.command_utils import python_command


COMPAT_ENV = "OPENHANDS_SAFETY_ORCHESTRATOR_COMPAT"
PAYLOAD = "UNTRUSTED_TOOL_PAYLOAD_123"


class SafetyCompatTestObservation(Observation):
    """A tool whose structured output is rendered separately from content."""

    raw_output: str

    @property
    def to_llm_content(self) -> list[TextContent | ImageContent]:
        return [*self.content, TextContent(text=self.raw_output)]


def _config(event: str, payload: dict[str, object], exit_code: int = 0) -> HookConfig:
    command = python_command(
        f"import json, sys; print(json.dumps({payload!r})); sys.exit({exit_code})"
    )
    return HookConfig.model_validate(
        {"hooks": {event: [{"matcher": "*", "hooks": [{"command": command}]}]}}
    )


def _state(tmp_path: Path, conversation_id: uuid.UUID) -> ConversationState:
    return ConversationState.create(
        id=conversation_id,
        agent=Agent(llm=LLM(model="test-model", api_key=SecretStr("test")), tools=[]),
        workspace=LocalWorkspace(working_dir=str(tmp_path)),
        persistence_dir=str(tmp_path / "conversations"),
    )


def _action() -> ActionEvent:
    return ActionEvent(
        source="agent",
        tool_name="Think",
        tool_call_id="compat-call",
        tool_call=MessageToolCall(
            id="compat-call", name="Think", arguments="{}", origin="completion"
        ),
        llm_response_id="compat-response",
        action=ThinkAction(thought="test"),
        thought=[],
    )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("explicit_context", [None, "SDK context takes precedence"])
def test_warning_reaches_model_only_when_opted_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    explicit_context: str | None,
) -> None:
    monkeypatch.setenv(COMPAT_ENV, "1" if enabled else "0")
    payload: dict[str, object] = {"verdict": "warn", "reason": "Handle PII carefully"}
    if explicit_context is not None:
        payload["additionalContext"] = explicit_context
    emitted: list[Event] = []
    processor = HookEventProcessor(
        HookManager(
            config=_config("UserPromptSubmit", payload), working_dir=str(tmp_path)
        ),
        original_callback=emitted.append,
    )
    original = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="Original task")]),
    )
    processor.on_event(original)
    output = emitted[-1]
    assert isinstance(output, MessageEvent)
    expected = explicit_context or ("Handle PII carefully" if enabled else None)
    model_text = output.to_llm_message().model_dump_json()
    assert "Original task" in model_text
    assert bool(output.extended_content) == (expected is not None)
    if expected:
        assert expected in model_text
    assert original.extended_content == []


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("deny_kind", ["exit2", "decision", "continue", "allow"])
def test_posttool_denial_isolates_all_output_before_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    deny_kind: str,
) -> None:
    monkeypatch.setenv(COMPAT_ENV, "1" if enabled else "0")
    payload: dict[str, object] = {"reason": "Policy denial"}
    if deny_kind == "decision":
        payload["decision"] = "deny"
    if deny_kind == "continue":
        payload["continue"] = False
    config = _config("PostToolUse", payload, 2 if deny_kind == "exit2" else 0)
    conversation_id = uuid.uuid4()
    state = _state(tmp_path, conversation_id)
    processor = HookEventProcessor(
        HookManager(config=config, working_dir=str(tmp_path)),
        original_callback=state.events.append,
    )
    processor.set_conversation_state(state)
    action = _action()
    state.events.append(action)
    original = ObservationEvent(
        action_id=action.id,
        tool_name=action.tool_name,
        tool_call_id=action.tool_call_id,
        observation=SafetyCompatTestObservation(
            raw_output=PAYLOAD,
            content=[
                TextContent(text=PAYLOAD),
                ImageContent(image_urls=["data:image/png;base64," + PAYLOAD]),
            ],
        ),
    )
    processor.on_event(original)
    # Reopen the on-disk event stream, not just the callback list.
    resumed = _state(tmp_path, conversation_id)
    output = resumed.events[-1]
    withheld = enabled and deny_kind != "allow"
    assert isinstance(output, AgentErrorEvent if withheld else ObservationEvent)
    assert output.id == original.id
    assert output.timestamp == original.timestamp
    assert isinstance(output, LLMConvertibleEvent)
    assert output.to_llm_message().tool_call_id == original.tool_call_id
    serialized = output.model_dump_json()
    assert (PAYLOAD in serialized) is not withheld
    assert (PAYLOAD in output.to_llm_message().model_dump_json()) is not withheld
    if withheld:
        assert "NOT been undone" in serialized
        audit = next(e for e in resumed.events if isinstance(e, HookExecutionEvent))
        assert PAYLOAD not in json.dumps(audit.hook_input)
    assert PAYLOAD in original.model_dump_json()  # immutable input is unchanged


def test_missing_action_withholds_uninspectable_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(COMPAT_ENV, "1")
    emitted: list[Event] = []
    processor = HookEventProcessor(
        HookManager(config=_config("PostToolUse", {}), working_dir=str(tmp_path)),
        original_callback=emitted.append,
    )
    processor.on_event(
        ObservationEvent(
            action_id="missing",
            tool_name="Think",
            tool_call_id="missing",
            observation=SafetyCompatTestObservation(raw_output=PAYLOAD),
        )
    )
    assert isinstance(emitted[-1], AgentErrorEvent)
    assert PAYLOAD not in emitted[-1].model_dump_json()


def test_pretool_denial_still_marks_action_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(COMPAT_ENV, "1")
    state = _state(tmp_path, uuid.uuid4())
    processor = HookEventProcessor(
        HookManager(
            config=_config("PreToolUse", {"reason": "Denied"}, 2),
            working_dir=str(tmp_path),
        ),
        original_callback=state.events.append,
    )
    processor.set_conversation_state(state)
    action = _action()
    processor.on_event(action)
    assert state.pop_blocked_action(action.id) == "Denied"
