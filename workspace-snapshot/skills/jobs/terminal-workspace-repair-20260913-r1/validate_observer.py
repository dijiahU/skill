"""Read retained task workspaces; retain full observations and compact evidence."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import time

JOB = Path(__file__).resolve().parent
tree = ast.parse((JOB / 'frozen/saber/sandbox_shell.py').read_text())
observer = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '_WORKSPACE_SNAPSHOT_OBSERVER' for t in n.targets))
observer += '\nimport resource; print(json.dumps({"peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),file=sys.stderr)\n'
targets = [('csv', '69743bef8427'), ('ppm', '01ec73737cf0'), ('c4', 'cbfd1f467246')]
for task, container in targets:
    info = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
    labels = info['Config']['Labels']
    assert labels['skilldistill.benchmark'] == 'terminal-bench'
    assert info['Name'].lstrip('/').startswith(labels['skilldistill.session'] + '-')
    assert labels['skilldistill.session'].startswith('rick-saber-tbretry-20260913-r1-')
    out = JOB / 'preflight' / (task + '-snapshot.json')
    start = time.monotonic()
    with out.open('x') as stream:
        proc = subprocess.run(['docker', 'exec', '-i', container, 'timeout', '125s',
                               'python3', '-I', '-S', '-c', observer],
                              input=json.dumps({'cwd': '/app', 'paths': []}), text=True,
                              stdout=stream, stderr=subprocess.PIPE, timeout=140)
    elapsed = time.monotonic() - start
    report = json.loads(out.read_text())
    hashes = {p: hashlib.sha256(v.encode()).hexdigest() for p, v in report['file_contents'].items()}
    # Independently hash regular source files; compare every observed text file.
    audit = 'import os,json,hashlib; print(json.dumps({os.path.join(d,f):hashlib.sha256(open(os.path.join(d,f),"rb").read()).hexdigest() for d,ds,fs in os.walk("/app") for f in fs if not os.path.islink(os.path.join(d,f))}))'
    expected = json.loads(subprocess.check_output(['docker', 'exec', container, 'python3', '-I', '-S', '-c', audit]))
    evidence = {'task': task, 'container': container, 'returncode': proc.returncode,
                'complete': report['complete'], 'files': len(hashes),
                'bytes': report['observed_bytes'], 'seconds': elapsed,
                'resource': proc.stderr.strip(), 'errors': report['errors'],
                'all_text_hashes_match': all(expected[p] == h for p, h in hashes.items()),
                'unaccounted_paths': sorted(set(expected) - set(hashes) - set(report['excluded_files']))}
    (JOB / 'preflight' / (task + '-observer-evidence.json')).write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence), flush=True)
    assert proc.returncode == 0 and report['complete'] and evidence['all_text_hashes_match'] and not evidence['unaccounted_paths']
