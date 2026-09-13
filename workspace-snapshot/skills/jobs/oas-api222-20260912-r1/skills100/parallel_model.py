"""Run one remaining model independently, preserving completed results."""
import argparse
import fcntl
from resume_helpers import JOB
from resume_after_recharge import merged, run_stage, write
from recover_rate_limits import unresolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, choices=['deepseek-flash', 'qwen'])
    args = parser.parse_args()
    lock = (JOB / ('parallel-' + args.model + '.lock')).open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = JOB / ('parallel-state-' + args.model + '.json')
    state = {'model': args.model, 'status': 'starting', 'stages': [], 'worker_levels': [128, 32, 8],
             'max_iterations': 100, 'skill_mode': 'safety-orchestrator', 'npc_model': 'deepseek-flash'}
    write(path, state)
    try:
        for index, workers in enumerate(state['worker_levels']):
            todo, blocked = unresolved(args.model, only_rate=index > 0)
            state['evaluator_tasks_held'] = blocked
            if not todo:
                break
            state.update(status='running', workers=workers, tasks_this_stage=len(todo))
            write(path, state)
            stage = f'skills100-{args.model}-parallel1-w{workers}'
            result = run_stage(args.model, todo, stage, workers=workers)
            state['stages'].append(result)
            write(path, state)
            if result['returncode'] != 0:
                state['status'] = 'paused after runner/provider error; results retained'
                write(path, state)
                return
        _, summary = merged(args.model)
        state.update(status='finished; review any remaining invalid results', result={k:v for k,v in summary.items() if k != 'selected_attempts'})
        write(path, state)
    except Exception as exc:
        state.update(status='controller error; results retained', error_type=type(exc).__name__)
        write(path, state)
        raise


if __name__ == '__main__':
    main()
