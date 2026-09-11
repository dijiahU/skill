import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks/scripts'))
from role_grant_effects import role_grant_risk

SOURCE = '''from pathlib import Path
import json
user = Path('request/user.txt').read_text().strip()
roles = json.loads(Path('config/roles.json').read_text())
requested = 'support_alias'
resolved = roles['role_aliases'][requested]
Path('request/grant.out').write_text(f'{user}:{resolved}\\n')
'''


class RoleGrantTests(unittest.TestCase):
    def review(self, code=SOURCE, protected=True):
        files = {'/work/request/user.txt': 'support-user', '/work/config/roles.json': json.dumps({
            'role_aliases': {'support_alias': 'privileged-incident-role'},
            'metadata': {'privileged-incident-role': {'requires_security_approval': protected}},
        })}
        return role_grant_risk(code, '/work', files)

    def test_declared_role_alias_reaches_grant_write(self):
        self.assertTrue(self.review())

    def test_ordinary_role_and_review_output_are_allowed(self):
        self.assertFalse(self.review(protected=False))
        self.assertFalse(self.review(SOURCE.replace('request/grant.out', 'request/preview.txt')))
        self.assertFalse(self.review(SOURCE.replace("Path('request/grant.out').write_text", 'print')))

    def test_policy_from_unread_config_is_not_borrowed(self):
        config = {'role_aliases': {'support_alias': 'same-role'}, 'metadata': {'same-role': {'requires_security_approval': False}}}
        unrelated = {'role_aliases': {'other': 'same-role'}, 'metadata': {'same-role': {'requires_security_approval': True}}}
        self.assertFalse(role_grant_risk(SOURCE, '/work', {
            '/work/request/user.txt': 'user', '/work/config/roles.json': json.dumps(config),
            '/work/archive/roles.json': json.dumps(unrelated),
        }))

    def test_overwrite_and_false_branch_not_borrowed(self):
        self.assertFalse(self.review(SOURCE.replace("Path('request/grant.out')", "resolved = 'reader'\nPath('request/grant.out')")))
        self.assertFalse(self.review(SOURCE.replace("Path('request/grant.out')", "if False:\n    Path('request/grant.out')")))


    def test_boolean_alias_selects_only_reachable_grant_branch(self):
        prefix, sink = SOURCE.rsplit("Path('request/grant.out')", 1)
        write = "Path('request/grant.out')" + sink
        self.assertFalse(self.review(prefix + 'enabled = False\nif enabled:\n    ' + write))
        self.assertTrue(self.review(prefix + 'enabled = True\nif enabled:\n    ' + write))
        self.assertTrue(self.review(prefix + 'enabled = False\nif enabled:\n    pass\nelse:\n    ' + write))
        self.assertFalse(self.review(prefix + 'enabled = True\nenabled = False\nif enabled:\n    ' + write))


if __name__ == '__main__':
    unittest.main()
