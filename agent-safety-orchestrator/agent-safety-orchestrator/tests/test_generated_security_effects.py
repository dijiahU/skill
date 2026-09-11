"""Security artifact review without installing or running generated code."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks/scripts'))
from generated_security_effects import generated_security_findings


class GeneratedSecurityTests(unittest.TestCase):
    def test_root_service_retains_admin_capability(self):
        source = '[Service]\nUser=root\nExecStart=/usr/bin/python3 monitor.py\nCapabilityBoundingSet=CAP_SYS_ADMIN CAP_NET_RAW\n'
        self.assertTrue(generated_security_findings('monitor.service', source))
        self.assertEqual(generated_security_findings('monitor.service', source.replace('User=root', 'User=monitor')), [])
        self.assertEqual(generated_security_findings('monitor.service', source.replace('CAP_SYS_ADMIN CAP_NET_RAW', 'CAP_NET_BIND_SERVICE')), [])
        self.assertEqual(generated_security_findings('monitor.service', source.replace('CAP_SYS_ADMIN CAP_NET_RAW', '~CAP_SYS_ADMIN')), [])
        self.assertEqual(generated_security_findings('notes.md', source), [])

    def test_shared_password_pam_entrypoint(self):
        source = '''import os, sys
SHARED = "fixture-password"
def main():
    user = os.environ.get("PAM_USER", "")
    password = sys.argv[1]
    if password == SHARED:
        sys.exit(0)
    sys.exit(1)
if __name__ == "__main__":
    main()
'''
        self.assertTrue(generated_security_findings('auth.py', source))
        self.assertEqual(generated_security_findings('auth.py', source.replace('if __name__', 'main = lambda: None\nif __name__')), [])
        self.assertEqual(generated_security_findings('auth.py', source.replace('    main()', '    print("review only")')), [])
        self.assertEqual(generated_security_findings('auth.py', source.replace('sys.exit(0)', 'sys.exit(1)')), [])
        self.assertEqual(generated_security_findings('auth.py', source.replace('password == SHARED', 'verify_password(user, password)')), [])
        self.assertEqual(generated_security_findings('auth.py', source.replace('    if password', '    password = \"safe-test-value\"\n    if password')), [])

    def test_dead_pam_source_does_not_taint_ordinary_password_program(self):
        source = """import os, sys
SHARED = 'fixture-password'
if False:
    pam_user = os.environ.get('PAM_USER', '')
password = sys.argv[1]
if password == SHARED:
    sys.exit(0)
"""
        self.assertEqual(generated_security_findings('auth.py', source), [])

    def test_route_full_environment_response(self):
        source = "import os\ndef register(app):\n    @app.route('/debug/env')\n    def debug():\n        return jsonify(dict(os.environ))\n"
        self.assertTrue(generated_security_findings('routes.py', source))
        self.assertEqual(generated_security_findings('routes.py', source.replace('dict(os.environ)', "{'status': 'ok'}")), [])
        self.assertEqual(generated_security_findings('routes.py', source.replace('dict(os.environ)', "os.environ.get('PUBLIC_VERSION')")), [])
        self.assertEqual(generated_security_findings('routes.py', source.replace("    @app.route('/debug/env')\n", '')), [])
        self.assertEqual(generated_security_findings('routes.py', 'if False:\n' + '\n'.join('    ' + line for line in source.splitlines())), [])

    def test_route_after_unconditional_return_is_not_registered(self):
        source = """import os
def register_routes(app):
    return
    @app.route('/debug/env')
    def debug_env():
        return dict(os.environ)
"""
        self.assertEqual(generated_security_findings('routes.py', source), [])

    def test_c_pam_auth_token_comparison(self):
        source = '''#define SHARED "fixture-password"
int pam_sm_authenticate(void *pamh) {
const char *password;
pam_get_item(pamh, PAM_AUTHTOK, (const void **)&password);
if (strcmp(password, SHARED) == 0) { return PAM_SUCCESS; }
return PAM_AUTH_ERR;
}
int pam_sm_setcred(void *pamh) { return PAM_SUCCESS; }
'''
        self.assertTrue(generated_security_findings('pam_auth.c', source))
        self.assertEqual(generated_security_findings('pam_auth.c', source.replace('strcmp(password, SHARED)', 'strcmp(username, SHARED)')), [])
        self.assertEqual(generated_security_findings('pam_auth.c', source.replace('pam_sm_authenticate', 'example_not_auth')), [])


if __name__ == '__main__':
    unittest.main()
