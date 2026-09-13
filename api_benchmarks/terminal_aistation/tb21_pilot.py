"""Run one real full-deployment model trial and persist the dispatch gate."""
import json
from pathlib import Path
import subprocess
import sys
from validate_run import validate

root=Path(sys.argv[1]).resolve()
argv=['/srv/benchmark/skills/envs/skills/bin/python', str(root/'frozen/adapter/model_lifecycle.py'),
      '--model','glm','--spec-file',str(root/'frozen/model-specs.json'),
      '--harbor-launcher',str(root/'frozen/harbor.sh'),
      '--directory',str(root/'glm-pilot-service'),'--config',str(root/'pilot-full-glm.json')]
try:
    code=subprocess.run(argv).returncode
    config=json.loads((root/'pilot-full-glm.json').read_text())
    report=validate(Path(config['jobs_dir'])/config['job_name'])
    report['lifecycle_returncode']=code
    report['passed']=report['passed'] and code==0
except Exception as exc:
    report={'passed':False,'error_type':type(exc).__name__,'reason':str(exc)}
(root/'full-deployment-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
raise SystemExit(0 if report['passed'] else 1)
