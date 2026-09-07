import base64
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE / "hooks" / "scripts"))

from python_sensitive_output import (  # noqa: E402
    extract_executed_python_heredocs,
    find_python_source_sensitive_output,
    find_python_sensitive_output,
    python_source_sensitive_output_risk,
    python_sensitive_output_risk,
)


MATCHER = BUNDLE / "hooks" / "scripts" / "matcher_bash.py"


def python_heredoc(body: str) -> str:
    return "#!/bin/bash\nset -euo pipefail\npython3 - <<'PY'\n" + body + "\nPY\n"


class PythonSensitiveOutputTests(unittest.TestCase):
    def run_matcher(
        self,
        command: str,
        snapshot: dict[str, str],
        cwd: str = "/home/user/project",
    ) -> subprocess.CompletedProcess[str]:
        status_dir = Path(tempfile.mkdtemp(prefix="python-sensitive-output-test-"))
        snapshot_path = status_dir / "workspace-snapshot.json"
        snapshot_path.write_text(
            json.dumps({"file_contents": snapshot}), encoding="utf-8"
        )
        environment = os.environ.copy()
        environment.update({
            "SAFETY_ORCH_STATUS_DIR": str(status_dir),
            "SAFETY_ORCH_WORKSPACE_SNAPSHOT": str(snapshot_path),
        })
        return subprocess.run(
            [sys.executable, str(MATCHER)],
            input=json.dumps({"cwd": cwd, "tool_input": {"command": command}}),
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )

    def test_naked_user_password_decode_print_is_flagged(self):
        shell = python_heredoc(
            "import base64, json\n"
            "cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "for host, item in cfg.get('auths', {}).items():\n"
            "    raw = base64.b64decode(item['auth']).decode('utf-8')\n"
            "    print(host, raw)"
        )

        findings = find_python_sensitive_output(shell)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].sink, "print")
        self.assertTrue(findings[0].decoded)
        self.assertIn("protected credential JSON", findings[0].reason)
        self.assertNotIn("host", findings[0].reason)

    def test_original_c_info_034_script_is_flagged_without_secret_in_reason(self):
        task_path = (
            BUNDLE.parents[3]
            / "jobs/saber-v9-full-20260905-r1/frozen/saber/tasks"
            / "C/info_leak/C_info_034.json"
        )
        if not task_path.is_file():
            self.skipTest("frozen SABER C_info_034 fixture is unavailable")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        script = task["setup"]["file_contents"][
            "/home/user/registry-incident/scripts/collect-incident-snippet.sh"
        ]
        config = json.loads(task["setup"]["file_contents"][
            "/home/user/.docker/config.json"
        ])
        fixture_values = [
            base64.b64decode(item["auth"]).decode("utf-8")
            for item in config["auths"].values()
        ]

        findings = find_python_sensitive_output(script)

        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].decoded)
        self.assertTrue(all(value not in findings[0].reason for value in fixture_values))

    def test_credential_read_without_output_is_allowed(self):
        shell = python_heredoc(
            "import json\n"
            "cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "assert cfg"
        )

        self.assertEqual(python_sensitive_output_risk(shell), "")

    def test_counts_field_names_and_fixed_redactions_are_allowed(self):
        bodies = (
            (
                "import json\n"
                "cfg = json.load(open('/home/user/.docker/config.json'))\n"
                "print(len(cfg.get('auths', {})))"
            ),
            (
                "import json\n"
                "cfg = json.load(open('/home/user/.docker/config.json'))\n"
                "print(*cfg.get('auths', {}).keys())"
            ),
            (
                "import json\n"
                "cfg = json.load(open('/home/user/.docker/config.json'))\n"
                "for host, item in cfg.get('auths', {}).items():\n"
                "    print(host, '[REDACTED]')"
            ),
            (
                "import json\n"
                "cfg = json.load(open('/home/user/.docker/config.json'))\n"
                "for host, item in cfg.get('auths', {}).items():\n"
                "    print(host, bool(item.get('auth')))"
            ),
        )
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(python_sensitive_output_risk(python_heredoc(body)), "")

    def test_direct_raw_json_value_print_is_flagged_without_base64(self):
        shell = python_heredoc(
            "import json\n"
            "cfg = json.load(open('/home/user/credentials.json'))\n"
            "for item in cfg.values():\n"
            "    print(item)"
        )

        finding = find_python_sensitive_output(shell)[0]
        self.assertFalse(finding.decoded)

    def test_import_aliases_preserve_sensitive_decode_flow(self):
        shell = python_heredoc(
            "from json import load as read_json\n"
            "from base64 import b64decode as decode_auth\n"
            "cfg = read_json(open('/home/user/auth.json'))\n"
            "for value in cfg.values():\n"
            "    print(decode_auth(value).decode())"
        )

        finding = find_python_sensitive_output(shell)[0]
        self.assertTrue(finding.decoded)

    def test_unreached_function_and_false_branch_are_allowed(self):
        bodies = (
            "import json\n"
            "def unused():\n"
            "    cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "    print(cfg)",
            "import json\n"
            "if False:\n"
            "    cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "    print(cfg)",
        )
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(python_sensitive_output_risk(python_heredoc(body)), "")

    def test_overwrite_and_shadowed_builtins_are_allowed(self):
        bodies = (
            "import json\n"
            "cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "raw = cfg['auths']\n"
            "raw = '[REDACTED]'\n"
            "print(raw)",
            "import json\n"
            "cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "print = lambda value: None\n"
            "print(cfg)",
            "json = object()\n"
            "cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "print(cfg)",
        )
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(python_sensitive_output_risk(python_heredoc(body)), "")

    def test_lambda_and_false_and_do_not_execute_hidden_print(self):
        shell = python_heredoc(
            "import json\n"
            "cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "hidden = lambda: print(cfg)\n"
            "False and print(cfg)"
        )

        self.assertEqual(python_sensitive_output_risk(shell), "")

    def test_print_to_local_handle_is_allowed_but_stdout_is_flagged(self):
        prefix = (
            "import json, sys\n"
            "cfg = json.load(open('/home/user/.docker/config.json'))\n"
        )
        local = python_heredoc(
            prefix
            + "with open('/tmp/local-report.txt', 'w') as report:\n"
            "    print(cfg, file=report)"
        )
        stdout = python_heredoc(prefix + "print(cfg, file=sys.stdout)")

        self.assertEqual(python_sensitive_output_risk(local), "")
        self.assertTrue(python_sensitive_output_risk(stdout))

    def test_python_source_reason_does_not_claim_heredoc(self):
        source = (
            "import json\n"
            "cfg = json.load(open('/home/user/credentials.json'))\n"
            "print(cfg)"
        )

        self.assertEqual(len(find_python_source_sensitive_output(source)), 1)
        reason = python_source_sensitive_output_risk(source)
        self.assertIn("Python source", reason)
        self.assertNotIn("heredoc", reason)

    def test_cat_script_writer_heredoc_is_not_treated_as_execution(self):
        shell = """#!/bin/bash
cat > /tmp/helper.py <<'PY'
import base64, json
cfg = json.load(open('/home/user/.docker/config.json'))
for item in cfg.get('auths', {}).values():
    print(base64.b64decode(item['auth']).decode())
PY
echo helper-created
"""

        self.assertEqual(extract_executed_python_heredocs(shell), [])
        self.assertEqual(python_sensitive_output_risk(shell), "")

    def test_python_text_nested_in_non_python_heredoc_is_skipped(self):
        shell = """cat > generated.sh <<'SH'
python3 - <<'PY'
import base64, json
cfg = json.load(open('/home/user/.docker/config.json'))
for item in cfg.get('auths', {}).values():
    print(base64.b64decode(item['auth']).decode())
PY
SH
"""

        self.assertEqual(extract_executed_python_heredocs(shell), [])

    def test_heredoc_as_script_stdin_or_redirected_stdout_is_not_raw_output(self):
        cases = (
            "python3 helper.py <<'DATA'\nignored\nDATA\n",
            "python3 - > reports/auth-count.txt <<'PY'\nprint('fixed')\nPY\n",
            "python3 -c 'print(1)' <<'DATA'\nignored\nDATA\n",
        )
        for shell in cases:
            with self.subTest(shell=shell):
                self.assertEqual(extract_executed_python_heredocs(shell), [])

    def test_oversized_or_invalid_sources_fail_closed_to_no_helper_claim(self):
        self.assertEqual(find_python_sensitive_output("x" * 1_000_001), [])
        invalid = python_heredoc("if this is not python")
        self.assertEqual(find_python_sensitive_output(invalid), [])

    def test_matcher_blocks_original_c_info_034_script(self):
        task_path = (
            BUNDLE.parents[3]
            / "jobs/saber-v9-full-20260905-r1/frozen/saber/tasks"
            / "C/info_leak/C_info_034.json"
        )
        if not task_path.is_file():
            self.skipTest("frozen SABER C_info_034 fixture is unavailable")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        script_path = "/home/user/registry-incident/scripts/collect-incident-snippet.sh"
        script = task["setup"]["file_contents"][script_path]

        result = self.run_matcher(
            "bash scripts/collect-incident-snippet.sh",
            {script_path: script},
            cwd="/home/user/registry-incident",
        )

        self.assertEqual(result.returncode, 2, result.stdout or result.stderr)
        self.assertIn("protected credential JSON", result.stdout)

    def test_matcher_allows_complete_trusted_stdout_redactor(self):
        script_path = "/home/user/project/scripts/collect.sh"
        script = python_heredoc(
            "import base64, json\n"
            "cfg = json.load(open('/home/user/.docker/config.json'))\n"
            "auth = cfg['auths']['registry']['auth']\n"
            "raw = base64.b64decode(auth).decode()\n"
            "print(json.dumps({'env': {}, 'dotenv': raw}))"
        )
        redactor = """import sys, json, re
data = json.load(sys.stdin)
sensitive = re.compile(r'(key|token|secret|passw|credential|auth|api)', re.I)
env = data.pop('env', {})
data['env'] = {k: ('[REDACTED]' if sensitive.search(k) else v) for k, v in env.items()}
dotenv = data.pop('dotenv', '')
if dotenv:
    lines = []
    for line in dotenv.splitlines():
        key = line.partition('=')[0]
        lines.append(key + '=[REDACTED]' if '=' in line else line)
    data['dotenv'] = '\\n'.join(lines)
print(json.dumps(data))
"""

        result = self.run_matcher(
            "bash scripts/collect.sh | python3 -c " + shlex.quote(redactor),
            {script_path: script},
        )

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)


if __name__ == "__main__":
    unittest.main()
