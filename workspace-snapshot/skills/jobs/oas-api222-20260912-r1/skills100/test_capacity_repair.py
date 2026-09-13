import runpy
from pathlib import Path
from unittest.mock import patch

JOB = Path(__file__).resolve().parent
capacity = runpy.run_path(str(JOB / 'capacity_admission.py'))['capacity']


def test_capacity_boundaries():
    def network(ours, others):
        return {'IPAM': {'Config': [{'Subnet': '203.0.113.0/24'}]}, 'Containers': {
            **{str(i): {'Name': 'rick-oas-api222-20260912-r1-' + str(i)} for i in range(ours)},
            **{'other' + str(i): {'Name': 'shared-' + str(i)} for i in range(others)}}}
    assert capacity(network(95, 0))['can_start']
    assert not capacity(network(96, 0))['can_start']
    assert not capacity(network(0, 221))['can_start']
    assert capacity(network(0, 220))['can_start']
    assert capacity(network(1, 3))['usable_addresses'] == 253


def test_guard_compatibility_and_rejections():
    module = runpy.run_path(str(JOB / 'bin/docker'))
    main = module['main']
    seen = []
    args = ['docker', 'run', '--rm', '-i', '--network', 'none', '--runtime', 'runc',
            '--read-only', '--name', 'skilldistill-oas-grader-test', '--entrypoint', 'python',
            module['BASE_IMAGE'], '-c', 'print(1)']
    with patch.dict(main.__globals__, {'approved': lambda: None, 'inspect': lambda target: {'Id': module['DIGEST']}}), \
         patch('runpy.run_path', return_value={'run_bounded': lambda args, grader: seen.append((args, grader)) or 0}):
        with patch('sys.argv', args):
            try: main()
            except SystemExit as exc: assert exc.code == 0
        actual, grader = seen[0]
        assert grader and module['IMAGE'] in actual and module['BASE_IMAGE'] not in actual
        assert 'rick-oas-api222-20260912-r1-skilldistill-oas-grader-test' in actual
        assert 'skilldistill.oas.api_run=oas-api222-20260912-r1' in actual
        bad_network = args[:]; bad_network[bad_network.index('none')] = 'host'
        bad_image = args[:]; bad_image[bad_image.index(module['BASE_IMAGE'])] = 'unrelated:image'
        bad_name = args[:]; bad_name[bad_name.index('skilldistill-oas-grader-test')] = 'shared-container'
        for invalid in [bad_network, bad_image, bad_name]:
            with patch('sys.argv', invalid):
                try: main()
                except SystemExit as exc: assert exc.code == 2
                else: raise AssertionError('Unsafe request accepted')
        assert len(seen) == 1


def test_removal_ownership():
    module = runpy.run_path(str(JOB / 'bin/docker'))
    main = module['main']
    owned = {'Name': '/rick-oas-api222-20260912-r1-test',
             'Config': {'Labels': {'skilldistill.oas.api_run': 'oas-api222-20260912-r1'}},
             'State': {'Running': False}}
    import copy
    unrelated = copy.deepcopy(owned); unrelated['Name'] = '/shared-container'
    wrong_label = copy.deepcopy(owned); wrong_label['Config']['Labels'] = {}
    running = copy.deepcopy(owned); running['State']['Running'] = True
    for obj in [unrelated, wrong_label, running]:
        with patch.dict(main.__globals__, {'approved': lambda: None, 'inspect': lambda target: obj}), \
             patch('sys.argv', ['docker', 'rm', 'fixture']), patch('os.execv') as launch:
            try: main()
            except SystemExit as exc: assert exc.code == 2
            else: raise AssertionError('Unsafe removal accepted')
            launch.assert_not_called()
    with patch.dict(main.__globals__, {'approved': lambda: None, 'inspect': lambda target: owned}), \
         patch('sys.argv', ['docker', 'rm', 'fixture']), patch('os.execv') as launch:
        main()
        launch.assert_called_once()


def test_recovery_preserves_scores_and_retries_guard_errors():
    from unittest.mock import Mock
    from repair_model import pending
    from resume_helpers import valid
    zero = {'test_result': {'final_score': {'result': 0, 'total': 1}}}
    assert valid(zero)
    partial = {'test_result': {'final_score': {'result': 1, 'total': 1},
                              'skilldistill': {'graded_from_partial_trajectory': True}}}
    assert not valid(partial)
    rows = {'guard': {'error': 'Evaluator failed: OAS run guard: pinned image'},
            'timeout': {'error': 'Evaluator failed: timed out'},
            'broken': {'error': 'Evaluator result has no valid final_score'},
            'partial': partial}
    fixture = Mock(); fixture.__truediv__ = Mock(return_value=Mock(exists=lambda: False, read_text=lambda: 'zero\nguard\ntimeout\nbroken\npartial\nmissing\n'))
    summary = {'selected_attempts': {k:'fixture' for k in rows}}
    with patch.dict(pending.__globals__, {'JOB': fixture, 'merged': lambda model: ({'zero':zero}, summary),
                                        'read_stage': lambda model, stage: rows}):
        todo, held = pending('glm5')
        assert set(todo) == {'guard', 'timeout', 'partial', 'missing'}
        assert held == ['broken']


if __name__ == '__main__':
    test_capacity_boundaries()
    test_guard_compatibility_and_rejections()
    test_removal_ownership()
    test_recovery_preserves_scores_and_retries_guard_errors()
    print('PASS: global capacity, shared address reserve, grader compatibility, and guard rejection cases')
