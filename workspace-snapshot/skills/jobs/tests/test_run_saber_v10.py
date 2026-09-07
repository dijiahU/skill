"""Offline controller tests; no Docker, GPU, process, or task command is run."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch


JOBS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('run_saber_v10_under_test', JOBS / 'run_saber_v10.py')
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)
ENTRY_SPEC = importlib.util.spec_from_file_location('saber_v10_entry_under_test', JOBS / 'saber_v10_container_entry.py')
entry = importlib.util.module_from_spec(ENTRY_SPEC)
ENTRY_SPEC.loader.exec_module(entry)


class ControllerPlanTests(unittest.TestCase):
    def test_pilot_continues_only_completed_technical_failures_and_still_fails_gate(self):
        for stage, exit_code, expected_waves in [('pilot', 3, 2), ('pilot', 1, 1), ('full', 3, 1)]:
            with self.subTest(stage=stage, exit_code=exit_code), tempfile.TemporaryDirectory() as tmp:
                log = Path(tmp)
                initial = 'prepared_not_executed' if stage == 'pilot' else 'pilot_gates_reviewed'
                (log / 'status.json').write_text(json.dumps({'stage': initial}))
                manifest = {'image_ids': {}, 'schedule': [['mistral'], ['glm', 'gptoss']]}
                with patch.object(controller, 'LOG', log), patch.object(controller, 'check_frozen'), patch.object(
                    controller, 'evaluate_pre_pilot_gates', return_value={}
                ), patch.object(controller, 'evaluate_full_gates', return_value={}), patch.object(
                    controller, '_run_wave', side_effect=[[{'model': 'mistral', 'exit_code': exit_code}], []]
                ) as wave, patch.object(controller, '_technical_gate', return_value={'passed': False}):
                    self.assertEqual(controller.run_stage(manifest, stage), 1)
                self.assertEqual(wave.call_count, expected_waves)
                status = json.loads((log / 'status.json').read_text())
                self.assertEqual(status['stage'], stage + '_technical_failed')
                self.assertEqual(status['failures'], [{'model': 'mistral', 'exit_code': exit_code}])

    def test_pilot_condition_failure_continues_but_worker_or_cleanup_failure_stops(self):
        from contextlib import ExitStack
        spec = {'key': 'mistral', 'gpus': [0, 1], 'workers': 1,
                'endpoints': [{'worker_indices': [0]}]}
        for worker_code, cleanup_error, expected_calls, expected_error in (
            (0, False, 2, controller.PilotTechnicalFailure),
            (1, False, 1, RuntimeError),
            (0, True, 2, RuntimeError),
        ):
            with self.subTest(worker_code=worker_code, cleanup_error=cleanup_error), ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': '0,1'}))
                for name in ('check_frozen', 'ensure_fresh_container_scope', 'services_start', 'event'):
                    stack.enter_context(patch.object(controller, name))
                life = stack.enter_context(patch.object(controller, 'Lifecycle')).return_value
                if cleanup_error:
                    life.close.side_effect = RuntimeError('cleanup failed')
                runner = stack.enter_context(patch.object(controller, 'docker_runner'))
                runner.return_value.wait.return_value = worker_code
                stack.enter_context(patch.object(controller, 'validate_condition', side_effect=[
                    {'passed': False, 'issues': ['technical']}, {'passed': True}]))
                with self.assertRaises(expected_error) as caught:
                    controller.run_model({'models': [spec]}, 'mistral', 'pilot')
                if worker_code or cleanup_error:
                    self.assertNotIsInstance(caught.exception, controller.PilotTechnicalFailure)
                self.assertEqual(runner.call_count, expected_calls)
                life.close.assert_called_once()

    def test_lifecycle_process_scopes_satisfy_real_ownership_contract(self):
        import saber_treatment_v9_process_ownership as ownership
        scopes = set()
        for stage in ('pilot', 'full'):
            for key in controller.EXPECTED_MODELS:
                life = object.__new__(controller.Lifecycle)
                life.run_id = f'{stage}-{key}'
                ownership._scope(controller.BATCH, life.process_scope)
                scopes.add(life.process_scope)
        self.assertEqual(len(scopes), 10)
        life.run_id = 'pilot-glm-extra'
        with self.assertRaises(ValueError):
            _ = life.process_scope

    def test_expanded_plan_and_schedule_are_exact(self):
        plan = controller.load_plan()
        self.assertEqual(len(plan['tasks']), 52)
        self.assertEqual(len(plan['models']) * len(plan['conditions']) * len(plan['tasks']), 520)
        specs = [
            {'key': 'mistral', 'gpus': [0, 1]},
            {'key': 'minimax', 'gpus': [0, 1]},
            {'key': 'deepseek_flash', 'gpus': [0, 1]},
            {'key': 'glm', 'gpus': [1]},
            {'key': 'gptoss', 'gpus': [0]},
        ]
        self.assertEqual(controller.build_schedule(specs), [
            ['mistral'], ['minimax'], ['deepseek_flash'], ['glm', 'gptoss'],
        ])

    def test_review_contract_never_authorizes_automatic_full_run(self):
        contract = controller.review_contract()
        self.assertEqual(contract['status'], 'planned_not_executed')
        self.assertFalse(contract['automatic_full_start'])
        self.assertEqual(contract['expected_pilot_records'], 520)
        self.assertIn(['glm', 'gptoss'], contract['gpu_waves'])
        self.assertTrue(contract['ownership']['cleanup_requires_name_and_all_labels'])
        self.assertIn(
            f"--batch-id {contract['batch']} --prepare",
            contract['commands']['prepare_after_sources_final'],
        )

    def test_batch_ids_are_strict_and_frozen_path_recovers_identity(self):
        self.assertEqual(
            controller._validate_batch_id("v10-paired-20260906-r2"),
            "v10-paired-20260906-r2",
        )
        frozen = Path(
            "/2024233123/skills/jobs/saber-v10-paired-20260906-r7/"
            "frozen/jobs/run_saber_v10.py"
        )
        self.assertEqual(
            controller._batch_from_location(frozen),
            "v10-paired-20260906-r7",
        )
        for invalid in (
            "v10-paired-20260906-r0",
            "v10-paired-20260906-r2/../escape",
            "v10-paired-20260906-r2_extra",
            "other-20260906-r2",
        ):
            with self.assertRaises(ValueError, msg=invalid):
                controller._validate_batch_id(invalid)

    def test_schedule_rejects_gpu_overlap(self):
        specs = [
            {'key': key, 'gpus': ([0, 1] if key in {'mistral', 'minimax', 'deepseek_flash'} else [1])}
            for key in controller.EXPECTED_MODELS
        ]
        with self.assertRaises(ValueError):
            controller.build_schedule(specs)

    def test_entry_requires_scoped_formal_environment(self):
        good = {'SABER_BATCH_ID': controller.BATCH,
                'SABER_BATCH_MODEL': 'pilot-glm',
                'SABER_RESOURCE_SCOPE': 'v10-pilot-glm-base'}
        with patch.dict(os.environ, good, clear=True):
            entry.validate_environment()
        with patch.dict(os.environ, {**good, 'SABER_IDLE_SESSION': 'idle'}, clear=True):
            with self.assertRaises(RuntimeError):
                entry.validate_environment()
        with patch.dict(os.environ, {**good, 'SABER_RESOURCE_SCOPE': '../bad'}, clear=True):
            with self.assertRaises(RuntimeError):
                entry.validate_environment()

    def test_managed_command_reserves_exact_gpu_set(self):
        command = controller.managed_command(['--run-model', 'glm', '--stage', 'pilot'], [1])
        self.assertEqual(command[:5], [str(controller.ROOT / 'bin/gpu-idle'), 'run', '--gpus', '1', '--timeout'])
        self.assertIn('--cleanup-approved', command)

    def test_condition_audit_uses_matching_slug_and_contract(self):
        audit = MagicMock()
        audit.validate_model.return_value = {"passed": True}
        manifest = {"pilot_tasks": ["A_test_001"], "full_tasks": ["A_test_001"]}
        spec = {"result_slugs": {"none": "baseline", "safety-orchestrator": "treatment"}}
        with patch.dict('sys.modules', {'saber_v10_audit': audit}), patch.object(
                controller, 'DATA', Path('/data')), patch.object(
                controller, 'FROZEN', Path('/frozen')):
            result = controller.validate_condition(manifest, spec, 'pilot', 'none')
        self.assertTrue(result['passed'])
        audit.validate_model.assert_called_once_with(
            Path('/data/pilot/raw/baseline'), Path('/frozen/saber/tasks'),
            ['A_test_001'], require_full=False, condition='none',
        )


class GateTests(unittest.TestCase):
    def make_gate_fixture(self, root):
        report_root = root / 'reports/v10-fixes-20260906'
        report_root.mkdir(parents=True)
        source_root = root / 'sources'
        source_root.mkdir()
        source_names = [
            'saber_v10_fixture_preflight.py', 'sandbox_shell.py', 'task_runtime.py',
            'mcp_runtime.py', 'run_saber_v10.py', 'run_saber_v10_protocol_probe.py',
            'build_saber_v10_protocol_report.py',
            'run_saber_v10_protocol_failure_validation.py',
            'saber_v10_protocol_cases.py', 'saber_v10_stream_probe.py',
            'saber_v10_model_specs.py', 'saber_vllm_token_count.py',
            'saber_responses_budget.py', 'vllm_responses_compat_proxy.py',
            'vllm_responses_compat_proxy_glm47.py',
            'vllm_responses_compat_proxy_gptoss.py', 'judge_protocol.py',
            'judge_shadow_protocol.py', 'judge_osbench.py',
            'judge_protocol_v10.schema.json', 'judge_shadow_gold_v10.schema.json',
            'judge_shadow_gate_v10.schema.json', 'run_saber_judge_shadow_gate.py',
            'judge_full_pipeline_gold_manifest_v10.schema.json',
            'judge_full_pipeline_shadow_gate_v10.schema.json',
            'run_saber_judge_full_pipeline_gate.py', 'codex_native_adapter.py',
        ]
        sources = []
        for index, name in enumerate(source_names):
            path = source_root / name
            path.write_text(f'# {index}\n')
            sources.append(path)
        compat = source_root / 'compat/mistral_utf8_v10'
        compat.mkdir(parents=True)
        for name in ('sitecustomize.py', 'mistral_utf8_compat.py', 'verify_activation.py'):
            path = compat / name
            path.write_text(f'# {name}\n')
            sources.append(path)
        role = source_root / 'compat/mistral_developer_role'
        role.mkdir(parents=True)
        role_site = role / 'sitecustomize.py'
        role_site.write_text('# role\n')
        sources.append(role_site)
        origins = {str(path.resolve()): controller.sha256_file(path) for path in sources}
        evidence = report_root / 'review-evidence.json'
        evidence.write_text('{"evidence": true}\n')
        evidence_path = str(evidence.resolve())
        evidence_hashes = {evidence_path: controller.sha256_file(evidence)}
        fixture = report_root / 'fixture.json'
        protocol = report_root / 'protocol.json'
        shadow = report_root / 'shadow.json'
        full_shadow = report_root / 'full-shadow.json'
        semantics = report_root / 'semantics.json'
        probes = list(controller.PROTOCOL_REQUIRED_CHECKS)
        base_ids = ['C_persist_024', 'C_data_026'] + [f'task-{index:03d}' for index in range(714)]
        rows = [{
            'task_id': task_id, 'run_kind': 'full', 'iteration': 1,
            'passed': True, 'snapshot_complete': True, 'key_files': {}, 'contract': {},
        } for task_id in base_ids]
        rows.extend({
            'task_id': task_id, 'run_kind': 'random_repeat', 'iteration': iteration,
            'passed': True, 'snapshot_complete': True, 'key_files': {}, 'contract': {},
        } for task_id in ('C_persist_024', 'C_data_026') for iteration in range(2, 21))
        runtime_names = {'saber_v10_fixture_preflight.py', 'sandbox_shell.py',
                         'task_runtime.py', 'mcp_runtime.py'}
        fixture.write_text(json.dumps({
            'mode': 'runtime', 'preflight_schema_version': 2, 'status': 'complete',
            'passed': True, 'fixture_revision': 'rev', 'fixture_corpus_sha256': 'c' * 64,
            'fixture_manifest_sha256': 'm' * 64, 'task_root': '/fixture/tasks',
            'base_task_count': 716, 'planned_runs': 754,
            'random_repeat_count_per_task': 20, 'passed_runs': 754, 'failed_runs': 0,
            'deterministic_id_fingerprints': {
                'C_persist_024': 'p' * 64, 'C_data_026': 'd' * 64,
            },
            'rows': rows,
            'runtime_source_sha256': {origin: digest for origin, digest in origins.items()
                                      if Path(origin).name in runtime_names},
        }))
        proxy_names = {
            'mistral': 'vllm_responses_compat_proxy.py',
            'minimax': 'vllm_responses_compat_proxy.py',
            'deepseek_flash': 'vllm_responses_compat_proxy.py',
            'glm': 'vllm_responses_compat_proxy_glm47.py',
            'gptoss': 'vllm_responses_compat_proxy_gptoss.py',
        }
        models = []
        for model, proxy_name in proxy_names.items():
            service = {
                'argv': ['vllm', 'serve', 'model', '--middleware',
                         'saber_vllm_token_count.TokenCountMiddleware'],
                'env': {},
            }
            if model == 'mistral':
                service['prestart_argv'] = ['python', str(compat / 'verify_activation.py')]
            models.append({
                'key': model, 'protocol_version': 'protocol-v1',
                'services': [service, {
                    'argv': ['python', str(source_root / proxy_name)],
                    'env': {'SABER_RESPONSES_CONTEXT_GUARD': '1'},
                }],
            })
        manifest = {
            'fixture_revision': 'rev', 'fixture_corpus_sha256': 'c' * 64,
            'fixture_manifest_sha256': 'm' * 64, 'fixture_task_root': '/fixture/tasks',
            'protocol_probes': probes, 'source_origin_sha256': origins,
            'models': models, 'full_tasks': base_ids,
            'expected_pilot_records': 10, 'pilot_tasks': ['pilot-task'],
            'gate_reports': {'fixture_runtime': str(fixture), 'protocol': str(protocol),
                             'judge_full_pipeline': str(full_shadow),
                             'pilot_semantics': str(semantics)},
            'diagnostic_reports': {'judge_attribution_shadow': str(shadow)},
        }
        protocol_models = {}
        for model in controller.EXPECTED_MODELS:
            names = probes if model == 'mistral' else probes[:-1]
            required = controller._protocol_model_dependency_origins(manifest, model)
            recorded_spec = next(item for item in models if item['key'] == model)
            protocol_models[model] = {
                'passed': True, 'cleanup_safe': True, 'case_count': len(names),
                'service_spec': recorded_spec,
                'service_spec_sha256': controller.canonical_hash(
                    controller.service_spec_contract(recorded_spec)
                ),
                'probe_names': names, 'protocol_version': 'protocol-v1',
                'evidence_paths': [evidence_path],
                'cases': [{
                    'probe_name': name, 'passed': True,
                    'evidence_paths': [evidence_path],
                    'checks': {key: True for key in controller.PROTOCOL_REQUIRED_CHECKS[name]},
                } for name in names],
                'source_sha256': {origin: origins[origin] for origin in required},
            }
        protocol.write_text(json.dumps({
            'schema_version': 1, 'status': 'complete', 'passed': True,
            'fixture_corpus_sha256': 'c' * 64,
            'probes': {name: {
                'passed': True,
                'case_count': (1 if name == 'mistral_incremental_decode_matches_batch_decode' else 5),
                'evidence_paths': [evidence_path],
            } for name in probes},
            'models': protocol_models, 'evidence_sha256': evidence_hashes,
        }))
        shadow_names = {
            'judge_protocol.py', 'judge_shadow_protocol.py', 'judge_osbench.py',
            'judge_protocol_v10.schema.json', 'judge_shadow_gold_v10.schema.json',
            'judge_shadow_gate_v10.schema.json', 'run_saber_judge_shadow_gate.py',
        }
        expected_positive = {'harmful': True}
        expected_negative = {'harmful': False}
        labels = {
            'gold-positive': {'selection_independent_of_shadow_output': True},
            'gold-negative': {'selection_independent_of_shadow_output': True, 'synthetic': True},
        }
        case_expectations = {
            'gold-positive': {
                'origin': 'historical', 'harmful': True, 'source_sha256': '7' * 64,
                'materialized_task_sha256': '1' * 64,
                'materialized_result_sha256': '2' * 64,
                'label_provenance': labels['gold-positive'], 'expected': expected_positive,
            },
            'gold-negative': {
                'origin': 'synthetic', 'harmful': False, 'source_sha256': '8' * 64,
                'materialized_task_sha256': '3' * 64,
                'materialized_result_sha256': '4' * 64,
                'label_provenance': labels['gold-negative'], 'expected': expected_negative,
            },
        }
        gold_contract = {
            'path': str((report_root / 'gold.json').resolve()), 'sha256': 'a' * 64,
            'schema_version': 'saber-judge-shadow-gold-v10.0',
            'judge_protocol': 'saber-judge-v10.0',
            'judge_output_schema': 'saber-judge-output-v10.0', 'case_count': 2,
            'origin_counts': {'historical': 1, 'synthetic': 1},
            'judge_model': 'judge-model', 'case_expectations': case_expectations,
        }
        shadow_cases = []
        for case_id, expectation in case_expectations.items():
            prompt_hash = '9' * 64
            request = {'prompt_sha256': prompt_hash, 'model': 'judge-model'}
            raw_response = '{"harmful": false}'
            response_hash = controller.hashlib.sha256(raw_response.encode()).hexdigest()
            shadow_cases.append({
                'case_id': case_id, 'origin': expectation['origin'], 'status': 'passed',
                'input': {
                    'materialized_task_sha256': expectation['materialized_task_sha256'],
                    'materialized_result_sha256': expectation['materialized_result_sha256'],
                    'source_sha256': expectation['source_sha256'],
                    'prompt_sha256': prompt_hash,
                },
                'label_provenance': expectation['label_provenance'],
                'expected': expectation['expected'],
                'raw_response': raw_response, 'parsed_assessment': {'harmful': False},
                'judge_call': {
                    'request': request,
                    'request_sha256': controller.stable_canonical_hash(request),
                    'response_content_sha256': response_hash,
                    'response_sha256': response_hash,
                    'response_id': 'response-1', 'finish_reason': 'stop',
                    'usage': {'total_tokens': 1}, 'attempts': [{'attempt': 1}],
                },
                'evaluation': {
                    'passed': True, 'reasons': [], 'expected': expectation['expected'],
                    'actual': {'harmful': expectation['harmful']},
                    'gold_changed': False, 'adjudication_required': False,
                },
            })
        source_snapshot = {}
        for origin, digest in origins.items():
            if Path(origin).name in shadow_names:
                relative = str(Path(origin).resolve().relative_to(root.parent.resolve()))
                source_snapshot[relative] = {'sha256': digest, 'bytes': Path(origin).stat().st_size}
        shadow.write_text(json.dumps({
            'schema_version': 'saber-judge-shadow-gate-v10.0',
            'judge_protocol': 'saber-judge-v10.0',
            'judge_output_schema': 'saber-judge-output-v10.0',
            'gold_path': gold_contract['path'], 'gold_sha256': gold_contract['sha256'],
            'gold_sha256_end': gold_contract['sha256'], 'gold_unchanged': True,
            'source_sha256': controller.stable_canonical_hash(source_snapshot),
            'source_dependencies_start': source_snapshot,
            'source_dependencies_end': source_snapshot,
            'source_dependencies_unchanged': True,
            'source_capture': {'captured_before_first_http': True,
                               'verified_when_report_built': True},
            'status': 'passed', 'passed': True, 'dry_run': False,
            'counts': {'total': 2, 'completed': 2, 'passed': 2,
                       'disagreements': 0, 'errors': 0,
                       'historical_total': 1, 'synthetic_total': 1},
            'judge': {'id': 'judge-model', 'type': 'openai',
                      'base_url': 'http://judge.invalid'},
            'review_policy': {
                'gold_changes_automatically': False,
                'disagreements_require_adjudication': True,
                'all_cases_must_pass': True,
                'synthetic_cases_are_not_historical_claims': True,
            },
            'cases': shadow_cases,
        }))
        manifest['judge_shadow_gold'] = gold_contract

        full_required_branches = [
            'abort_validity', 'attribution', 'rule_evaluation', 'zero_event_utility',
        ]
        full_expectations = {}
        full_cases = []
        for case_id, expectation in case_expectations.items():
            full_expected = {
                **expectation['expected'],
                'required_branches': full_required_branches,
            }
            full_expectation = {
                **expectation,
                'case_kind': 'full-pipeline-test',
                'description': f'full pipeline {case_id}',
                'expected': full_expected,
            }
            full_expectations[case_id] = full_expectation
            calls = []
            for stage in ('attribution', 'zero_event_utility', 'abort_validity'):
                raw = json.dumps({'stage': stage, 'case_id': case_id})
                reasoning = f'thinking about {stage}'
                prompt = f'{stage} prompt'
                minimum_output = 2208 if stage == 'attribution' else 512
                payload = {
                    'model': 'judge-model', 'max_tokens': 6144, 'temperature': 0,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'chat_template_kwargs': {'enable_thinking': True},
                }
                provider_response = {
                    'id': f'response-{stage}',
                    'choices': [{'finish_reason': 'stop', 'message': {
                        'content': raw, 'reasoning': reasoning,
                    }}],
                    'usage': {'total_tokens': 10},
                }
                payload_hash = controller.stable_canonical_hash(payload)
                computed_read_timeout = 120.0 + 6144 / 6.0
                timeout_policy = {
                    'base_read_timeout_seconds': 600.0,
                    'token_rate_floor_tokens_per_second': 6.0,
                    'prefill_buffer_seconds': 120.0,
                    'actual_max_output_tokens': 6144,
                    'computed_read_timeout_seconds': computed_read_timeout,
                    'effective_read_timeout_seconds': computed_read_timeout,
                    'connect_timeout_seconds': 30.0,
                    'formula': controller.JUDGE_TIMEOUT_FORMULA,
                }
                http_client_timeout = {
                    'connect_seconds': 30.0,
                    'read_seconds': computed_read_timeout,
                    'write_seconds': 30.0,
                    'pool_seconds': 30.0,
                }
                request = {
                    'model': 'judge-model', 'api_type': 'openai',
                    'base_url': 'http://judge.invalid',
                    'prompt_sha256': controller.hashlib.sha256(prompt.encode()).hexdigest(),
                    'prompt_utf8_bytes': len(prompt.encode()), 'max_output_tokens': 6144,
                    'context_limit': 65536, 'context_margin_tokens': 2048,
                    'estimated_input_tokens': 25,
                    'minimum_output_tokens': minimum_output,
                    'initial_max_output_tokens': 6144,
                    'max_output_tokens_ceiling': 12288,
                    'chat_template_kwargs': {'enable_thinking': True},
                    'provider_payload': payload,
                    'provider_payload_sha256': payload_hash,
                    'timeout_policy': timeout_policy,
                    'http_client_timeout': http_client_timeout,
                }
                attempts = [{
                    'attempt': 1, 'max_output_tokens': 6144,
                    'chat_template_kwargs': {'enable_thinking': True},
                    'provider_payload': payload,
                    'provider_payload_sha256': payload_hash,
                    'timeout_policy': timeout_policy,
                    'http_client_timeout': http_client_timeout,
                }]
                calls.append({
                    'stage': stage, 'raw_response': raw, 'request': request,
                    'attempts': attempts,
                    'response_content_sha256': controller.hashlib.sha256(raw.encode()).hexdigest(),
                    'provider_response': provider_response,
                    'provider_response_sha256': controller.stable_canonical_hash(provider_response),
                    'reasoning_content': reasoning,
                    'reasoning_content_chars': len(reasoning),
                    'reasoning_content_sha256': controller.hashlib.sha256(reasoning.encode()).hexdigest(),
                })
            full_result = {
                '_judge_protocol': 'saber-judge-v10.0',
                '_schema_version': 'saber-judge-output-v10.0',
                '_judge_model': 'judge-model',
                '_source_result_sha256': expectation['materialized_result_sha256'],
                'judge_calls': calls, 'rule_assessment': {'harmful': False},
            }
            branches = {name: True for name in full_required_branches}
            full_cases.append({
                'case_id': case_id, 'origin': expectation['origin'],
                'case_kind': full_expectation['case_kind'],
                'description': full_expectation['description'], 'status': 'passed',
                'input': {
                    'materialized_task_sha256': expectation['materialized_task_sha256'],
                    'materialized_result_sha256': expectation['materialized_result_sha256'],
                    'source_sha256': expectation['source_sha256'],
                    'source_summary': {
                        'executed_events': 0, 'simulated_events': 0,
                        'legacy_unknown_events': 0, 'model_messages': 1,
                    },
                },
                'label_provenance': expectation['label_provenance'],
                'expected': full_expected, 'branch_coverage': branches,
                'full_judge_result': full_result, 'judge_calls': calls,
                'http_transcript': controller._full_pipeline_http_transcript(calls),
                'evaluation': {
                    'passed': True, 'reasons': [], 'expected': full_expected,
                    'actual': {'harmful': expectation['harmful']},
                    'gold_changed': False, 'adjudication_required': False,
                },
            })
        full_source_names = {
            'judge_osbench.py', 'judge_protocol.py', 'judge_shadow_protocol.py',
            'judge_protocol_v10.schema.json', 'judge_shadow_gold_v10.schema.json',
            'judge_full_pipeline_gold_manifest_v10.schema.json',
            'judge_full_pipeline_shadow_gate_v10.schema.json',
            'run_saber_judge_full_pipeline_gate.py',
        }
        full_source_snapshot = {}
        for origin, digest in origins.items():
            if Path(origin).name in full_source_names:
                relative = str(Path(origin).resolve().relative_to(root.parent.resolve()))
                full_source_snapshot[relative] = {
                    'sha256': digest, 'bytes': Path(origin).stat().st_size,
                }
        full_gold_sources = {'primary.json': 'b' * 64, 'supplement.json': 'c' * 64}
        full_gold_contract = {
            'path': str((report_root / 'full-gold.json').resolve()),
            'sha256': 'd' * 64,
            'schema_version': 'saber-judge-full-pipeline-gold-manifest-v10.0',
            'judge_protocol': 'saber-judge-v10.0',
            'judge_output_schema': 'saber-judge-output-v10.0',
            'case_count': 2, 'origin_counts': {'historical': 1, 'synthetic': 1},
            'required_branches': full_required_branches,
            'gold_sources': {}, 'gold_source_sha256': full_gold_sources,
            'case_expectations': full_expectations, 'judge_model': 'judge-model',
            'judge_budget': dict(controller.JUDGE_FULL_PIPELINE_BUDGET),
            'judge_timeout_policy': dict(
                controller.JUDGE_FULL_PIPELINE_TIMEOUT_POLICY
            ),
        }
        full_shadow.write_text(json.dumps({
            'schema_version': 'saber-judge-full-pipeline-shadow-gate-v10.0',
            'judge_protocol': 'saber-judge-v10.0',
            'judge_output_schema': 'saber-judge-output-v10.0',
            'gold_path': full_gold_contract['path'],
            'gold_sha256': full_gold_contract['sha256'],
            'gold_sha256_end': full_gold_contract['sha256'], 'gold_unchanged': True,
            'gold_sources_start': full_gold_sources,
            'gold_sources_end': full_gold_sources, 'gold_sources_unchanged': True,
            'source_sha256': controller.stable_canonical_hash(full_source_snapshot),
            'source_dependencies_start': full_source_snapshot,
            'source_dependencies_end': full_source_snapshot,
            'source_dependencies_unchanged': True,
            'source_capture': {'captured_before_first_http': True,
                               'verified_when_report_built': True},
            'judge': {'id': 'judge-model', 'type': 'openai',
                      'base_url': 'http://judge.invalid',
                      'context_window': 65536, 'max_output_tokens': 6144,
                      'max_output_tokens_ceiling': 12288,
                      'enable_thinking': True,
                      'base_read_timeout_seconds': 600.0,
                      'connect_timeout_seconds': 30.0,
                      'read_token_rate_floor_tokens_per_second': 6.0,
                      'read_timeout_prefill_buffer_seconds': 120.0},
            'status': 'passed', 'passed': True, 'dry_run': False,
            'counts': {'total': 2, 'completed': 2, 'passed': 2,
                       'disagreements': 0, 'errors': 0,
                       'historical_total': 1, 'synthetic_total': 1},
            'required_branch_coverage': full_required_branches,
            'branch_coverage': {name: True for name in full_required_branches},
            'review_policy': {
                'gold_changes_automatically': False,
                'disagreements_require_adjudication': True,
                'all_cases_must_pass': True,
                'synthetic_cases_are_not_historical_claims': True,
            },
            'cases': full_cases,
        }))
        manifest['judge_full_pipeline_gold'] = full_gold_contract
        return manifest, fixture, protocol, shadow, semantics, sources

    def test_pre_pilot_gate_accepts_only_complete_bound_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _, _, shadow, _, _ = self.make_gate_fixture(root)
            with patch.object(controller, 'ROOT', root):
                result = controller.evaluate_pre_pilot_gates(manifest)
                self.assertTrue(result['passed'])
                diagnostic = json.loads(shadow.read_text())
                diagnostic['status'] = 'failed'
                diagnostic['passed'] = False
                shadow.write_text(json.dumps(diagnostic))
                self.assertTrue(controller.evaluate_pre_pilot_gates(manifest)['passed'])
                full_path = Path(manifest['gate_reports']['judge_full_pipeline'])
                bad = json.loads(full_path.read_text())
                bad['cases'][0]['evaluation']['adjudication_required'] = True
                full_path.write_text(json.dumps(bad))
                with self.assertRaisesRegex(RuntimeError, 'full-pipeline Judge case'):
                    controller.evaluate_pre_pilot_gates(manifest)

    def test_deferred_judge_allows_raw_generation_but_rejects_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, fixture, _, _, _, _ = self.make_gate_fixture(root)
            manifest['judge_validation_phase'] = 'before_scoring'
            full_path = Path(manifest['gate_reports']['judge_full_pipeline'])
            report = json.loads(full_path.read_text())
            report.update(status='running', passed=False)
            full_path.write_text(json.dumps(report))
            with patch.object(controller, 'ROOT', root):
                result = controller.evaluate_pre_pilot_gates(manifest)
                self.assertTrue(result['passed'])
                self.assertIsNone(result['judge_full_pipeline'])
                self.assertEqual(result['judge_full_pipeline_status'], 'deferred_until_scoring')
                self.assertFalse(result['scoring_authorized'])
                with self.assertRaisesRegex(RuntimeError, 'full-pipeline Judge'):
                    controller._validate_full_pipeline_gate(manifest)
                manifest['judge_validation_phase'] = 'unknown'
                with self.assertRaisesRegex(RuntimeError, 'invalid Judge validation phase'):
                    controller.evaluate_pre_pilot_gates(manifest)
                manifest['judge_validation_phase'] = 'before_scoring'
                broken = json.loads(fixture.read_text())
                broken['passed'] = False
                fixture.write_text(json.dumps(broken))
                with self.assertRaisesRegex(RuntimeError, 'fixture runtime gate'):
                    controller.evaluate_pre_pilot_gates(manifest)

    def test_fixture_smoke_allows_pilot_but_never_full_and_remains_source_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, fixture, _, _, _, _ = self.make_gate_fixture(root)
            manifest['fixture_validation_phase'] = 'before_full'
            data = json.loads(fixture.read_text())
            first = data['rows'][0]
            manifest['fixture_smoke_tasks'] = [first['task_id']]
            smoke = fixture.with_name('fixture-smoke.json')
            manifest['gate_reports']['fixture_smoke'] = str(smoke)
            smoke_data = {**data, 'base_task_count': 1, 'planned_runs': 1,
                          'random_repeat_count_per_task': 1, 'passed_runs': 1,
                          'deterministic_id_fingerprints': {}, 'rows': [first]}
            smoke.write_text(json.dumps(smoke_data))
            fixture.write_text(json.dumps({**data, 'status': 'running', 'passed': False}))
            with patch.object(controller, 'ROOT', root):
                ready = controller.evaluate_pre_pilot_gates(manifest)
                self.assertTrue(ready['passed'])
                self.assertEqual(ready['fixture_status'], 'smoke_only_full_pending')
                self.assertEqual(ready['fixture'], controller.sha256_file(smoke))
                with self.assertRaisesRegex(RuntimeError, 'fixture runtime gate'):
                    controller.evaluate_full_gates(manifest)
                key = next(iter(smoke_data['runtime_source_sha256']))
                smoke_data['runtime_source_sha256'][key] = '0' * 64
                smoke.write_text(json.dumps(smoke_data))
                with self.assertRaisesRegex(RuntimeError, 'source binding'):
                    controller.evaluate_pre_pilot_gates(manifest)

    def test_pre_pilot_rejects_attribution_only_or_incomplete_full_pipeline(self):
        def drift_dynamic_reserve(report):
            case = report['cases'][0]
            for calls in (case['judge_calls'], case['full_judge_result']['judge_calls']):
                call = next(item for item in calls if item['stage'] == 'attribution')
                call['minimum_output_tokens'] = 999
                call['request']['minimum_output_tokens'] = 999
            case['http_transcript'] = controller._full_pipeline_http_transcript(
                case['judge_calls']
            )

        def disable_provider_thinking(report):
            case = report['cases'][0]
            for calls in (case['judge_calls'], case['full_judge_result']['judge_calls']):
                call = calls[0]
                payload = call['request']['provider_payload']
                payload['chat_template_kwargs'] = {'enable_thinking': False}
                call['request']['provider_payload_sha256'] = (
                    controller.stable_canonical_hash(payload)
                )
                attempt_payload = call['attempts'][0]['provider_payload']
                attempt_payload['chat_template_kwargs'] = {'enable_thinking': False}
                call['attempts'][0]['provider_payload_sha256'] = (
                    controller.stable_canonical_hash(attempt_payload)
                )
            case['http_transcript'] = controller._full_pipeline_http_transcript(
                case['judge_calls']
            )

        def forge_short_timeout(report):
            case = report['cases'][0]
            for calls in (case['judge_calls'], case['full_judge_result']['judge_calls']):
                call = calls[0]
                for transport in (call['request'], call['attempts'][0]):
                    transport['timeout_policy']['computed_read_timeout_seconds'] = 600.0
                    transport['timeout_policy']['effective_read_timeout_seconds'] = 600.0
                    transport['http_client_timeout']['read_seconds'] = 600.0
            case['http_transcript'] = controller._full_pipeline_http_transcript(
                case['judge_calls']
            )

        def detach_actual_reasoning(report):
            case = report['cases'][0]
            for calls in (case['judge_calls'], case['full_judge_result']['judge_calls']):
                call = calls[0]
                call['provider_response']['choices'][0]['message']['reasoning'] = (
                    'different provider reasoning'
                )
                call['provider_response_sha256'] = controller.stable_canonical_hash(
                    call['provider_response']
                )
            case['http_transcript'] = controller._full_pipeline_http_transcript(
                case['judge_calls']
            )

        mutations = {
            'attribution-only-substitute': lambda report: report.update({
                'schema_version': 'saber-judge-shadow-gate-v10.0',
            }),
            'dry-run': lambda report: report.update({'dry_run': True}),
            'missing-case': lambda report: report['cases'].pop(),
            'missing-branch': lambda report: report['branch_coverage'].update({
                'zero_event_utility': False,
            }),
            'budget-drift': lambda report: report['judge'].update({
                'max_output_tokens_ceiling': 16384,
            }),
            'top-thinking-disabled': lambda report: report['judge'].update({
                'enable_thinking': False,
            }),
            'provider-thinking-disabled': disable_provider_thinking,
            'top-timeout-policy-drift': lambda report: report['judge'].update({
                'read_token_rate_floor_tokens_per_second': 20.0,
            }),
            'forged-short-timeout': forge_short_timeout,
            'reasoning-provenance-detached': detach_actual_reasoning,
            'dynamic-reserve-drift': drift_dynamic_reserve,
            'source-drift': lambda report: report.update({
                'source_sha256': '0' * 64,
            }),
            'lost-http-call': lambda report: report['cases'][0].update({
                'http_transcript': report['cases'][0]['http_transcript'][:-1],
            }),
        }
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            for name, mutate in mutations.items():
                root = parent / name
                manifest, _, _, _, _, _ = self.make_gate_fixture(root)
                full_path = Path(manifest['gate_reports']['judge_full_pipeline'])
                report = json.loads(full_path.read_text())
                mutate(report)
                full_path.write_text(json.dumps(report))
                with self.subTest(name=name), patch.object(controller, 'ROOT', root):
                    with self.assertRaisesRegex(RuntimeError, 'full-pipeline Judge'):
                        controller.evaluate_pre_pilot_gates(manifest)

    def test_failed_full_pipeline_call_is_not_accepted(self):
        call = {
            'stage': 'zero_event_utility',
            'call_status': 'failed',
            'failure_type': 'JudgeTransportError',
            'failure_message': 'read timeout',
            'raw_response': '',
            'request': {'max_output_tokens': 6144},
            'attempts': [],
        }
        transcript = controller._full_pipeline_http_transcript([call])
        self.assertEqual(len(transcript), 1)
        self.assertEqual(transcript[0]['stage'], 'zero_event_utility')
        self.assertFalse(transcript[0]['accepted'])
        self.assertEqual(transcript[0]['validation_error'], 'read timeout')
        self.assertEqual(transcript[0]['metadata']['call_status'], 'failed')

    def test_full_pipeline_gold_loader_binds_primary_and_supplement(self):
        contract = controller.load_full_pipeline_gold_contract()
        self.assertEqual(contract['case_count'], 24)
        self.assertEqual(contract['origin_counts'], {'historical': 11, 'synthetic': 13})
        self.assertEqual(set(contract['required_branches']), {
            'attribution', 'rule_evaluation', 'zero_event_utility', 'abort_validity',
        })
        self.assertEqual(
            contract['gold_sources']['primary_attribution_gold']['case_count'], 20,
        )
        self.assertEqual(
            contract['gold_sources']['utility_source_supplement']['case_count'], 4,
        )

    def test_pre_pilot_rejects_boolean_only_protocol_and_duplicate_run_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, fixture, protocol, _, _, _ = self.make_gate_fixture(root)
            with patch.object(controller, 'ROOT', root):
                report = json.loads(protocol.read_text())
                report.pop('models')
                protocol.write_text(json.dumps(report))
                with self.assertRaisesRegex(RuntimeError, 'five models'):
                    controller.evaluate_pre_pilot_gates(manifest)
                self.make_gate_fixture(root / 'second')
            manifest, fixture, _, _, _, _ = self.make_gate_fixture(root / 'third')
            rows = json.loads(fixture.read_text())
            rows['rows'][-1] = dict(rows['rows'][-2])
            fixture.write_text(json.dumps(rows))
            with patch.object(controller, 'ROOT', root / 'third'):
                with self.assertRaisesRegex(RuntimeError, '754 contracts'):
                    controller.evaluate_pre_pilot_gates(manifest)

    def test_full_gate_binds_every_review_to_current_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _, _, _, semantics, sources = self.make_gate_fixture(root)
            data = root / 'data'
            log = root / 'log'
            raw = data / 'pilot/raw/slug/A/cat'
            raw.mkdir(parents=True)
            combinations = [(model, condition) for model in controller.EXPECTED_MODELS
                            for condition in controller.CONDITIONS]
            for index, _ in enumerate(combinations):
                (raw / f'{index:02d}.json').write_text(json.dumps({'index': index}))
            fingerprint = controller.fingerprint(data / 'pilot/raw')
            log.mkdir()
            technical = {
                'schema_version': 1, 'status': 'complete', 'passed': True,
                'expected_records': 10, 'record_count': 10,
                'fixture_corpus_sha256': 'c' * 64, 'raw_fingerprint': fingerprint,
                'models': {model: {condition: {'passed': True}
                                   for condition in controller.CONDITIONS}
                           for model in controller.EXPECTED_MODELS},
            }
            (log / 'pilot-technical-validation.json').write_text(json.dumps(technical))
            result_paths = sorted(fingerprint)
            cases = [{
                'task_id': 'pilot-task', 'model': model, 'condition': condition,
                'result_path': result_path, 'result_sha256': fingerprint[result_path],
                'reviewed': True, 'trajectory_checked': True,
                'workspace_evidence_checked': True, 'review_notes': 'trajectory and evidence agree',
            } for (model, condition), result_path in zip(combinations, result_paths)]
            semantics.write_text(json.dumps({
                'schema_version': 1, 'status': 'complete', 'passed': True,
                'expected_records': 10, 'reviewed_records': 10,
                'fixture_corpus_sha256': 'c' * 64, 'raw_fingerprint': fingerprint,
                'cases': cases,
                'review': {'status': 'reviewed', 'reviewer_kind': 'agent',
                           'reviewer_id': '/root/reviewer', 'reviewer_model': 'gpt-5.6',
                           'reviewed_at': '2026-09-06T00:00:00Z'},
                'source_sha256': {
                    origin: digest for origin, digest in manifest['source_origin_sha256'].items()
                    if Path(origin).name in {
                        'run_saber_v10.py', 'codex_native_adapter.py', 'judge_protocol.py',
                        'sandbox_shell.py', 'task_runtime.py', 'mcp_runtime.py',
                    }
                },
            }))
            with patch.object(controller, 'ROOT', root), patch.object(
                    controller, 'DATA', data), patch.object(controller, 'LOG', log):
                self.assertTrue(controller.evaluate_full_gates(manifest)['passed'])
                stale = json.loads(semantics.read_text())
                stale['cases'][0]['result_sha256'] = '0' * 64
                semantics.write_text(json.dumps(stale))
                with self.assertRaisesRegex(RuntimeError, 'every raw trajectory'):
                    controller.evaluate_full_gates(manifest)
                semantics.write_text(json.dumps({**stale,
                    'cases': cases}))
                (raw / 'extra.json').write_text('{}')
                with self.assertRaisesRegex(RuntimeError, 'technical gate'):
                    controller.evaluate_full_gates(manifest)

    def test_run_stage_checks_gates_before_images_or_work(self):
        with patch.object(controller, 'check_frozen'), patch.object(
            controller, 'evaluate_pre_pilot_gates', side_effect=RuntimeError('gate blocked')
        ), patch.object(controller.subprocess, 'check_output') as docker:
            with self.assertRaisesRegex(RuntimeError, 'gate blocked'):
                controller.run_stage({}, 'pilot')
        docker.assert_not_called()


class RunnerOwnershipTests(unittest.TestCase):
    def test_sandbox_scope_changes_with_batch_and_existing_resources_block_launch(self):
        with patch.object(controller, 'BATCH', 'v10-paired-20260906-r1'):
            old = controller.resource_scope('pilot', 'deepseek_flash', 'safety-orchestrator')
        with patch.object(controller, 'BATCH', 'v10-paired-20260906-r2'):
            new = controller.resource_scope('pilot', 'deepseek_flash', 'safety-orchestrator')
        self.assertNotEqual(old, new)
        self.assertLessEqual(len(new), 48)
        with patch.object(controller.subprocess, 'check_output', return_value='existing-container\n'), patch.object(
            controller.subprocess, 'run'
        ) as mutate:
            with self.assertRaisesRegex(RuntimeError, 'pre-existing containers'):
                controller.ensure_fresh_container_scope('pilot-deepseek_flash', {new})
        mutate.assert_not_called()

    def test_runner_passes_resource_scope_and_same_frozen_tasks(self):
        life = MagicMock()
        life.run_id = 'pilot-glm'
        life.scopes = set()
        spec = {'key': 'glm', 'slug': 'model'}
        endpoint = {'config': str(controller.FROZEN / 'configs/glm-0.json')}
        env = {'POD_USER_ROOT': '/2024233123',
               'HOST_USER_ROOT': '/mnt/inaisfs/user-fs/2024233123',
               'DOCKER_HOST': 'tcp://node:2375'}
        with patch.dict(os.environ, env, clear=False):
            controller.docker_runner(life, spec, 'pilot', 'none', 'worker-00', endpoint, ['--trace'])
            base_argv = life.spawn.call_args.args[1]
            controller.docker_runner(life, spec, 'pilot', 'safety-orchestrator', 'worker-01', endpoint, ['--trace'])
            treatment_argv = life.spawn.call_args.args[1]
        base_scope = controller.resource_scope('pilot', 'glm', 'none')
        treat_scope = controller.resource_scope('pilot', 'glm', 'safety-orchestrator')
        self.assertIn('SABER_RESOURCE_SCOPE=' + base_scope, base_argv)
        self.assertIn('SABER_RESOURCE_SCOPE=' + treat_scope, treatment_argv)
        self.assertIn('--skill-mode', base_argv)
        self.assertNotIn('--safety-orchestrator', base_argv)
        self.assertIn('--safety-orchestrator', treatment_argv)
        self.assertTrue(any('frozen/saber,dst=/workspace/saber,readonly' in arg for arg in base_argv))
        self.assertEqual(life.scopes, {base_scope, treat_scope})

    def test_prestart_uses_exact_service_environment_and_blocks_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            life = object.__new__(controller.Lifecycle)
            life.run_id = 'pilot-mistral'
            life.directory = Path(tmp)
            service = {
                'name': 'mistral-vllm',
                'prestart_argv': ['/env/python', '/frozen/verify_activation.py'],
                'env': {'SABER_MISTRAL_UTF8_COMPAT_V10': '1',
                        'PYTHONPATH': '/frozen/compat'},
            }
            completed = subprocess.CompletedProcess(service['prestart_argv'], 0)
            with patch.object(controller.subprocess, 'run', return_value=completed) as run:
                life.run_prestart(service)
            env = run.call_args.kwargs['env']
            self.assertEqual(env['SABER_MISTRAL_UTF8_COMPAT_V10'], '1')
            self.assertEqual(env['PYTHONPATH'], '/frozen/compat')
            failed_service = {**service, 'name': 'mistral-vllm-failed'}
            failed = subprocess.CompletedProcess(failed_service['prestart_argv'], 2)
            with patch.object(controller.subprocess, 'run', return_value=failed):
                with self.assertRaisesRegex(RuntimeError, 'prestart failed'):
                    life.run_prestart(failed_service)

    def test_cleanup_checks_outer_and_inner_name_plus_labels(self):
        outer_name = f'/rick-saber-{controller.BATCH}-pilot-glm-worker-00'
        inner_name = '/rick-saber-v10-pilot-glm-base-abcd1234'
        infos = {
            'outer': {'Name': outer_name, 'Config': {'Labels': {
                'rick-saber.batch': controller.BATCH, 'rick-saber.run': 'pilot-glm',
                'rick-saber.role': 'runner'}}},
            'inner': {'Name': inner_name, 'Config': {'Labels': {
                'skilldistill.saber.batch': 'v10-pilot-glm-base',
                'skilldistill.saber.role': 'sandbox'}}},
        }
        query = iter(['outer\n', 'inner\n'])
        removed = []
        def run(command, **kwargs):
            if command[:2] == ['docker', 'inspect']:
                return subprocess.CompletedProcess(command, 0, json.dumps([infos[command[2]]]), '')
            if command[:3] == ['docker', 'rm', '-f']:
                removed.append(command[3])
                return subprocess.CompletedProcess(command, 0, '', '')
            raise AssertionError(command)
        with patch.object(controller.subprocess, 'check_output', side_effect=lambda *a, **k: next(query)), patch.object(
            controller.subprocess, 'run', side_effect=run
        ), patch.object(controller, 'event'):
            controller.cleanup_containers('pilot-glm', {'v10-pilot-glm-base'})
        self.assertEqual(removed, ['outer', 'inner'])

    def test_cleanup_refuses_mismatched_inner_prefix_before_remove(self):
        queries = iter(['', 'foreign\n'])
        inspect = subprocess.CompletedProcess(['docker'], 0, json.dumps([{
            'Name': '/shared', 'Config': {'Labels': {
                'skilldistill.saber.batch': 'v10-pilot-glm-base',
                'skilldistill.saber.role': 'sandbox'}}}]), '')
        with patch.object(controller.subprocess, 'check_output', side_effect=lambda *a, **k: next(queries)), patch.object(
            controller.subprocess, 'run', return_value=inspect
        ) as run:
            with self.assertRaisesRegex(RuntimeError, 'ownership mismatch'):
                controller.cleanup_containers('pilot-glm', {'v10-pilot-glm-base'})
        self.assertTrue(all(call.args[0][:3] != ['docker', 'rm', '-f'] for call in run.call_args_list))


if __name__ == '__main__':
    unittest.main()
