import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks/scripts'))
from sensitive_data import sensitive_command_risk


class DirectoryServerPrivacyTests(unittest.TestCase):
    def risk(self, command, files=None):
        return sensitive_command_risk(command, {'cwd': '/work/project', 'workspace_snapshot': {'file_contents': files if files is not None else {'/work/project/.env': 'API_KEY=fixture', '/work/project/public/index.html': 'hello'}}})

    def test_public_server_exposes_snapshot_credentials(self):
        for command in ('python3 -m http.server 8000 > /dev/null 2>&1 &', 'cd /work/project && python3 -m http.server 8080 &', 'python3 -u -m http.server --bind 0.0.0.0', 'python3 -m http.server --bind=:: --directory=.'):
            with self.subTest(command=command):
                self.assertTrue(self.risk(command))

    def test_loopback_public_subdirectory_and_inspection_are_allowed(self):
        for command in ('python3 -m http.server --bind 127.0.0.1', 'python3 -m http.server -b ::1', 'python3 -m http.server --bind=localhost', 'python3 -m http.server --directory public', 'cd public && python3 -m http.server', 'python3 -m http.server --help', 'echo "python3 -m http.server"', 'ps aux | grep http.server'):
            with self.subTest(command=command):
                self.assertFalse(self.risk(command))
        self.assertFalse(self.risk('python3 -m http.server', {'/work/project/index.html': 'public'}))

    def test_directory_override_does_not_borrow_original_root(self):
        self.assertFalse(self.risk('python3 -m http.server -d /srv/public'))
        self.assertTrue(self.risk('cd /srv/public && python3 -m http.server -d /work/project'))


if __name__ == '__main__':
    unittest.main()
