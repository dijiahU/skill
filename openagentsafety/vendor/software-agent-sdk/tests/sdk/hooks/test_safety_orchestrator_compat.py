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
    ).replace(" -c ", " -S -c ", 1)  # Standard-library hook fixture; no sitecustomize.
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


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("replacement", ["Checked synthetic output", ""])
def test_replacement_discards_structured_fields_and_images_and_survives_reload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    replacement: str,
) -> None:
    monkeypatch.setenv(COMPAT_ENV, "1" if enabled else "0")
    conversation_id = uuid.uuid4()
    state = _state(tmp_path, conversation_id)
    processor = HookEventProcessor(
        HookManager(
            config=_config(
                "PostToolUse",
                {
                    "verdict": "warn",
                    "reason": "Synthetic redaction",
                    "modified_output": replacement,
                },
            ),
            working_dir=str(tmp_path),
        ),
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
    resumed = _state(tmp_path, conversation_id)
    output = resumed.events[-1]
    assert isinstance(output, ObservationEvent)
    assert output.id == original.id
    assert output.action_id == original.action_id
    assert output.to_llm_message().tool_call_id == original.tool_call_id
    assert (PAYLOAD in output.model_dump_json()) is not enabled
    assert (PAYLOAD in output.to_llm_message().model_dump_json()) is not enabled
    if enabled:
        assert "Synthetic redaction" in output.to_llm_message().model_dump_json()
        audit = next(e for e in resumed.events if isinstance(e, HookExecutionEvent))
        assert PAYLOAD not in json.dumps(audit.hook_input)
    assert PAYLOAD in original.model_dump_json()


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("event_name", ["PreToolUse", "PostToolUse"])
def test_tool_warning_is_visible_without_blocking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    event_name: str,
) -> None:
    monkeypatch.setenv(COMPAT_ENV, "1" if enabled else "0")
    state = _state(tmp_path, uuid.uuid4())
    processor = HookEventProcessor(
        HookManager(
            config=_config(
                event_name,
                {
                    "verdict": "warn",
                    "reason": "Synthetic scoped warning",
                },
            ),
            working_dir=str(tmp_path),
        ),
        original_callback=state.events.append,
    )
    processor.set_conversation_state(state)
    action = _action()
    processor.on_event(action)
    assert state.pop_blocked_action(action.id) is None
    processor.on_event(
        ObservationEvent(
            action_id=action.id,
            tool_name=action.tool_name,
            tool_call_id=action.tool_call_id,
            observation=SafetyCompatTestObservation(raw_output="Ordinary result"),
        )
    )
    output = state.events[-1]
    assert isinstance(output, ObservationEvent)
    rendered = output.to_llm_message().model_dump_json()
    assert "Ordinary result" in rendered
    assert ("Synthetic scoped warning" in rendered) is enabled
    if enabled:
        assert "already ran" in rendered


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("failure", ["timeout", "exit1", "bad-json", "bad-replacement"])
def test_tool_check_failure_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    failure: str,
) -> None:
    import subprocess
    from types import SimpleNamespace

    from openhands.sdk.hooks.config import HookDefinition
    from openhands.sdk.hooks.executor import HookExecutor
    from openhands.sdk.hooks.types import HookEvent, HookEventType

    monkeypatch.setenv(COMPAT_ENV, "1" if enabled else "0")

    def mock_run(*args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired("synthetic", 1)
        return SimpleNamespace(
            returncode=1 if failure == "exit1" else 0,
            stdout="{}\n{}"
            if failure == "bad-json"
            else '{"modified_output": 123}'
            if failure == "bad-replacement"
            else "",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    result = HookExecutor(working_dir=str(tmp_path)).execute(
        HookDefinition(command="never executed"),
        HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="terminal"),
    )
    assert result.should_continue is not enabled
    assert result.blocked is enabled
    if enabled:
        assert result.error


def test_posttool_failure_withholds_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(COMPAT_ENV, "1")
    state = _state(tmp_path, uuid.uuid4())
    processor = HookEventProcessor(
        HookManager(config=_config("PostToolUse", {}, 1), working_dir=str(tmp_path)),
        original_callback=state.events.append,
    )
    processor.set_conversation_state(state)
    action = _action()
    state.events.append(action)
    processor.on_event(
        ObservationEvent(
            action_id=action.id,
            tool_name=action.tool_name,
            tool_call_id=action.tool_call_id,
            observation=SafetyCompatTestObservation(raw_output=PAYLOAD),
        )
    )
    assert isinstance(state.events[-1], AgentErrorEvent)
    assert PAYLOAD not in state.events[-1].model_dump_json()
    audit = next(e for e in state.events if isinstance(e, HookExecutionEvent))
    assert audit.blocked and audit.error
    assert PAYLOAD not in json.dumps(audit.hook_input)


@pytest.mark.parametrize(
    "variant", ["verified", "wrong-hash", "wrong-tool", "fake-type"]
)
def test_only_verified_typed_reference_bypasses_untrusted_output_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
) -> None:
    import hashlib

    from openhands.sdk.tool.builtins import invoke_skill

    monkeypatch.setenv(COMPAT_ENV, "1")
    root = tmp_path / "trusted-bundle"
    directory = root / "references" / "archetypes"
    directory.mkdir(parents=True)
    reference = "detect-prompt-injection"
    content = "Trusted fixture policy text, no commands."
    (directory / f"{reference}.md").write_text(content)
    monkeypatch.setattr(invoke_skill, "SAFETY_REFERENCE_ROOT", root)
    action = _action().model_copy(
        update={
            "tool_name": "invoke_skill",
            "action": invoke_skill.InvokeSkillAction(
                name="safety-router-skill",
                reference=reference,
            ),
        }
    )
    observation = invoke_skill.InvokeSkillObservation.from_text(
        text=content,
        skill_name="safety-router-skill",
        reference_id=reference,
        reference_sha256=hashlib.sha256(content.encode()).hexdigest(),
        reference_provenance=invoke_skill.SAFETY_REFERENCE_PROVENANCE,
    )
    if variant == "wrong-hash":
        observation = observation.model_copy(update={"reference_sha256": "bad"})
    if variant == "wrong-tool":
        action = action.model_copy(update={"tool_name": "terminal"})
    if variant == "fake-type":
        observation = SafetyCompatTestObservation(raw_output=content)
    state = _state(tmp_path, uuid.uuid4())
    processor = HookEventProcessor(
        HookManager(
            config=_config("PostToolUse", {"reason": "Untrusted"}, 2),
            working_dir=str(tmp_path),
        ),
        original_callback=state.events.append,
    )
    processor.set_conversation_state(state)
    state.events.append(action)
    processor.on_event(
        ObservationEvent(
            action_id=action.id,
            tool_name=action.tool_name,
            tool_call_id=action.tool_call_id,
            observation=observation,
        )
    )
    assert isinstance(
        state.events[-1], ObservationEvent if variant == "verified" else AgentErrorEvent
    )


def test_real_bundle_redaction_protocol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import os
    import shlex
    import sys

    bundle = os.environ.get("OAS_TEST_BUNDLE_ROOT")
    if not bundle:
        pytest.skip("Set OAS_TEST_BUNDLE_ROOT for the offline producer integration")
    monkeypatch.setenv(COMPAT_ENV, "1")
    script = Path(bundle) / "hooks/scripts/matcher_posttool.py"
    command = shlex.join([sys.executable, "-S", str(script)])
    config = HookConfig.model_validate(
        {"hooks": {"PostToolUse": [{"matcher": "*", "hooks": [{"command": command}]}]}}
    )
    state = _state(tmp_path, uuid.uuid4())
    processor = HookEventProcessor(
        HookManager(config=config, working_dir=str(tmp_path)),
        original_callback=state.events.append,
    )
    processor.set_conversation_state(state)
    action = _action()
    state.events.append(action)
    processor.on_event(
        ObservationEvent(
            action_id=action.id,
            tool_name=action.tool_name,
            tool_call_id=action.tool_call_id,
            observation=SafetyCompatTestObservation(
                raw_output="Synthetic contact: person@example.com",
            ),
        )
    )
    output = state.events[-1]
    assert isinstance(output, ObservationEvent)
    rendered = output.to_llm_message().model_dump_json()
    assert "person@example.com" not in rendered
    assert "REDACTED" in rendered
    audit = next(e for e in state.events if isinstance(e, HookExecutionEvent))
    payload = json.loads(audit.stdout)
    assert isinstance(payload["modified_output"], str)
    assert not audit.blocked and not audit.error
    assert "person@example.com" not in json.dumps(audit.hook_input)
