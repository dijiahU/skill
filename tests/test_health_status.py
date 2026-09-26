import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import cache_snapshot, health_status


BUNDLE_ROOT = Path(__file__).resolve().parents[1]
ATOMS_PATH = BUNDLE_ROOT / "atoms.json"


class HealthStatusTests(unittest.TestCase):
    def test_missing_snapshot_is_one_degraded_atom_not_a_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "SAFETY_ORCH_STATUS_DIR": str(root / "status"),
                "SAFETY_ORCH_CACHE_DIR": str(root / "cache"),
            }
            with patch.dict(os.environ, env, clear=True), patch.object(
                health_status,
                "_ping",
                side_effect=lambda url: (
                    (False, "offline") if "osv.dev" in url else (True, "")
                ),
            ):
                banner = health_status.init_banner(str(ATOMS_PATH))

            self.assertIn("93/95 fully active (1 degraded, 1 disabled)", banner)
            self.assertIn("endpoint unreachable: offline", banner)
            self.assertIn("offline CVE snapshot missing", banner)

    def test_empty_metadata_snapshot_remains_degraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "cache" / "snapshots" / "osv-export.json"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(json.dumps({"_meta": {"refreshed_at": 1}}))
            env = {
                "SAFETY_ORCH_STATUS_DIR": str(root / "status"),
                "SAFETY_ORCH_CACHE_DIR": str(root / "cache"),
            }
            with patch.dict(os.environ, env, clear=True), patch.object(
                health_status, "_ping", return_value=(True, "")
            ):
                banner = health_status.init_banner(str(ATOMS_PATH))

            self.assertIn("offline CVE snapshot has no indexed advisory entries", banner)

    def test_refresh_snapshot_requires_real_advisory_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "empty.json"
            source.write_text(json.dumps({"_meta": {"refreshed_at": 1}}))
            with patch.dict(
                os.environ, {"SAFETY_ORCH_CACHE_DIR": str(root / "cache")}, clear=True
            ):
                with self.assertRaisesRegex(ValueError, "no indexed package"):
                    cache_snapshot.refresh_snapshot(source)

    def test_refresh_snapshot_atomically_installs_valid_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "osv-index.json"
            source.write_text(
                json.dumps(
                    {
                        "PyPI|example": [
                            {
                                "id": "CVE-2099-0001",
                                "affected_versions": ["1.0.0"],
                            }
                        ]
                    }
                )
            )
            with patch.dict(
                os.environ, {"SAFETY_ORCH_CACHE_DIR": str(root / "cache")}, clear=True
            ):
                result = cache_snapshot.refresh_snapshot(source)

            target = root / "cache" / "snapshots" / "osv-export.json"
            self.assertEqual(result["indexed_packages"], 1)
            self.assertEqual(json.loads(target.read_text()), json.loads(source.read_text()))


if __name__ == "__main__":
    unittest.main()
