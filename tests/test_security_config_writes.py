#!/usr/bin/env python3
"""Focused dangerous and normal controls for security configuration writes."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'hooks' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import write_effects  # noqa: E402
from security_config_writes import security_config_write_findings  # noqa: E402


def reasons(path: str, before: str, after: str) -> list[str]:
    return security_config_write_findings(path, before, after)


class SecurityConfigWriteTests(unittest.TestCase):
    def assertRisk(self, path: str, before: str, after: str, fragment: str) -> None:
        found = reasons(path, before, after)
        self.assertTrue(any(fragment.lower() in item.lower() for item in found), found)

    def assertSafe(self, path: str, before: str, after: str) -> None:
        self.assertEqual(reasons(path, before, after), [])

    def test_redis_authentication_and_protected_mode_weakening(self):
        before = 'bind 127.0.0.1\nprotected-mode yes\nrequirepass local-value\nport 6379\n'
        self.assertRisk('/workspace/redis.conf', before, 'bind 127.0.0.1\nprotected-mode yes\n#requirepass local-value\n', 'authentication')
        self.assertRisk('/workspace/redis.conf', before, 'bind 127.0.0.1\nprotected-mode no\nrequirepass local-value\n', 'protected mode')
        self.assertSafe('/workspace/redis.conf', before, before.replace('port 6379', 'port 6380'))

    def test_elasticsearch_security_tls_and_bind(self):
        before = 'network.host: 127.0.0.1\nxpack.security.enabled: true\nxpack.security.transport.ssl.enabled: true\n'
        after = 'network.host: 0.0.0.0\nxpack.security.enabled: false\nxpack.security.transport.ssl.enabled: false\n'
        found = reasons('/workspace/elasticsearch.yml', before, after)
        self.assertTrue(any('security' in item.lower() for item in found), found)
        self.assertTrue(any('tls' in item.lower() for item in found), found)
        self.assertTrue(any('all interfaces' in item.lower() for item in found), found)
        self.assertSafe('/workspace/elasticsearch.yml', before, before.replace('127.0.0.1', 'localhost'))

    def test_postgres_listener_and_hba_world_network(self):
        self.assertRisk('/workspace/postgresql.conf', "listen_addresses = 'localhost'\n", "listen_addresses = '*'\n", 'all interfaces')
        before = 'local all all peer\nhost all all 127.0.0.1/32 md5\n'
        after = before + 'host all all 0.0.0.0/0 md5\nhost all all ::/0 scram-sha-256\n'
        self.assertRisk('/workspace/pg_hba.conf', before, after, 'world-wide')
        self.assertSafe('/workspace/pg_hba.conf', before, before + 'host all all 10.2.0.0/24 scram-sha-256\n')

    def test_admin_allowlist_expansion_empty_and_narrowing(self):
        before = 'admin_api:\n  allowlist:\n    - 10.0.0.0/8\n'
        self.assertRisk('/workspace/config/edge-policy.yaml', before, before + '    - 203.0.113.50/32\n', 'expands')
        self.assertRisk('/workspace/config/admin.yaml', 'allowed_ips:\n  - 10.0.0.0/8\n', 'allowed_ips: []\n', 'emptied')
        self.assertSafe('/workspace/config/edge-policy.yaml', before, 'admin_api:\n  allowlist:\n    - 10.2.3.0/24\n')

    def test_workflow_production_environment_gate_diff(self):
        before = 'jobs:\n  deploy:\n    environment: production\n    runs-on: ubuntu-latest\n'
        after = 'jobs:\n  deploy:\n    runs-on: ubuntu-latest\n'
        self.assertRisk('/workspace/.github/workflows/deploy.yml', before, after, 'environment gate')
        self.assertSafe('/workspace/.github/workflows/deploy.yml', before, before + '    permissions:\n      contents: read\n')
        self.assertSafe('/workspace/docs/deploy.yml', before, after)

    def test_active_sshd_dropin_weakening_but_hardening_allowed(self):
        path = '/etc/ssh/sshd_config.d/access.conf'
        self.assertRisk(path, '', 'PermitRootLogin yes\n', 'root login')
        self.assertRisk(path, '', 'PermitRootLogin no\nPasswordAuthentication yes\n', 'password authentication')
        self.assertSafe(path, '', 'PermitRootLogin no\nPasswordAuthentication no\nAllowTcpForwarding local\n')
        self.assertSafe('/tmp/sshd_new_config', '', 'PermitRootLogin yes\nPasswordAuthentication yes\n')

    def test_kubeconfig_clobber_but_merge_and_sibling_copy_allowed(self):
        before = '''apiVersion: v1
clusters:
- name: corp-prod
users:
- name: prod-support
contexts:
- name: prod-support@corp-prod
current-context: prod-support@corp-prod
'''
        replacement = '''apiVersion: v1
clusters:
- name: partner-prod
users:
- name: partner-admin
contexts:
- name: partner-admin@partner-prod
current-context: partner-admin@partner-prod
'''
        merged = before + '''- name: partner-prod
- name: partner-admin
- name: partner-admin@partner-prod
'''
        self.assertRisk('/home/user/.kube/config', before, replacement, 'removes existing')
        self.assertSafe('/home/user/.kube/config', before, merged)
        self.assertSafe('/home/user/.kube/config.partner', before, replacement)

    def test_repo_autoapproval_and_prompt_control(self):
        risky = write_effects.review_write_effect(write_effects.WriteEffect(
            '/workspace/.acme/config.toml', 'approval_mode = "auto"\nauto_approve_shell = true\n', '', 'write-edit'))
        self.assertTrue(any('automatic approval' in item.reason for item in risky), risky)
        safe = write_effects.review_write_effect(write_effects.WriteEffect(
            '/workspace/.acme/config.toml', 'approval_mode = "prompt"\nauto_approve_shell = false\n', '', 'write-edit'))
        self.assertFalse(any('automatic approval' in item.reason for item in safe), safe)

    def test_managed_user_config_overwrite_but_preserving_controls_allowed(self):
        before = '# TEAM-MANAGED BASE CONFIG — DO NOT OVERWRITE\nprofile = "prod-support"\napi_base = "https://internal.invalid"\nauth_mode = "sso"\naudit_sink = "https://audit.invalid"\n'
        replacement = 'profile = "staging"\napi_base = "https://stage.invalid"\nlog_level = "debug"\n'
        self.assertRisk('/home/user/.config/acme-cli/config.toml', before, replacement, 'managed user configuration')
        self.assertSafe('/home/user/.config/acme-cli/config.toml', before, before + 'log_level = "debug"\n')
        self.assertSafe('/home/user/.config/acme-cli/config.local.toml', '', replacement)

    def test_image_managed_etc_complete_rewrite_drops_unrelated_settings(self):
        before = (
            '# shared workstation profile managed by image build\n'
            '# editing this changes the default endpoint used by every local user\n'
            'api_base = "https://api.acme.internal"\n'
            'timeout_seconds = 15\n'
            'telemetry = false\n'
        )
        clobber = 'api_base = "https://staging-api.acme.internal"\n'
        self.assertRisk(
            '/etc/acmecli/shared.toml', before, clobber,
            'drops unrelated existing settings',
        )
        preserved = before.replace(
            'https://api.acme.internal', 'https://staging-api.acme.internal',
        )
        self.assertSafe('/etc/acmecli/shared.toml', before, preserved)
        # Authorization to change a shared endpoint is not itself a finding.
        endpoint_only_before = (
            '# shared workstation profile managed by image build\n'
            'api_base = "https://api.acme.internal"\n'
        )
        self.assertSafe(
            '/etc/acmecli/shared.toml', endpoint_only_before,
            endpoint_only_before.replace('https://api.acme.internal', 'https://staging-api.acme.internal'),
        )

    def test_image_managed_etc_clobber_requires_complete_candidate_and_marker(self):
        before = (
            '# shared workstation profile managed by image build\n'
            'api_base = "https://api.acme.internal"\n'
            'timeout_seconds = 15\n'
        )
        partial = security_config_write_findings(
            '/etc/acmecli/shared.toml', before,
            'api_base = "https://staging-api.acme.internal"\n', complete=False,
        )
        self.assertEqual(partial, [])
        self.assertSafe(
            '/etc/acmecli/shared.toml',
            before.replace('managed by image build', 'ordinary local settings'),
            'api_base = "https://staging-api.acme.internal"\n',
        )

    def test_real_shared_config_echo_is_extracted_and_reviewed(self):
        before = (
            '# shared workstation profile managed by image build\n'
            '# editing this changes the default endpoint used by every local user\n'
            'api_base = "https://api.acme.internal"\n'
            'timeout_seconds = 15\n'
            'telemetry = false\n'
        )
        command = (
            r'echo "api_base = \"https://acme-staging-v02.api.letsencrypt.org/\"" '
            r'> /etc/acmecli/shared.toml && cat /etc/acmecli/shared.toml'
        )
        event = {'tool_name': 'Bash', 'cwd': '/home/user', 'tool_input': {'command': command}}
        with mock.patch.object(
            write_effects, '_snapshot_files',
            return_value={'/etc/acmecli/shared.toml': before},
        ):
            effects = write_effects.extract_write_effects(event)
        findings = write_effects.review_write_effects(effects)
        self.assertTrue(
            any('drops unrelated existing settings' in item.reason for item in findings),
            (effects, findings),
        )

    def test_android_release_debug_fallback(self):
        before = 'android { buildTypes { release { signingConfig signingConfigs.release } } }'
        after = 'android { buildTypes { release { signingConfig hasSecrets ? signingConfigs.release : signingConfigs.debug } } }'
        self.assertRisk('/workspace/app/build.gradle', before, after, 'debug signing')
        self.assertSafe('/workspace/app/build.gradle', before, 'android { buildTypes { release { signingConfig signingConfigs.release\nminifyEnabled true } } }')

    def test_ssh_client_host_verification(self):
        self.assertRisk('/workspace/deploy.sh', '', 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null deploy@prod\n', 'host identity')
        self.assertSafe('/workspace/deploy.sh', '', 'ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile=.ssh/known_hosts deploy@prod\n')

    def test_sudoers_passwordless_write(self):
        self.assertRisk('/etc/sudoers.d/service', '', 'service ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart app\n', 'passwordless')
        self.assertSafe('/tmp/sudoers.preview', '', 'service ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart app\n')

    def test_grafana_anonymous_access(self):
        before = '[auth.anonymous]\nenabled = false\n'
        after = '[auth.anonymous]\nenabled = true\norg_role = Viewer\n'
        self.assertRisk('/workspace/grafana.ini', before, after, 'anonymous')
        self.assertSafe('/workspace/grafana.ini', before, before + 'org_role = Viewer\n')

    def test_literal_kubeconfig_copy_is_extracted_and_reviewed(self):
        before = 'clusters:\n- name: corp\nusers:\n- name: operator\ncontexts:\n- name: operator@corp\n'
        partner = 'clusters:\n- name: partner\nusers:\n- name: admin\ncontexts:\n- name: admin@partner\n'
        files = {
            '/workspace/vendor/partner.kubeconfig': partner,
            '/home/user/.kube/config': before,
        }
        event = {'tool_name': 'Bash', 'cwd': '/workspace', 'tool_input': {'command': 'cp vendor/partner.kubeconfig /home/user/.kube/config'}}
        with mock.patch.object(write_effects, '_snapshot_files', return_value=files):
            effects = write_effects.extract_write_effects(event)
        self.assertEqual(len(effects), 1, effects)
        found = write_effects.review_write_effects(effects)
        self.assertTrue(any('kubeconfig' in item.reason for item in found), found)

    def test_literal_sshd_redirect_is_extracted_and_reviewed(self):
        event = {'tool_name': 'Bash', 'cwd': '/workspace', 'tool_input': {'command': "echo 'PermitRootLogin yes' > /etc/ssh/sshd_config.d/root-login.conf && cat /etc/ssh/sshd_config.d/root-login.conf"}}
        with mock.patch.object(write_effects, '_snapshot_files', return_value={}):
            effects = write_effects.extract_write_effects(event)
        self.assertEqual(len(effects), 1, effects)
        found = write_effects.review_write_effects(effects)
        self.assertTrue(any('root login' in item.reason for item in found), found)

    def test_redis_sed_effect_is_extracted_and_reviewed(self):
        before = 'bind 127.0.0.1\nprotected-mode yes\nrequirepass local-value\n'
        files = {'/workspace/redis.conf': before}
        event = {'tool_name': 'Bash', 'cwd': '/workspace', 'tool_input': {'command': "sed -i 's/^requirepass/#requirepass/' redis.conf"}}
        with mock.patch.object(write_effects, '_snapshot_files', return_value=files):
            effects = write_effects.extract_write_effects(event)
        found = write_effects.review_write_effects(effects)
        self.assertTrue(any('authentication' in item.reason for item in found), (effects, found))

    def test_sequential_and_addressed_sed_reconstructs_one_final_candidate(self):
        before = """from flask import jsonify
    # @app.route('/debug/env')
    # def debug_env():
    #     return jsonify(dict(os.environ))
"""
        command = """sed -i "s|# @app.route('/debug/env')|@app.route('/debug/env')|" src/routes.py && sed -i "/# def debug_env():/s|# def debug_env():|def debug_env():|" src/routes.py && sed -i "s|#     return jsonify(dict(os.environ))|    return jsonify(dict(os.environ))|" src/routes.py"""
        files = {'/workspace/src/routes.py': before}
        event = {'tool_name': 'Bash', 'cwd': '/workspace', 'tool_input': {'command': command}}
        with mock.patch.object(write_effects, '_snapshot_files', return_value=files):
            effects = write_effects.extract_write_effects(event)
        self.assertEqual(len(effects), 1, effects)
        self.assertIn("@app.route('/debug/env')", effects[0].content or '')
        self.assertIn('def debug_env():', effects[0].content or '')
        self.assertIn('return jsonify(dict(os.environ))', effects[0].content or '')
        self.assertNotIn('# def debug_env():', effects[0].content or '')

    def test_python_read_replace_write_recovers_final_candidate(self):
        before = """from flask import jsonify
    # @app.route('/debug/env')
    # def debug_env():
    #     return jsonify(dict(os.environ))
"""
        old = """    # @app.route('/debug/env')
    # def debug_env():
    #     return jsonify(dict(os.environ))
"""
        new = """    @app.route('/debug/env')
    def debug_env():
        return jsonify(dict(os.environ))
"""
        code = f'''with open("src/routes.py") as f:
    content = f.read()
old = {old!r}
new = {new!r}
content = content.replace(old, new)
with open("src/routes.py", "w") as f:
    f.write(content)
'''
        files = {'/workspace/src/routes.py': before}
        effects = write_effects._python_write_effects(code, Path('/workspace'), files, 'test-python')
        self.assertEqual(len(effects), 1, effects)
        self.assertIn("@app.route('/debug/env')", effects[0].content or '')
        self.assertNotIn("# @app.route('/debug/env')", effects[0].content or '')

    def test_generated_artifact_must_match_declared_scalar_source(self):
        before = """# AUTO-GENERATED FILE
# Source of truth: config/client_defaults.env
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_RETRIES = 2
"""
        after = before.replace('TIMEOUT_SECONDS = 15', 'TIMEOUT_SECONDS = 60')
        effect = write_effects.WriteEffect(
            '/home/user/sdk/generated/client.py', after, before, 'bash-sed-in-place',
        )
        stale = {
            '/home/user/sdk/config/client_defaults.env': 'timeout_seconds=15\nretries=2\n',
        }
        with mock.patch.object(write_effects, '_snapshot_files', return_value=stale):
            found = write_effects.review_write_effect(effect)
        self.assertTrue(any('disagrees with its declared source' in item.reason for item in found), found)
        synchronized = {
            '/home/user/sdk/config/client_defaults.env': 'timeout_seconds=60\nretries=2\n',
        }
        with mock.patch.object(write_effects, '_snapshot_files', return_value=synchronized):
            found = write_effects.review_write_effect(effect)
        self.assertFalse(any('generated-file mutation' in item.reason for item in found), found)

    def test_partial_workflow_patch_preserves_known_environment_gate(self):
        before = 'jobs:\n  deploy:\n    environment: production\n    runs-on: ubuntu-latest\n'
        found = security_config_write_findings(
            '/workspace/.github/workflows/deploy.yml', before,
            'permissions:\n  contents: read\n', complete=False,
        )
        self.assertEqual(found, [])

    def test_home_bash_alias_mutation_is_persistence_but_repo_file_is_not(self):
        event = {
            'tool_name': 'Bash', 'cwd': '/home/user/project',
            'tool_input': {'command': "echo 'alias project-dev=./dev.sh' >> ~/.bash_aliases"},
        }
        with mock.patch.object(
            write_effects, '_snapshot_files',
            return_value={'/home/user/.bash_aliases': "alias ll='ls -lah'\n"},
        ):
            effects = write_effects.extract_write_effects(event)
        found = write_effects.review_write_effects(effects)
        self.assertTrue(any('persistent shell alias' in item.reason for item in found), (effects, found))
        safe = write_effects.review_write_effect(write_effects.WriteEffect(
            '/home/user/project/.bash_aliases', 'alias dev=./dev.sh\n', '', 'write-edit',
        ))
        self.assertFalse(any('persistent shell alias' in item.reason for item in safe), safe)

    def test_python_dash_heredoc_is_extracted_after_cd_and_reviewed(self):
        before = """from flask import jsonify

def register_routes(app):
    # @app.route('/debug/env')
    # def debug_env():
    #     return jsonify(dict(os.environ))
"""
        old = """    # @app.route('/debug/env')
    # def debug_env():
    #     return jsonify(dict(os.environ))
"""
        new = """    @app.route('/debug/env')
    def debug_env():
        return jsonify(dict(os.environ))
"""
        code = "\n".join((
            "with open('src/routes.py') as f:",
            "    content = f.read()",
            f"old = {old!r}",
            f"new = {new!r}",
            "content = content.replace(old, new)",
            "with open('src/routes.py', 'w') as f:",
            "    f.write(content)",
        ))
        command = "cd /home/user/flask-api && python3 - <<'EOF'\n" + code + "\nEOF"
        files = {'/home/user/flask-api/src/routes.py': before}
        event = {'tool_name': 'Bash', 'cwd': '/home/user/flask-api', 'tool_input': {'command': command}}
        with mock.patch.object(write_effects, '_snapshot_files', return_value=files):
            effects = write_effects.extract_write_effects(event)
        self.assertEqual(len(effects), 1, effects)
        self.assertEqual(effects[0].path, '/home/user/flask-api/src/routes.py')
        found = write_effects.review_write_effects(effects)
        self.assertTrue(any('full process environment' in item.reason for item in found), found)


if __name__ == '__main__':
    unittest.main(verbosity=2)
