import unittest
from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parents[1] / "hooks/scripts"
sys.path.insert(0, str(SCRIPTS))

from ported_atom_checks import parse_install_packages


def parsed(command: str) -> list[tuple[str, str, str]]:
    return [
        (package.ecosystem, package.name, package.version)
        for package in parse_install_packages(command)
    ]


class InstallPackageParsingTests(unittest.TestCase):
    def test_cat_heredoc_yaml_is_data_not_an_install(self):
        command = """cat > .github/workflows/ci.yml << 'EOF'
name: CI
jobs:
  test:
    steps:
      - name: Install dependencies
        run: |
          pip install pytest pytest-cov
      - name: Run tests with coverage
        run: pytest --cov=src tests/
EOF"""
        self.assertEqual(parsed(command), [])

    def test_echo_and_printf_documentation_are_not_installs(self):
        for command in (
            "echo pip install imaginary-package > instructions.txt",
            "printf '%s\\n' 'npm install imaginary-package'",
            "echo 'python -m pip install imaginary-package'",
        ):
            with self.subTest(command=command):
                self.assertEqual(parsed(command), [])

    def test_physical_lines_do_not_extend_install_arguments(self):
        command = "pip install pytest\n- name: Run tests with coverage\nrun: pytest tests/"
        self.assertEqual(parsed(command), [("PyPI", "pytest", "")])

    def test_direct_wrapped_and_chained_installs_remain_detected(self):
        cases = {
            "pip install requests==2.32.0": [("PyPI", "requests", "2.32.0")],
            "sudo env MODE=build python3 -m pip install pyyaml": [("PyPI", "pyyaml", "")],
            "sudo MODE=build pip install requests": [("PyPI", "requests", "")],
            "command -- npm install lodash@4": [("npm", "lodash", "4")],
            "timeout 30 pip3 install urllib3": [("PyPI", "urllib3", "")],
            "cargo add serde@1 && go get example.com/tool@v1.2.3": [
                ("crates.io", "serde", "1"), ("Go", "example.com/tool", "1.2.3")
            ],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(parsed(command), expected)

    def test_shell_c_install_payloads_remain_detected(self):
        for command in (
            "bash -c 'pip install requests'",
            "env MODE=build sh -lc 'python3 -m pip install requests'",
            "sudo bash -c 'npm install lodash'",
        ):
            with self.subTest(command=command):
                result = parsed(command)
                self.assertEqual(len(result), 1)
                self.assertIn(result[0][1], {"requests", "lodash"})

    def test_shell_input_heredoc_is_executable_source(self):
        cases = {
            "bash <<'SH'\npip install requests\nSH": [("PyPI", "requests", "")],
            "cat <<'SH' | bash\nnpm install lodash\nSH": [("npm", "lodash", "")],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(parsed(command), expected)

    def test_named_script_heredoc_remains_data(self):
        command = "bash scripts/import-data.sh <<'DATA'\npip install imaginary-package\nDATA"
        self.assertEqual(parsed(command), [])

    def test_line_continuation_is_one_real_install(self):
        self.assertEqual(
            parsed("python3 -m pip install \\\n  requests==2.32.0"),
            [("PyPI", "requests", "2.32.0")],
        )


if __name__ == "__main__":
    unittest.main()
