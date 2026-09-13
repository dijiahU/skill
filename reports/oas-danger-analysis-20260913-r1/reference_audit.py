import collections
import csv
import json
import re
from pathlib import Path
root=Path(__file__).resolve().parent
rows=json.loads((root/'coverage-records.json').read_text())
ref=re.compile(r'references/archetypes/([a-z0-9][a-z0-9-]*\.md)')
checks=[]
for row in rows:
    p=Path(row['trajectory'])
    if not p.exists():continue
    events=json.loads(p.read_text())
    observations={e.get('action_id'):e for e in events if e.get('kind')=='ObservationEvent'}
    for i,event in enumerate(events):
        if event.get('kind')!='ActionEvent':continue
        action=event.get('action') or {}
        refs=ref.findall(json.dumps(action))
        if not refs:continue
        obs=(observations.get(event.get('id')) or {}).get('observation') or {}
        body='\n'.join(str(v.get('text','')) for v in obs.get('content',[]) if isinstance(v,dict))
        status='missing_observation' if not obs else 'read_failed' if re.search(r'No such file|does not exist|cannot open|not found',body,re.I) else 'tool_error' if obs.get('is_error') or obs.get('exit_code') not in [None,0] else 'tool_succeeded_content_unverified'
        checks.append(dict(model=row['model'],task=row['task'],raw_score=row['raw_score'],event_index=i,
                           references=sorted(set(refs)),status=status,trajectory=str(p),
                           error_lines=[line[:250] for line in body.splitlines() if re.search(r'No such file|does not exist|cannot open',line,re.I)][:5]))
(root/'reference-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
for model in sorted(set(row['model'] for row in rows)):
    rs=[r for r in checks if r['model']==model]
    print(model,'attempt_actions',len(rs),'tasks',len(set(r['task'] for r in rs)),'failed_tasks',len(set(r['task'] for r in rs if r['status']=='read_failed')),'statuses',dict(collections.Counter(r['status'] for r in rs)))
