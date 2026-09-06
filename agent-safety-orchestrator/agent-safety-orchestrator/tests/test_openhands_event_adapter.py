from hooks.scripts.lib_common import normalize_host_event


def test_normalizes_openhands_terminal_event() -> None:
    event = normalize_host_event(
        {
            "event_type": "PreToolUse",
            "tool_name": "terminal",
            "tool_input": {"command": "pwd"},
            "working_dir": "/workspace",
        }
    )

    assert event["tool_name"] == "Bash"
    assert event["tool_input"]["command"] == "pwd"
    assert event["cwd"] == "/workspace"


def test_normalizes_openhands_prompt_and_file_editor_event() -> None:
    prompt = normalize_host_event(
        {"event_type": "UserPromptSubmit", "message": "hello"}
    )
    edit = normalize_host_event(
        {
            "event_type": "PreToolUse",
            "tool_name": "file_editor",
            "tool_input": {
                "path": "/workspace/a.py",
                "file_text": "print('ok')",
            },
        }
    )

    assert prompt["prompt"] == "hello"
    assert prompt["user_message"] == "hello"
    assert edit["tool_name"] == "Edit"
    assert edit["tool_input"]["file_path"] == "/workspace/a.py"
    assert edit["tool_input"]["content"] == "print('ok')"
