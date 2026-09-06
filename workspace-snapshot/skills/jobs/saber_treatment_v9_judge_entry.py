"""Run the existing DeepSeek judge against only this frozen batch's results."""

import importlib.util
import json
from pathlib import Path
import sys


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def main():
    manifest = json.loads(Path(sys.argv[1]).read_text())
    frozen = Path(manifest['frozen'])
    sys.path.insert(0, str(frozen / 'saber'))
    judge = module('judge_osbench', frozen / 'saber/judge_osbench.py')
    runner = module('run_saber_parallel_judge', frozen / 'bin/run_saber_parallel_judge.py')
    local = module('run_saber_parallel_judge_deepseekv4',
                   frozen / 'bin/run_saber_parallel_judge_deepseekv4.py')
    judge.TASKS_DIR = frozen / 'saber/tasks'
    judge.RESULTS_DIR = Path(manifest['raw'])
    local.OUTPUT_ROOT = Path(manifest['judged'])
    for spec in manifest['models']:
        runner.run_model(spec['result_slug'], workers=8, max_attempts=3)


if __name__ == '__main__':
    main()
