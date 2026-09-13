"""Replay only a completed task's official verifier, preserving original evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import tomllib

sys.path.insert(0, '/srv/benchmark/skills/projects/terminal-bench-aistation')
from verifier_integrity import assess_verifier

DATASET = Path('/srv/benchmark/skills/datasets/terminal-bench-2.1-7131e437-transport-r1')
ALLOWED_ROOTS = [Path('/srv/benchmark/skills/results/terminal-api-foreign-20260913-r1'), Path('/srv/benchmark/skills/results/terminal-gptoss-skills-20260913-r1')]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);args=parser.parse_args()
    source=args.source.resolve()
    if not any(source.is_relative_to(root) for root in ALLOWED_ROOTS):raise ValueError('Unowned source')
    result_path=source/'result.json';row=json.loads(result_path.read_text())
    if row.get('exception_info'):raise ValueError('Only completed attempts are eligible for this verifier-only replay')
    runtimes=list((source/'aistation').glob('*/runtime.json'))
    if len(runtimes)!=1:raise ValueError('Ambiguous runtime ownership')
    session=runtimes[0].parent.name
    if not session.startswith(('rick-saber-tbretry-','rick-saber-tbapi-','rick-saber-terminal-','rick-saber-tbgptoss-')):raise ValueError('Unowned session prefix')
    ids=subprocess.check_output(['docker','ps','-q','--filter','label=skilldistill.session='+session,'--filter','label=com.docker.compose.service=main'],text=True).split()
    if len(ids)!=1:raise ValueError('Exactly one retained running task container required')
    info=json.loads(subprocess.check_output(['docker','inspect',ids[0]],text=True))[0]
    labels=info['Config']['Labels']
    if labels.get('skilldistill.benchmark')!='terminal-bench' or labels.get('skilldistill.session')!=session or not info['Name'].lstrip('/').startswith(session+'-'):raise ValueError('Container name/label mismatch')
    task=row['task_name'].removeprefix('terminal-bench/');tests=DATASET/task/'tests'
    timeout=int(tomllib.loads((DATASET/task/'task.toml').read_text()).get('verifier',{}).get('timeout_sec',1200))
    # Refuse replay against a changed test suite.
    hashes={}
    for p in tests.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(tests).as_posix()
        actual=subprocess.check_output(['docker','exec',ids[0],'cat','/tests/'+rel])
        expected=p.read_bytes()
        if actual!=expected:raise ValueError('Container verifier differs from pinned dataset: '+rel)
        hashes[rel]=hashlib.sha256(actual).hexdigest()
    stamp='repair-'+uuid.uuid4().hex[:12];output=source/'verifier'/stamp;output.mkdir()
    target='/logs/verifier/'+stamp
    original=(tests/'test.sh').read_text()
    script=original.replace('/logs/verifier/',target+'/')
    (output/'test.transport.sh').write_text(script)
    argv=['docker','exec','-i']
    env={k:'http://private-host-fb6337b4cc5a.invalid:7899' for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']}
    env.update(ALL_PROXY='',all_proxy='',NO_PROXY='localhost,127.0.0.1',no_proxy='localhost,127.0.0.1',PIP_INDEX_URL='https://pypi.org/simple',PIP_EXTRA_INDEX_URL='',UV_DEFAULT_INDEX='https://pypi.org/simple',UV_INDEX_URL='https://pypi.org/simple')
    for k,v in env.items():argv.extend(['-e',k+'='+v])
    argv.extend([ids[0],'timeout','--signal=TERM','--kill-after=5s',str(timeout)+'s','bash','-s'])
    request={'source':str(source),'source_result_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest(),'container_id':info['Id'],'session':session,'test_sha256':hashes,'changed_only':'package transport environment and verifier output directory','model_api_calls':0,'verifier_timeout_seconds':timeout,'started_at_utc':datetime.now(timezone.utc).isoformat()}
    (output/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    with (output/'test-stdout.txt').open('w') as log:
        try:r=subprocess.run(argv,input=script,text=True,stdout=log,stderr=subprocess.STDOUT,timeout=timeout+30);rc=r.returncode
        except subprocess.TimeoutExpired:rc=124
    try:reward=float((output/'reward.txt').read_text())
    except (OSError,ValueError):reward=None
    verdict=assess_verifier(output,reward)
    if rc not in (0,1):verdict={'valid':False,'reason':'verifier_process_error'}
    complete={**request,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'returncode':rc,'reward':reward,'integrity':verdict,'output':str(output)}
    (output/'completion.json').write_text(json.dumps(complete,indent=2)+'\n')
    print(json.dumps(complete,indent=2),flush=True)
    if not verdict['valid']:raise SystemExit(1)

if __name__=='__main__':main()
