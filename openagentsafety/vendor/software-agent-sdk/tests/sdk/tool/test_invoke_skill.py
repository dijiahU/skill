"""Tests for the `invoke_skill` built-in tool."""

from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM, Agent, AgentContext
from openhands.sdk.context import KeywordTrigger
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.skills import Skill
from openhands.sdk.tool.builtins import (
    BUILT_IN_TOOL_CLASSES,
    BUILT_IN_TOOLS,
    InvokeSkillAction,
    InvokeSkillObservation,
    InvokeSkillTool,
    invoke_skill as reference_module,
)
from openhands.sdk.workspace.local import LocalWorkspace


def _make_skill(
    name: str,
    content: str = "# body\n\nSome guidance.",
    is_agentskills_format: bool = True,
    trigger=None,
    disable_model_invocation: bool = False,
) -> Skill:
    return Skill(
        name=name,
        content=content,
        description=f"desc for {name}",
        source=f"/skills/{name}/SKILL.md",
        is_agentskills_format=is_agentskills_format,
        trigger=trigger,
        disable_model_invocation=disable_model_invocation,
    )


def _make_conv(
    skills: list[Skill],
    working_dir: str = "/tmp",
    invoked_skills: list[str] | None = None,
) -> Any:
    """Minimal duck-typed BaseConversation replacement for the executor.

    Returned as `Any` so pyright accepts it where a `LocalConversation`
    is declared; the executor only uses attribute access, so a
    SimpleNamespace is enough at runtime.
    """
    return SimpleNamespace(
        state=SimpleNamespace(
            agent=SimpleNamespace(
                agent_context=SimpleNamespace(skills=skills),
            ),
            workspace=SimpleNamespace(working_dir=working_dir),
            invoked_skills=invoked_skills or [],
        ),
    )


def _tool() -> InvokeSkillTool:
    (t,) = InvokeSkillTool.create()
    return t


def _run(name: str, conv: Any) -> InvokeSkillObservation:
    """Invoke the executor, silencing pyright's Optional complaint on .executor."""
    executor = _tool().executor
    assert executor is not None
    return executor(InvokeSkillAction(name=name), conversation=conv)


def test_not_in_default_builtins_but_resolvable_by_name():
    # Deliberately NOT in BUILT_IN_TOOLS: it must only attach when an
    # AgentSkills-format skill is loaded.
    assert InvokeSkillTool not in BUILT_IN_TOOLS
    # Still resolvable by name so the agent can wire it up conditionally.
    assert BUILT_IN_TOOL_CLASSES["InvokeSkillTool"] is InvokeSkillTool


def test_name_auto_derived():
    assert InvokeSkillTool.name == "invoke_skill"


def test_create_rejects_params():
    with pytest.raises(ValueError):
        InvokeSkillTool.create(foo="bar")


@pytest.mark.parametrize(
    ("attr", "expected"),
    [
        ("readOnlyHint", True),
        ("destructiveHint", False),
        ("idempotentHint", True),
        ("openWorldHint", False),
    ],
)
def test_annotations_are_read_only_safe(attr: str, expected: bool):
    t = _tool()
    assert t.annotations is not None
    assert getattr(t.annotations, attr) is expected


@pytest.mark.parametrize(
    ("content", "present", "absent"),
    [
        pytest.param(
            "Rule 1.\nRule 2.",
            "Rule 1.",
            None,
            id="static-content",
        ),
        pytest.param(
            "before !`echo TOKEN_OK` after",
            "TOKEN_OK",
            "!`echo",
            id="dynamic-shell-token-executed",
        ),
    ],
)
def test_invoke_renders_and_records(
    content: str, present: str, absent: str | None, tmp_path
):
    skill = _make_skill("s", content=content)
    conv = _make_conv([skill], working_dir=str(tmp_path))

    obs = _run("s", conv)

    assert obs.is_error is False
    assert obs.skill_name == "s"
    assert present in obs.text
    if absent is not None:
        assert absent not in obs.text
    assert conv.state.invoked_skills == ["s"]


@pytest.mark.parametrize(
    "requested",
    ["pdf-analyst", "  pdf-analyst  ", "\tpdf-analyst\n"],
    ids=["exact", "padded-spaces", "padded-tabs-newlines"],
)
def test_name_is_trimmed_before_lookup(requested: str):
    conv = _make_conv([_make_skill("pdf-analyst")])

    obs = _run(requested, conv)

    assert obs.is_error is False
    assert obs.skill_name == "pdf-analyst"


def test_footer_uses_absolute_path_when_outside_working_dir(tmp_path):
    """Skill outside the conversation's working_dir: footer shows absolute path."""
    skill_dir = tmp_path / "pdf-analyst"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("placeholder")
    skill = Skill(
        name="pdf-analyst",
        content="# body\n\nSee scripts/extract.py.",
        description="desc",
        source=str(skill_md),
        is_agentskills_format=True,
    )
    # working_dir is unrelated, so the footer must stay absolute.
    conv = _make_conv([skill], working_dir=str(tmp_path / "elsewhere"))

    obs = _run("pdf-analyst", conv)

    assert obs.is_error is False
    assert skill_dir.resolve().as_posix() in obs.text
    assert "scripts/" in obs.text and "references/" in obs.text
    assert obs.text.rstrip().endswith("relative to that directory.")


def test_footer_uses_relative_path_when_inside_working_dir(tmp_path):
    """Skill under working_dir: footer uses the relative path, avoiding leakage
    of absolute home-directory paths into the LLM context."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    skill_dir = workspace / "skills" / "pdf-analyst"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("placeholder")
    skill = Skill(
        name="pdf-analyst",
        content="body",
        description="desc",
        source=str(skill_md),
        is_agentskills_format=True,
    )
    conv = _make_conv([skill], working_dir=str(workspace))

    obs = _run("pdf-analyst", conv)

    assert obs.is_error is False
    assert "`skills/pdf-analyst`" in obs.text
    assert str(workspace.resolve()) not in obs.text


def test_footer_omitted_when_skill_has_no_source():
    """Programmatic skills (source=None) should not get a footer."""
    skill = Skill(
        name="prog",
        content="inline body",
        description="desc",
        source=None,
        is_agentskills_format=True,
    )
    conv = _make_conv([skill])

    obs = _run("prog", conv)

    assert obs.is_error is False
    assert "located at" not in obs.text
    assert obs.text.strip() == "inline body"


def test_footer_omitted_when_source_is_not_a_real_path():
    """Sentinels like `'local'` or `'github:owner/repo'` must not produce a footer
    pointing at a made-up path."""
    skill = Skill(
        name="remote",
        content="body",
        description="desc",
        source="github:owner/repo",
        is_agentskills_format=True,
    )
    conv = _make_conv([skill])

    obs = _run("remote", conv)

    assert obs.is_error is False
    assert "located at" not in obs.text


def test_invoked_skills_dedupes():
    conv = _make_conv([_make_skill("x")])

    _run("x", conv)
    _run("x", conv)

    assert conv.state.invoked_skills == ["x"]


def test_legacy_triggered_skill_is_invocable():
    """Any Skill in agent_context.skills is resolvable, not just
    AgentSkills-format. This keeps the executor consistent with what the
    `<available_skills>` prompt block advertises."""
    legacy = _make_skill(
        "flarglebargle",
        content="legacy body",
        is_agentskills_format=False,
        trigger=KeywordTrigger(keywords=["flarglebargle"]),
    )
    conv = _make_conv([legacy])

    obs = _run("flarglebargle", conv)

    assert obs.is_error is False
    assert "legacy body" in obs.text
    assert conv.state.invoked_skills == ["flarglebargle"]


def test_disable_model_invocation_rejects_direct_invocation():
    skill = _make_skill(
        "trigger-only",
        disable_model_invocation=True,
        trigger=KeywordTrigger(keywords=["trigger-only"]),
    )
    conv = _make_conv([skill])

    obs = _run("trigger-only", conv)

    assert obs.is_error is True
    assert obs.skill_name == "trigger-only"
    assert "cannot be invoked directly" in obs.text
    assert conv.state.invoked_skills == []


@pytest.mark.parametrize(
    ("conv_factory", "requested", "expected_substrings"),
    [
        pytest.param(
            lambda: _make_conv([_make_skill("alpha"), _make_skill("beta")]),
            "gamma",
            ("Unknown skill 'gamma'", "alpha", "beta"),
            id="name-not-in-catalog",
        ),
        pytest.param(
            lambda: _make_conv([]),
            "anything",
            ("Unknown skill 'anything'", "<none>"),
            id="empty-catalog",
        ),
        pytest.param(
            lambda: None,
            "anything",
            ("Unknown skill 'anything'", "<none>"),
            id="no-conversation",
        ),
    ],
)
def test_error_paths_do_not_mutate_state(
    conv_factory, requested: str, expected_substrings: tuple[str, ...]
):
    conv = conv_factory()

    obs = _run(requested, conv)

    assert obs.is_error is True
    assert obs.skill_name == requested
    for expected in expected_substrings:
        assert expected in obs.text
    if conv is not None:
        assert conv.state.invoked_skills == []


@pytest.mark.parametrize(
    "skill_name",
    ["pdf-analyst", "frontend-design", "with space"],
)
def test_declared_resources_keyed_on_skill_name(skill_name: str):
    res = _tool().declared_resources(InvokeSkillAction(name=skill_name))

    assert res.declared is True
    assert res.keys == (f"skill:{skill_name.strip()}",)


def _make_agent(skills: list[Skill]) -> Agent:
    llm = LLM(
        usage_id="agent",
        model="anthropic/claude-sonnet-4-5-20250929",
        api_key=SecretStr("x"),
    )
    return Agent(llm=llm, tools=[], agent_context=AgentContext(skills=skills))


@pytest.mark.parametrize(
    ("skills", "expect_attached"),
    [
        pytest.param([], False, id="no-skills"),
        pytest.param(
            [_make_skill("legacy", is_agentskills_format=False)],
            False,
            id="only-legacy-skill",
        ),
        pytest.param(
            [_make_skill("frontend-design", is_agentskills_format=True)],
            True,
            id="agentskills-present",
        ),
        pytest.param(
            [
                _make_skill(
                    "trigger-only",
                    is_agentskills_format=True,
                    disable_model_invocation=True,
                )
            ],
            False,
            id="only-disabled-agentskills",
        ),
        pytest.param(
            [
                _make_skill(
                    "trigger-only",
                    is_agentskills_format=True,
                    disable_model_invocation=True,
                ),
                _make_skill("frontend-design", is_agentskills_format=True),
            ],
            True,
            id="mixed-disabled-and-invocable-agentskills",
        ),
    ],
)
def test_agent_auto_attaches_invoke_skill_tool(
    skills: list[Skill], expect_attached: bool, tmp_path
):
    """`Agent._initialize` must attach `invoke_skill` iff an AgentSkills-format
    skill is loaded — regardless of what's in `include_default_tools`."""
    agent = _make_agent(skills)
    state = ConversationState.create(
        id=uuid.uuid4(),
        agent=agent,
        workspace=LocalWorkspace(working_dir=str(tmp_path)),
    )
    agent._initialize(state)

    attached = "invoke_skill" in agent._tools
    assert attached is expect_attached


@pytest.fixture
def trusted_safety_reference(tmp_path, monkeypatch):
    root = tmp_path / "bundle" / "skills" / "safety-router-skill"
    refs = root / "references" / "archetypes"
    refs.mkdir(parents=True)
    (root / "SKILL.md").write_text("# Router")
    path = refs / "detect-task-overreach.md"
    body = "# detect-task-overreach\nTrusted policy, not executable: !`touch marker`\n"
    path.write_text(body)
    monkeypatch.setattr(reference_module, "SAFETY_REFERENCE_ROOT", root)
    skill = _make_skill("safety-router-skill").model_copy(
        update={"source": str(root / "SKILL.md")}
    )
    conv = _make_conv([skill], working_dir=str(tmp_path / "unrelated-workspace"))
    return root, path, body, conv


def test_reference_reads_static_document_without_cwd_or_command_execution(
    trusted_safety_reference,
):
    _, _, body, conv = trusted_safety_reference
    action = InvokeSkillAction(
        name="safety-router-skill", reference="detect-task-overreach"
    )
    result = reference_module.InvokeSkillExecutor()(action, conv)
    assert not result.is_error
    assert result.text == body
    assert result.reference_sha256 == hashlib.sha256(body.encode()).hexdigest()
    assert reference_module.verify_safety_reference_observation(action, result)
    assert (
        not conv.state.invoked_skills
    )  # Reading is distinct from invoking the router.
    altered = result.model_copy(update={"reference_sha256": "0" * 64})
    assert not reference_module.verify_safety_reference_observation(action, altered)


@pytest.mark.parametrize(
    "reference", ["../SKILL", "/etc/passwd", "unknown", "detect-task-overreach.md"]
)
def test_reference_rejects_non_catalog_ids(trusted_safety_reference, reference):
    _, _, _, conv = trusted_safety_reference
    action = InvokeSkillAction(name="safety-router-skill", reference=reference)
    assert reference_module.InvokeSkillExecutor()(action, conv).is_error


def test_reference_rejects_impostor_skill_source(trusted_safety_reference, tmp_path):
    _, _, _, conv = trusted_safety_reference
    fake = tmp_path / "fake" / "SKILL.md"
    fake.parent.mkdir()
    fake.write_text("# Impostor")
    conv.state.agent.agent_context.skills[0] = _make_skill(
        "safety-router-skill"
    ).model_copy(update={"source": str(fake)})
    action = InvokeSkillAction(
        name="safety-router-skill", reference="detect-task-overreach"
    )
    assert reference_module.InvokeSkillExecutor()(action, conv).is_error


def test_reference_rejects_symlink_escape(trusted_safety_reference, tmp_path):
    root, _, _, conv = trusted_safety_reference
    outside = tmp_path / "outside.md"
    outside.write_text("# Untrusted")
    (root / "references" / "archetypes" / "detect-prompt-injection.md").symlink_to(
        outside
    )
    action = InvokeSkillAction(
        name="safety-router-skill", reference="detect-prompt-injection"
    )
    assert reference_module.InvokeSkillExecutor()(action, conv).is_error


def test_reference_rejects_missing_file(trusted_safety_reference):
    _, _, _, conv = trusted_safety_reference
    action = InvokeSkillAction(
        name="safety-router-skill", reference="detect-data-exfiltration"
    )
    assert reference_module.InvokeSkillExecutor()(action, conv).is_error
