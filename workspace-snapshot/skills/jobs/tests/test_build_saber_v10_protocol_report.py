"""Offline integration checks for the v10 protocol evidence aggregate."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import build_saber_v10_protocol_report as aggregate
import run_saber_v10 as controller
from saber_v10_model_specs import MODEL_SPECS


class ProtocolAggregateTests(unittest.TestCase):
    def test_current_evidence_builds_all_models_and_keeps_fault_scope_explicit(self):
        report = aggregate.build()
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(set(report["models"]), set(controller.EXPECTED_MODELS))
        self.assertEqual(set(report["probes"]), set(controller.PROTOCOL_REQUIRED_CHECKS))
        for model, item in report["models"].items():
            self.assertTrue(item["cleanup_safe"])
            fault_cases = [case for case in item["cases"]
                           if "controlled_local_fault" in case.get("evidence_kind", "")]
            self.assertEqual(len(fault_cases), 3, model)
            self.assertTrue(all(case["controlled_scope"] ==
                                "does_not_prove_model_encountered_fault"
                                for case in fault_cases))

    def test_generated_report_satisfies_controller_protocol_contract(self):
        report = json.loads(aggregate.DEFAULT_OUTPUT.read_text())
        all_sources = {path for item in report["models"].values()
                       for path in item["source_sha256"]}
        manifest = {
            "models": MODEL_SPECS,
            "protocol_probes": list(controller.PROTOCOL_REQUIRED_CHECKS),
            "source_origin_sha256": {
                path: controller.sha256_file(Path(path))
                for path in all_sources if Path(path).is_file()
            },
        }
        common = set(controller.PROTOCOL_REQUIRED_CHECKS) - {
            "mistral_incremental_decode_matches_batch_decode"
        }
        for model, item in report["models"].items():
            expected = set(controller.PROTOCOL_REQUIRED_CHECKS) if model == "mistral" else common
            controller._validate_protocol_cases(model, item, expected)
            controller._validate_recorded_service_spec(item, manifest, model)
            controller._validate_protocol_model_sources(item, manifest, model)
        controller._validate_evidence_paths(
            report,
            [item["evidence_paths"] for item in report["probes"].values()]
            + [item["evidence_paths"] for item in report["models"].values()]
            + [case["evidence_paths"] for item in report["models"].values()
               for case in item["cases"]],
            "protocol",
        )

    def test_service_contract_only_deduplicates_identical_path_entries(self):
        spec = deepcopy(next(item for item in MODEL_SPECS if item["key"] == "minimax"))
        inherited = deepcopy(spec)
        path = inherited["services"][0]["env"]["PATH"]
        first = path.split(":", 1)[0]
        inherited["services"][0]["env"]["PATH"] = f"{first}:{first}:{path}"
        self.assertEqual(controller.service_spec_contract(spec),
                         controller.service_spec_contract(inherited))

        for key, override in (
            ("PATH", "/tmp/override-bin"),
            ("PYTHONPATH", "/tmp/override-python"),
            ("LD_LIBRARY_PATH", "/tmp/override-lib"),
        ):
            changed = deepcopy(spec)
            original = changed["services"][0]["env"].get(key, "")
            changed["services"][0]["env"][key] = (
                f"{override}:{original}" if original else override
            )
            self.assertNotEqual(
                controller.service_spec_contract(spec),
                controller.service_spec_contract(changed),
                key,
            )

    def test_service_contract_detects_runtime_arg_change(self):
        spec = deepcopy(next(item for item in MODEL_SPECS if item["key"] == "minimax"))
        changed = deepcopy(spec)
        position = changed["services"][0]["argv"].index("--max-model-len") + 1
        changed["services"][0]["argv"][position] = "16384"
        self.assertNotEqual(controller.service_spec_contract(spec),
                            controller.service_spec_contract(changed))


if __name__ == "__main__":
    unittest.main()
