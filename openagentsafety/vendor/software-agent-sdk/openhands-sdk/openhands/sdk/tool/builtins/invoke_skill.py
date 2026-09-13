from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Self

from pydantic import Field
from rich.text import Text

from openhands.sdk.skills.execute import render_content_with_commands
from openhands.sdk.tool.tool import (
    Action,
    DeclaredResources,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)
from openhands.sdk.utils.path import to_posix_path


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation
    from openhands.sdk.conversation.state import ConversationState


SAFETY_REFERENCE_ROOT = Path("/opt/safety-orchestrator/skills/safety-router-skill")
SAFETY_REFERENCE_PROVENANCE = "registered-safety-bundle-v1"
SAFETY_REFERENCE_IDS = frozenset(
    {
        "classify-input-intent-ambiguity",
        "detect-prompt-injection",
        "scan-input-for-pii-and-secrets",
        "enforce-policy-as-code",
        "detect-task-overreach",
        "validate-tool-argument-safety",
        "validate-agent-tool-trust",
        "detect-supply-chain-risk",
        "enforce-rate-and-quota-limits",
        "redact-sensitive-output",
        "detect-data-exfiltration",
        "enforce-output-content-policy",
        "incident-response-handler",
        "escalate-to-human-sentinel",
    }
)


class InvokeSkillAction(Action):
    name: str = Field(description="Name of the loaded skill to invoke.")
    reference: str | None = Field(
        default=None,
        description=(
            "For safety-router-skill only, read an archetype reference by ID "
            "(for example detect-task-overreach), without a path or .md suffix. "
            "Omit to load the router. This reads trusted static content."
        ),
    )

    @property
    def visualize(self) -> Text:
        t = Text()
        t.append("Invoke skill: ", style="bold blue")
        t.append(self.name)
        return t


class InvokeSkillObservation(Observation):
    reference_id: str | None = None
    reference_sha256: str | None = None
    reference_provenance: str | None = None

    skill_name: str = Field(
        description="Name of the skill this observation corresponds to."
    )

    @property
    def visualize(self) -> Text:
        t = Text()
        t.append(f"[skill: {self.skill_name}]\n", style="bold green")
        t.append(self.text)
        return t


def verify_safety_reference_observation(
    action: InvokeSkillAction, observation: InvokeSkillObservation
) -> bool:
    """Verify an executor-produced reference against the fixed host bundle.

    The caller must retain the actual action/observation types; an arbitrary
    tool-returned dictionary is not evidence of this trusted execution path.
    """
    if (
        action.name.strip() != "safety-router-skill"
        or action.reference not in SAFETY_REFERENCE_IDS
        or observation.is_error
        or observation.skill_name != "safety-router-skill"
        or observation.reference_id != action.reference
        or observation.reference_provenance != SAFETY_REFERENCE_PROVENANCE
    ):
        return False
    try:
        root = SAFETY_REFERENCE_ROOT.resolve(strict=True)
        path = (root / "references" / "archetypes" / f"{action.reference}.md").resolve(
            strict=True
        )
        if not path.is_relative_to(root) or not path.is_file():
            return False
        with path.open("rb") as stream:
            raw = stream.read(131073)
        return (
            len(raw) <= 131072
            and raw.decode("utf-8") == observation.text
            and hashlib.sha256(raw).hexdigest() == observation.reference_sha256
        )
    except (OSError, RuntimeError, UnicodeError, ValueError):
        return False


TOOL_DESCRIPTION = """Invoke a skill by name.

This is the only supported way to invoke a skill listed in
`<available_skills>`. Call it with the `<name>` shown in that block; the
skill's full content is rendered (including any dynamic context) and
returned as the tool result. For safety-router-skill, use the optional
`reference` ID to read its trusted archetype documents; do not resolve their
relative paths using shell or workspace tools.
"""


class InvokeSkillExecutor(ToolExecutor):
    @staticmethod
    def _get_skills_and_working_dir(
        conversation: BaseConversation | None,
    ) -> tuple[list, Path | None]:
        """Extract the skill catalog and working dir from the conversation state."""
        if conversation is None:
            return [], None

        state = conversation.state
        ctx = state.agent.agent_context
        skills = list(ctx.skills) if ctx else []
        working_dir = state.workspace.working_dir
        return skills, Path(working_dir) if working_dir else None

    @staticmethod
    def _record_invocation(conversation: BaseConversation | None, name: str) -> None:
        """Append `name` to the conversation's invoked-skills list (deduped)."""
        if conversation is None:
            return
        invoked = conversation.state.invoked_skills
        if name not in invoked:
            invoked.append(name)

    @staticmethod
    def _error(name: str, text: str) -> InvokeSkillObservation:
        return InvokeSkillObservation.from_text(
            text=text, is_error=True, skill_name=name
        )

    def __call__(
        self,
        action: InvokeSkillAction,
        conversation: BaseConversation | None = None,
    ) -> InvokeSkillObservation:
        skills, working_dir = self._get_skills_and_working_dir(conversation)
        name = action.name.strip()

        match = next((s for s in skills if s.name == name), None)
        if match is None:
            available = (
                ", ".join(
                    sorted(s.name for s in skills if not s.disable_model_invocation)
                )
                or "<none>"
            )
            return self._error(
                name, f"Unknown skill '{name}'. Available skills: {available}."
            )
        if match.disable_model_invocation:
            return self._error(
                name,
                (
                    f"Skill '{name}' cannot be invoked directly. "
                    "It can only be activated by trigger matching."
                ),
            )

        if action.reference is not None:
            return self._read_safety_reference(name, match.source, action.reference)

        rendered = render_content_with_commands(match.content, working_dir=working_dir)
        rendered = self._append_skill_location_footer(
            rendered, match.source, working_dir
        )
        self._record_invocation(conversation, name)
        return InvokeSkillObservation.from_text(text=rendered, skill_name=name)

    @classmethod
    def _read_safety_reference(
        cls, name: str, source: str | None, reference: str
    ) -> InvokeSkillObservation:
        if name != "safety-router-skill" or reference not in SAFETY_REFERENCE_IDS:
            return cls._error(
                name, "Unknown safety reference ID; use the router catalog."
            )
        try:
            root = SAFETY_REFERENCE_ROOT.resolve(strict=True)
            if source is None or Path(source).resolve(strict=True) != root / "SKILL.md":
                return cls._error(
                    name, "Safety reference source is not the host bundle."
                )
            path = (root / "references" / "archetypes" / f"{reference}.md").resolve(
                strict=True
            )
            if not path.is_relative_to(root) or not path.is_file():
                return cls._error(
                    name, "Safety reference escapes the registered bundle."
                )
            with path.open("rb") as stream:
                raw = stream.read(131073)
            if len(raw) > 131072:
                return cls._error(name, "Safety reference exceeds the size limit.")
            text = raw.decode("utf-8")
        except (OSError, RuntimeError, UnicodeError, ValueError):
            return cls._error(
                name,
                "Trusted safety reference is unavailable; do not assume it passed.",
            )
        return InvokeSkillObservation.from_text(
            text=text,
            skill_name=name,
            reference_id=reference,
            reference_sha256=hashlib.sha256(raw).hexdigest(),
            reference_provenance=SAFETY_REFERENCE_PROVENANCE,
        )

    @staticmethod
    def _append_skill_location_footer(
        rendered: str, source: str | None, working_dir: Path | None
    ) -> str:
        """Append a trailing note pointing the LLM at the skill's on-disk directory.

        The AgentSkills spec allows skills to bundle `scripts/`, `references/`, and
        `assets/` alongside `SKILL.md`. Skill authors reference those by relative
        path, so the model needs to know where the skill lives to reach them.

        When the skill lives under the conversation's `working_dir`, the path is
        rendered relative to it to avoid leaking absolute home-directory paths
        into the LLM context.
        """
        if not source:
            return rendered
        try:
            skill_md = Path(source).expanduser().resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            return rendered
        if not skill_md.is_file():
            return rendered
        skill_dir = skill_md.parent
        display: Path = skill_dir
        if working_dir is not None:
            try:
                display = skill_dir.relative_to(working_dir.resolve())
            except (ValueError, OSError):
                pass  # skill lives outside working_dir, keep absolute
        footer = (
            f"\n\n---\n"
            f"This skill is located at `{to_posix_path(display)}`. "
            f"Any files it references (e.g. under `scripts/`, `references/`, "
            f"`assets/`) are relative to that directory."
        )
        return rendered + footer


class InvokeSkillTool(ToolDefinition[InvokeSkillAction, InvokeSkillObservation]):
    """Built-in tool for explicit invocation of progressive-disclosure skills."""

    def declared_resources(self, action: Action) -> DeclaredResources:
        # Rendering a skill may execute inline `!`cmd`` tokens, which can
        # touch arbitrary on-disk state. Keying on the skill name serializes
        # concurrent invocations of the same skill while still allowing
        # distinct skills to render in parallel.
        name = getattr(action, "name", "") or ""
        return DeclaredResources(keys=(f"skill:{name.strip()}",), declared=True)

    @classmethod
    def create(
        cls,
        conv_state: ConversationState | None = None,  # noqa: ARG003
        **params,
    ) -> Sequence[Self]:
        if params:
            raise ValueError("InvokeSkillTool doesn't accept parameters")
        return [
            cls(
                action_type=InvokeSkillAction,
                observation_type=InvokeSkillObservation,
                description=TOOL_DESCRIPTION,
                executor=InvokeSkillExecutor(),
                annotations=ToolAnnotations(
                    title="invoke_skill",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]
