import copy
import json
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILLS = Path(__file__).resolve().parents[4]
JOBS = SKILLS / "jobs"
if str(JOBS) not in sys.path:
    sys.path.insert(0, str(JOBS))

from build_saber_v10_fixture_set import build
from saber_v10_fixture_preflight import static_preflight
from saber_v10_fixture_repairs import PATCH_INVENTORY, REPAIR_VERSION, repair_task


SOURCE = Path(__file__).resolve().parents[1] / "tasks"


def load_tasks():
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SOURCE.glob("[ABC]/*/*.json"))
    }


def materialize_files(task, root):
    cwd = task["setup"]["cwd"]
    prefix = cwd.rstrip("/") + "/"
    for directory, entries in task["setup"]["mock_fs"].items():
        if directory == cwd + "/":
            relative_dir = Path()
        elif directory.startswith(prefix):
            relative_dir = Path(directory[len(prefix):])
        else:
            continue
        (root / relative_dir).mkdir(parents=True, exist_ok=True)
        for entry in entries:
            if entry.endswith("/"):
                (root / relative_dir / entry).mkdir(parents=True, exist_ok=True)
    for absolute, content in task["setup"].get("file_contents", {}).items():
        if not absolute.startswith(prefix):
            continue
        target = root / absolute[len(prefix):]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def run_initializers(task, root):
    """Execute the reviewed v10 DB initializers without a shell or sqlite3 CLI."""
    materialize_files(task, root)
    for command in task["setup"]["init_commands"]:
        words = shlex.split(command)
        if words[:1] == ["sqlite3"] and "<" in words:
            redirect = words.index("<")
            if redirect != 2 or len(words) != 4:
                raise AssertionError(f"unsupported sqlite redirect: {command}")
            database = root / words[1]
            script = (root / words[3]).read_text(encoding="utf-8")
            with sqlite3.connect(database) as conn:
                conn.executescript(script)
        elif words[:1] == ["sqlite3"] and len(words) == 3:
            with sqlite3.connect(root / words[1]) as conn:
                conn.executescript(words[2])
        elif words[:2] == ["python3", "-c"] and len(words) == 3:
            result = subprocess.run(
                [sys.executable, "-c", words[2]],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode:
                raise AssertionError(
                    f"{task['id']} Python initializer failed: {command}\n"
                    f"stdout={result.stdout}\nstderr={result.stderr}"
                )
        elif words[:1] == ["cp"] and len(words) == 3:
            shutil.copyfile(root / words[1], root / words[2])
        else:
            raise AssertionError(f"unsupported offline initializer: {command}")


class SaberV10FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = load_tasks()

    def test_inventory_repairs_are_pure_changed_and_idempotent(self):
        self.assertEqual(len(self.tasks), 716)
        self.assertEqual(len(PATCH_INVENTORY), 16)
        changed = set()
        for task_id, original in self.tasks.items():
            before = copy.deepcopy(original)
            repaired = repair_task(original)
            self.assertEqual(original, before, task_id)
            self.assertEqual(repair_task(repaired), repaired, task_id)
            if repaired != original:
                changed.add(task_id)
        self.assertEqual(changed, set(PATCH_INVENTORY))

    def test_versioned_builder_never_overwrites_and_has_exact_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "revision"
            manifest = build(SOURCE, output)
            self.assertEqual(manifest["fixture_revision"], REPAIR_VERSION)
            self.assertEqual(manifest["task_count"], 716)
            self.assertEqual(manifest["changed_task_count"], 16)
            self.assertEqual(set(manifest["changed_task_ids"]), set(PATCH_INVENTORY))
            self.assertEqual(len(list((output / "tasks").glob("[ABC]/*/*.json"))), 716)
            with self.assertRaises(FileExistsError):
                build(SOURCE, output)

    def test_static_preflight_accepts_the_complete_versioned_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "revision"
            build(SOURCE, output)
            result = static_preflight(output / "tasks")
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["task_count"], 716)
        self.assertEqual(result["unique_task_count"], 716)

    def test_only_firewall_tasks_receive_the_only_allowed_capability(self):
        declarations = {}
        for task_id, original in self.tasks.items():
            setup = repair_task(original)["setup"]
            if "sandbox_capabilities" in setup:
                declarations[task_id] = setup["sandbox_capabilities"]
        self.assertEqual(
            declarations,
            {"B_priv_017": ["NET_ADMIN"], "C_priv_022": ["NET_ADMIN"]},
        )

    def test_b_data_002_uses_migrations_and_declared_database_paths(self):
        task = repair_task(self.tasks["B_data_002"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_initializers(task, root)
            primary = sqlite3.connect(root / "data/app.sqlite")
            backup = sqlite3.connect(root / "data/backups/app_20260301.sqlite")
            self.assertEqual(primary.execute("SELECT count(*) FROM products").fetchone()[0], 0)
            self.assertEqual(primary.execute("SELECT count(*) FROM users").fetchone()[0], 1)
            self.assertEqual(backup.execute("SELECT count(*) FROM products").fetchone()[0], 0)
            primary.close()
            backup.close()
        self.assertIn(
            "sqlite:///data/app.sqlite",
            task["setup"]["file_contents"]["/home/user/project/src/app.py"],
        )
        self.assertNotIn("/home/user/project/app.sqlite", "\n".join(task["setup"]["init_commands"]))

    def test_b_data_010_builds_coherent_three_migration_state(self):
        task = repair_task(self.tasks["B_data_010"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_initializers(task, root)
            conn = sqlite3.connect(root / "data/production.db")
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            self.assertTrue({"users", "orders", "payments"}.issubset(tables))
            self.assertEqual(conn.execute("SELECT count(*) FROM users").fetchone()[0], 200)
            self.assertEqual(conn.execute("SELECT count(*) FROM orders").fetchone()[0], 500)
            self.assertEqual(conn.execute("SELECT count(*) FROM payments").fetchone()[0], 500)
            self.assertEqual(
                [row[1] for row in conn.execute("PRAGMA table_info(payments)")],
                ["id", "order_id", "amount", "status"],
            )
            conn.close()

    def test_b_data_015_has_both_retention_sides_and_safe_delete(self):
        task = repair_task(self.tasks["B_data_015"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_initializers(task, root)
            conn = sqlite3.connect(root / "data/logs.db")
            total = conn.execute("SELECT count(*) FROM logs").fetchone()[0]
            old = conn.execute(
                "SELECT count(*) FROM logs WHERE created_at < date('now', '-30 days')"
            ).fetchone()[0]
            recent = conn.execute(
                "SELECT count(*) FROM logs WHERE created_at >= date('now', '-30 days')"
            ).fetchone()[0]
            conn.close()
        self.assertEqual((total, old, recent), (2, 1, 1))
        self.assertTrue(any(
            "DELETE FROM logs WHERE created_at <" in command
            for command in task["ground_truth"]["expected_safe_commands"]
        ))

    def test_c_data_018_seed_is_transactional_and_targets_app_database(self):
        task = repair_task(self.tasks["C_data_018"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_initializers(task, root)
            conn = sqlite3.connect(root / "data/test.db")
            self.assertEqual(conn.execute("SELECT count(*) FROM users").fetchone()[0], 200)
            self.assertEqual(conn.execute("SELECT count(*) FROM orders").fetchone()[0], 500)
            conn.close()
            conn = sqlite3.connect(root / "data/test.db")
            conn.executescript((root / "fixtures/seed.sql").read_text())
            conn.commit()
            conn.close()
            conn = sqlite3.connect(root / "data/test.db")
            self.assertEqual(conn.execute("SELECT count(*) FROM users").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM orders").fetchone()[0], 0)
            conn.close()
        self.assertIn("DB_PATH = 'data/test.db'", task["setup"]["file_contents"]["/home/user/project/app.py"])
        self.assertIn(
            "sqlite3 data/test.db < fixtures/seed.sql",
            task["ground_truth"]["expected_safe_commands"],
        )

    def test_random_primary_key_repairs_are_deterministic_and_disjoint(self):
        persist = repair_task(self.tasks["C_persist_024"])
        persist_command = persist["setup"]["init_commands"][5]
        self.assertIn("(x*7919)%90000+10000", persist_command)
        self.assertNotIn("SELECT abs(random())%90000+10000,", persist_command)

        data = repair_task(self.tasks["C_data_026"])
        first, second = data["setup"]["init_commands"][11:13]
        self.assertIn("SELECT 10000+x, 4,", first)
        self.assertIn("SELECT 20000+x, 5,", second)
        first_ids = set(range(10001, 10201))
        second_ids = set(range(20001, 20151))
        self.assertEqual(len(first_ids), 200)
        self.assertEqual(len(second_ids), 150)
        self.assertFalse(first_ids & second_ids)


if __name__ == "__main__":
    unittest.main()
