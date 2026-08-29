import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
MATCHER = BUNDLE / "hooks" / "scripts" / "matcher_posttool.py"


class MatcherPostToolTests(unittest.TestCase):
    def run_matcher(self, output: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["SAFETY_ORCH_STATUS_DIR"] = tmp
            return subprocess.run(
                [sys.executable, str(MATCHER)],
                input=json.dumps({"tool_response": output}),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

    def test_df_inode_columns_are_not_credit_card_data(self):
        result = self.run_matcher(
            "Filesystem Inodes IUsed IFree IUse% Mounted on\n"
            "overlay 30179328 1077273 29102055 4% /"
        )

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
        self.assertNotIn("redact-output-pii", result.stdout)
        self.assertNotIn("REDACTED-PII", result.stdout)

    def test_formatted_credit_card_is_still_redacted(self):
        result = self.run_matcher("card: 4111 1111 1111 1111")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("redact-output-pii", result.stdout)
        self.assertIn("REDACTED-PII-CREDIT_CARD", result.stdout)


if __name__ == "__main__":
    unittest.main()
