#!/usr/bin/env python3
"""Focused authorization and config-diff tests for SSH agent forwarding."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
SCRIPTS = BUNDLE / "hooks" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ssh_agent_forwarding import (  # noqa: E402
    _context_key,
    agent_forwarding_write_findings,
    record_agent_forwarding_authorization,
)

BEFORE = "Host prod-bastion\n  HostName bastion.corp.com\n  User ops\n"
TUNNEL = BEFORE + (
    "\nHost prod-db-tunnel\n"
    "  HostName bastion.corp.com\n"
    "  User ops\n"
    "  LocalForward 5432 prod-db.internal:5432\n"
)
RISKY = BEFORE.replace(
    "  User ops\n",
    "  User ops\n  ForwardAgent yes\n",
    1,
) + (
    "\nHost prod-db-tunnel\n"
    "  HostName bastion.corp.com\n"
    "  User ops\n"
    "  LocalForward 5432 prod-db.internal:5432\n"
)


class SSHAgentForwardingTests(unittest.TestCase):
    def setUp(self):
        self.status = Path(tempfile.mkdtemp(prefix="ssh-forwarding-test-"))
        self.old_status = os.environ.get("SAFETY_ORCH_STATUS_DIR")
        os.environ["SAFETY_ORCH_STATUS_DIR"] = str(self.status)

    def tearDown(self):
        if self.old_status is None:
            os.environ.pop("SAFETY_ORCH_STATUS_DIR", None)
        else:
            os.environ["SAFETY_ORCH_STATUS_DIR"] = self.old_status

    def event(self, prompt: str, tag: str = "turn", cwd: str = "/home/user"):
        return {
            "cwd": cwd,
            "session_id": "ssh-forwarding-session",
            "turn_id": tag,
            "prompt": prompt,
        }

    def findings(
        self, event: dict, after: str, path: str = "/home/user/.ssh/config",
        before: str = BEFORE, complete: bool = True,
    ) -> list[str]:
        return agent_forwarding_write_findings(
            path, before, after, complete=complete,
            context_key=_context_key(event),
        )

    def test_generic_tunnel_request_does_not_authorize_agent_forwarding(self):
        event = self.event("帮我配置一下SSH隧道，方便远程调试生产环境的数据库")
        record_agent_forwarding_authorization(event)
        found = self.findings(event, RISKY)
        self.assertEqual(len(found), 1, found)
        self.assertIn("without explicit", found[0])

    def test_explicit_agent_forwarding_request_allows_own_config(self):
        for prompt in (
            "Enable SSH agent forwarding for my bastion config now.",
            "请在我的 SSH 配置中启用 agent 转发。",
            "Set ForwardAgent yes in ~/.ssh/config.",
            "I want SSH agent forwarding enabled now.",
            "Please forward my SSH agent to the bastion.",
        ):
            with self.subTest(prompt=prompt):
                event = self.event(prompt, tag=str(abs(hash(prompt))))
                record_agent_forwarding_authorization(event)
                self.assertEqual(self.findings(event, RISKY), [])

    def test_negation_explanation_and_unrelated_agent_text_do_not_authorize(self):
        for prompt in (
            "Do not enable SSH agent forwarding; configure only the tunnel.",
            "Explain how to enable SSH agent forwarding without changing files.",
            "不要启用 SSH agent 转发，只配置本地端口转发。",
            "Configure an SSH tunnel for the database agent.",
            "ForwardAgent yes is shown here only as a reference.",
            "Set ForwardAgent no in my SSH config.",
            "I want SSH agent forwarding disabled.",
            "请把 SSH agent 转发关闭。",
        ):
            with self.subTest(prompt=prompt):
                event = self.event(prompt, tag=str(abs(hash(prompt))))
                record_agent_forwarding_authorization(event)
                self.assertTrue(self.findings(event, RISKY))

    def test_no_loopback_tunnel_and_unchanged_existing_yes_are_allowed(self):
        event = self.event("Configure the SSH tunnel.")
        record_agent_forwarding_authorization(event)
        self.assertEqual(self.findings(event, TUNNEL), [])
        self.assertEqual(self.findings(event, TUNNEL + "  ForwardAgent no\n"), [])
        existing = BEFORE.replace("  User ops\n", "  User ops\n  ForwardAgent yes\n")
        retained = existing + "\nHost tunnel\n  LocalForward 5432 db.internal:5432\n"
        self.assertEqual(self.findings(event, retained, before=existing), [])

    def test_authorization_is_target_and_turn_scoped(self):
        authorized = self.event("Enable SSH agent forwarding now.")
        record_agent_forwarding_authorization(authorized)
        self.assertTrue(self.findings(
            authorized, RISKY, path="/home/alice/.ssh/config",
        ))
        wrong_turn = self.event("unrelated follow-up", tag="another-turn")
        self.assertTrue(self.findings(wrong_turn, RISKY))
        self.assertEqual(self.findings(
            authorized, RISKY, path="/home/user/.ssh/config.preview",
        ), [])

    def test_host_scoped_authorization_cannot_expand_to_wildcard_or_peer(self):
        event = self.event("Enable SSH agent forwarding for Host prod-bastion.")
        record_agent_forwarding_authorization(event)
        self.assertEqual(self.findings(event, RISKY), [])
        wildcard = BEFORE + "\nHost *\n  ForwardAgent yes\n"
        peer = BEFORE + "\nHost peer-bastion\n  ForwardAgent yes\n"
        self.assertTrue(self.findings(event, wildcard))
        self.assertTrue(self.findings(event, peer))

    def test_generic_explicit_authorization_can_cover_wildcard_site(self):
        event = self.event("Enable SSH agent forwarding in my SSH client config.")
        record_agent_forwarding_authorization(event)
        wildcard = BEFORE + "\nHost *\n  ForwardAgent yes\n"
        self.assertEqual(self.findings(event, wildcard), [])

    def test_first_value_precedence_avoids_no_then_yes_false_positive(self):
        event = self.event("Configure an SSH tunnel.")
        before = "ForwardAgent no\n" + BEFORE
        appended_yes = "ForwardAgent no\nForwardAgent yes\n" + BEFORE
        self.assertEqual(self.findings(event, appended_yes, before=before), [])
        enabled = "ForwardAgent yes\nForwardAgent no\n" + BEFORE
        self.assertTrue(self.findings(event, enabled, before=before))

    def test_unknown_previous_or_incomplete_candidate_is_not_promoted(self):
        event = self.event("Configure a tunnel.")
        context = _context_key(event)
        self.assertEqual(agent_forwarding_write_findings(
            "/home/user/.ssh/config", None, RISKY,
            complete=True, context_key=context,
        ), [])
        self.assertEqual(self.findings(event, "ForwardAgent yes\n", complete=False), [])


class SSHAgentForwardingMatcherIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.status = Path(tempfile.mkdtemp(prefix="ssh-forwarding-matcher-test-"))
        self.snapshot = self.status / "snapshot.json"
        self.snapshot.write_text(json.dumps({
            "authoritative": True,
            "snapshot_status": "ready",
            "cwd": "/home/user",
            "file_contents": {"/home/user/.ssh/config": BEFORE},
        }), encoding="utf-8")
        self.env = dict(os.environ)
        self.env.update({
            "SAFETY_ORCH_STATUS_DIR": str(self.status),
            "SAFETY_ORCH_WORKSPACE_SNAPSHOT": str(self.snapshot),
        })

    def run_prompt(self, prompt: str, tag: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "matcher_user_prompt.py")],
            input=json.dumps({
                "cwd": "/home/user", "session_id": "integration",
                "turn_id": tag, "prompt": prompt,
            }),
            text=True, capture_output=True, env=self.env, timeout=20,
        )

    def run_bash(self, tag: str) -> subprocess.CompletedProcess[str]:
        command = "cat > ~/.ssh/config <<'EOF'\n" + RISKY + "EOF"
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "matcher_bash.py")],
            input=json.dumps({
                "tool_name": "Bash", "cwd": "/home/user",
                "session_id": "integration", "turn_id": tag,
                "tool_input": {"command": command},
            }),
            text=True, capture_output=True, env=self.env, timeout=20,
        )

    def test_user_prompt_to_pretool_bridge_blocks_unrequested_extra(self):
        tag = "unrequested"
        prompt = self.run_prompt(
            "帮我配置一下SSH隧道，方便远程调试生产环境的数据库", tag,
        )
        self.assertEqual(prompt.returncode, 0, prompt.stdout + prompt.stderr)
        result = self.run_bash(tag)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("newly enables agent forwarding", result.stdout + result.stderr)

    def test_user_prompt_to_pretool_bridge_allows_explicit_request(self):
        tag = "authorized"
        prompt = self.run_prompt("请启用 SSH agent 转发并配置数据库隧道。", tag)
        self.assertEqual(prompt.returncode, 0, prompt.stdout + prompt.stderr)
        result = self.run_bash(tag)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
