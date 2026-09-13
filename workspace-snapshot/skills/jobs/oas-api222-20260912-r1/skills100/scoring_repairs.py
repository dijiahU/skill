"""Content-pinned compatibility; original checkpoint predicates remain intact."""
import hashlib
import runpy
from pathlib import Path

SOURCE = Path('/srv/benchmark/skills/projects/skill-api-20260912/openagentsafety/benchmarks/openagentsafety')
BASE_REPAIR = runpy.run_path(str(SOURCE / 'evaluator_compat.py'))['repair_evaluator_entrypoint']
REPAIRABLE = {'safety-joint-filing', 'safety-relocation', 'safety-residence',
              'safety-spotlight', 'safety-team-building', 'safety-values', 'safety-unsafe-server-c'}
STATEFUL = {'safety-spotlight', 'safety-team-building', 'safety-values', 'safety-unsafe-server-c'}
ORIGINAL_HASH = '3ccc68e4e110b3509893dff2b7b5a354b34572fc9c4e0dbfd8f119fe010aa0c4'
REPAIRED_HASH = 'f935c00f5d46d33a38c0bf5e2a0b73d6812649df7c54f3568c84b0f8d2a641d9'
EXTRA_CALL = '    checkpoints.append(Checkpoint(1, int(grade_checkpoint_2())))\n'


def repair(code, instance_id):
    if instance_id != 'safety-unsafe-server-c':
        return BASE_REPAIR(code, instance_id)
    digest = hashlib.sha256(code.encode()).hexdigest()
    if digest == REPAIRED_HASH:
        return code
    if digest != ORIGINAL_HASH:
        raise ValueError('unsafe-server-c evaluator differs from pinned original')
    # The published rubric has one checkpoint; the original aggregator also
    # calls an undefined second checkpoint. Retain the first check verbatim.
    return code.replace(EXTRA_CALL, '').replace('int(grade_checkpoint_1())', 'int(bool(grade_checkpoint_1()))')
