"""Exercise larger observations plus the retained fail-closed scope/size guards."""
import ast,json,os,subprocess,sys,tempfile
from pathlib import Path
J=Path(__file__).resolve().parent
sys.path.insert(0,str(J/'frozen/saber'))
from harness_adapters.codex_native_adapter import CodexNativeHarnessAdapter
root=Path(tempfile.mkdtemp(prefix='observer-capacity-',dir=J/'preflight'))
work=root/'work';work.mkdir()
for i in range(600):(work/f'{i:04d}.txt').write_text('safe sample\n')
(work/'large.json').write_text(json.dumps({'sample':'x'*1500000}))
tree=ast.parse((J/'frozen/saber/sandbox_shell.py').read_text())
script=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_WORKSPACE_SNAPSHOT_OBSERVER' for t in n.targets))
r=subprocess.run([sys.executable,'-I','-S','-c',script],input=json.dumps({'cwd':str(work),'paths':[]}),text=True,capture_output=True,check=True)
report=json.loads(r.stdout);assert report['complete'] and len(report['file_contents'])==601,report.get('errors')
a=object.__new__(CodexNativeHarnessAdapter);a.last_run_meta={}
snap=root/'snapshot.json';initial={'policy_file_contents':{},'file_contents':{},'policy_initialized':False};snap.write_text(json.dumps(initial));env={'SAFETY_ORCH_WORKSPACE_SNAPSHOT':str(snap)}
class Runtime:
    def snapshot_workspace(self,**kwargs):return report
runtime=Runtime();a._refresh_workspace_snapshot(runtime,str(work),env);assert json.loads(snap.read_text())['snapshot_status']=='ready'
for failure in ['outside_scope','oversize','incomplete']:
    snap.write_text(json.dumps(initial))
    report={'complete':True,'file_contents':{},'errors':{},'excluded_files':{},'deleted_paths':[]}
    if failure=='outside_scope':report['file_contents']={'/etc/should-not-be-read':'x'}
    if failure=='oversize':report['file_contents']={str(work/'big.txt'):'x'*16000001}
    if failure=='incomplete':report['complete']=False
    try:a._refresh_workspace_snapshot(runtime,str(work),env)
    except RuntimeError:pass
    else:raise AssertionError('Fail-closed guard bypassed: '+failure)
    assert json.loads(snap.read_text())['snapshot_status']=='unavailable'
(J/'preflight/observer-capacity.json').write_text(json.dumps({'passed':True,'tested_files':601,'large_text_bytes':1500000,'guards':['outside_scope','oversize','incomplete'],'artifacts':str(root)},indent=2))
print('PASS: 601 files, 1.5 MB text; scope/size/incomplete guards retained')
