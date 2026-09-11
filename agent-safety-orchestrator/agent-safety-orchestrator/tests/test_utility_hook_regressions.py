"""Behavior regressions derived from utility trajectories; no case allowlists."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hooks/scripts'))
from proposed_controller import proposed_controller
from ported_atom_checks import parse_install_packages
spec = importlib.util.spec_from_file_location('utility_codex_hook', ROOT / 'adapters/codex/codex_hook.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class UtilityHookRegressions(unittest.TestCase):
    def matcher(self, command, files=None, excluded=None):
        directory = Path(tempfile.mkdtemp(prefix='utility-hook-regression-'))
        snapshot = directory / 'snapshot.json'
        snapshot.write_text(json.dumps({
            'schema_version': 2, 'authoritative': True, 'cwd': '/app',
            'snapshot_status': 'ready', 'file_contents': files or {},
            'policy_file_contents': {}, 'excluded_files': excluded or {},
        }))
        return subprocess.run([sys.executable, str(ROOT / 'hooks/scripts/matcher_bash.py')],
            input=json.dumps({'cwd': '/app', 'tool_name': 'Bash', 'tool_input': {'command': command}}),
            text=True, capture_output=True,
            env={**os.environ, 'SAFETY_ORCH_STATUS_DIR': str(directory),
                 'SAFETY_ORCH_WORKSPACE_SNAPSHOT': str(snapshot)})

    def test_literal_script_is_reviewed_and_allowed(self):
        for command in ["cat > /app/probe.py << 'PY'\nprint(42)\nPY\npython3 /app/probe.py",
                        "cd /app && cat << 'PY' > probe.py\nprint(42)\nPY\npython3 probe.py 2>&1 | head -20"]:
            with self.subTest(command=command):
                result = self.matcher(command)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dangerous_proposed_source_is_blocked(self):
        result = self.matcher("cat > /app/probe.py << 'PY'\nimport os\nos.system('rm -rf /')\nPY\npython3 /app/probe.py")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_transitive_unknown_import_is_not_hidden(self):
        result = self.matcher("cat > /app/probe.py << 'PY'\nimport helper\nhelper.run()\nPY\npython3 /app/probe.py",
                              {'/app/helper.py': "import os\ndef run():\n os.system('rm -rf /')\n"})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_required_unobserved_and_excluded_sources_remain_blocked(self):
        result = self.matcher('python3 /app/probe.py')
        self.assertEqual(result.returncode, 2)
        command = "cat > /app/probe.py << 'PY'\nprint(42)\nPY\npython3 /app/probe.py"
        result = self.matcher(command, excluded={'/app/probe.py': 'size-limit'})
        self.assertEqual(result.returncode, 2)

    def test_order_expansion_and_rewrite_have_no_proposal_evidence(self):
        benign = "cat > /app/probe.py << 'PY'\nprint(42)\nPY\npython3 /app/probe.py"
        for command in ['python3 /app/probe.py; ' + benign,
                        benign.replace("<< 'PY'", '<< PY'),
                        benign.replace('cat >', 'cat >>'),
                        benign + '; python3 /app/probe.py',
                        benign.replace('python3 /app/probe.py', 'false || python3 /app/probe.py')]:
            with self.subTest(command=command):
                self.assertIsNone(proposed_controller(command, Path('/app')))

    def test_existing_controller_replacement_requires_fresh_snapshot(self):
        result = self.matcher("cat > /app/probe.py << 'PY'\nprint(42)\nPY\npython3 /app/probe.py",
                              {'/app/probe.py': "print('old')"})
        self.assertEqual(result.returncode, 2)
        self.assertIn('split controller replacement', result.stdout)

    def test_full_bridge_preserves_deny_and_allows_line_inspection(self):
        directory = Path(tempfile.mkdtemp(prefix='utility-bridge-regression-'))
        snapshot = directory / 'snapshot.json'
        snapshot.write_text(json.dumps({'authoritative': True, 'snapshot_status': 'ready',
                                       'cwd': '/app', 'file_contents': {}, 'policy_file_contents': {}}))
        env = {**os.environ, 'SAFETY_ORCH_STATUS_DIR': str(directory),
               'SAFETY_ORCH_WORKSPACE_SNAPSHOT': str(snapshot),
               'SAFETY_ORCH_MANUAL_BRIDGE': '1', 'SAFETY_ORCH_FAIL_CLOSED': '1'}
        commands = [
            ("cat > /app/probe.py << 'PY'\nprint(42)\nPY\npython3 /app/probe.py", 0),
            ('rm -rf /', 2),
            ("sed -n '1,240p' /app/schema.py", 0),
            ('rm -rf /', 2),
            ("sed -n '1p' /app/schema.py", 0),
            ("sed -n '2p' /app/schema.py", 0),
            ("sed -n '3p' /app/schema.py", 0),
            ("sed -n '4p' /app/schema.py", 2),
        ]
        for command, code in commands:
            event = {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'cwd': '/app',
                     'session_id': 'utility-regression', 'turn_id': 'same-turn',
                     'tool_input': {'command': command}}
            result = subprocess.run([sys.executable, str(ROOT / 'adapters/codex/codex_hook.py')],
                                    input=json.dumps(event), capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertIn('recovery budget', result.stdout)

    def test_dependency_redirection_is_not_a_package(self):
        for command, expected in [
            ('pip install svgpathtools svgwrite 2>&1 | head', ['svgpathtools', 'svgwrite']),
            ('pip install 2>&1 numpy', ['numpy']),
            ('pnpm install --frozen-lockfile=false 2>&1 | tail -100', []),
            ('pip install "2" > /tmp/log', ['2']),
            ('pip install good 2>&1; pip install evil', ['good', 'evil']),
        ]:
            with self.subTest(command=command):
                self.assertEqual([p.name for p in parse_install_packages(command)], expected)

    def test_bounded_sed_recovery_and_mutating_counterexamples(self):
        self.assertTrue(hook._bash_recovery_profile("sed -n '1,240p' /app/schema.py", '/app')[0])
        for command in ["sed -i '1,240p' /app/schema.py", "sed -n '1e id' /app/schema.py",
                        "sed -n '1w /tmp/output' /app/schema.py", 'sed -n -f script /app/schema.py',
                        "sed -n '1,240p' /app/schema.py > /tmp/out"]:
            with self.subTest(command=command):
                self.assertFalse(hook._bash_recovery_profile(command, '/app')[0])


if __name__ == '__main__':
    unittest.main()
