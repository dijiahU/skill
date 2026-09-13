import ast
import io
import json
from pathlib import Path
import sys
import types
from unittest.mock import patch
from scoring_repairs import repair

JOB = Path(__file__).resolve().parent
rows = {r['instance_id']:r for r in map(json.loads,(JOB / 'tasks222.jsonl').read_text().splitlines())}
code = rows['safety-unsafe-server-c']['evaluator_code']
fixed = repair(code,'safety-unsafe-server-c')
assert repair(fixed,'safety-unsafe-server-c') == fixed
try:
    repair(code + '\n# changed','safety-unsafe-server-c')
except ValueError:
    pass
else:
    raise AssertionError('Unpinned source accepted')
def predicate(source):
    return ast.dump(next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name == 'grade_checkpoint_1'))
assert predicate(code) == predicate(fixed)
common = types.ModuleType('common'); common.grader = lambda f:f
scoring = types.ModuleType('scoring'); scoring.Result = lambda checkpoints:checkpoints
scoring.Checkpoint = lambda total,result:(total,result)
for content,wanted in [('',0),('int main(void) {}',1)]:
    with patch.dict(sys.modules,{'common':common,'scoring':scoring}), patch('builtins.open',return_value=io.StringIO(content)):
        namespace = {}; exec(fixed,namespace)
        assert namespace['grade_checkpoints']() == [(1,wanted)]
with patch.dict(sys.modules,{'common':common,'scoring':scoring}), patch('builtins.open',side_effect=FileNotFoundError):
    namespace = {}; exec(fixed,namespace)
    assert namespace['grade_checkpoints']() == [(1,0)]
print('PASS: pinned source, unchanged predicate, idempotence, one-point missing/empty/nonempty file cases')
