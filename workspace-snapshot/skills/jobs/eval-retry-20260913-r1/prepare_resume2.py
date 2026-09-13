"""Prepare an isolated continuation of the interrupted supplemental queue."""
import copy
import hashlib
import json
import shutil
import socket
import sys
import time
from pathlib import Path

OLD = Path(__file__).resolve().parent
NEW = OLD.with_name('eval-retry-20260913-r2')
OJ = OLD.parent / 'oas-api222-20260912-r1/skills100'
sys.path.insert(0, str(OJ))
from resume_helpers import read_stage, valid

if NEW.exists():
    raise RuntimeError('Resume directory already exists; inspect before resubmission')
NEW.mkdir()
for name in ['logs', 'configs', 'preflight']:
    (NEW / name).mkdir()
(NEW / 'frozen').symlink_to(OLD / 'frozen', target_is_directory=True)
for name in ['oas_api.py', 'local_retry.py', 'terminal_common.py', 'api_terminal.py',
             'lifecycle.py', 'cuda_probe.py', 'progress.py', 'run.sh', 'harbor.sh']:
    text = (OLD / name).read_text().replace(str(OLD), str(NEW))
    if name == 'oas_api.py':
        text = text.replace('supplement-20260913-r1-', 'supplement-20260913-r2-')
    if name in ['local_retry.py', 'terminal_common.py']:
        text = text.replace('retry1', 'resume2')
    (NEW / name).write_text(text)
    if name.endswith('.sh'):
        (NEW / name).chmod(0o755)

network = (OLD / 'network.sh').read_text()
network = network.replace('export NO_PROXY=',
    'bench_pod_address="$(hostname -i | awk \'{print $1}\')"\nexport NO_PROXY=')
network = network.replace('private-host-e3205d07ce94.invalid', '${bench_pod_address}')
network += '\nunset bench_pod_address\n'
(NEW / 'network.sh').write_text(network)

plan = copy.deepcopy(json.loads((OLD / 'plan.json').read_text()))
plan.update(created_at=time.time(), parent_job=str(OLD),
            user_request='那重新恢复一下',
            retry_policy='Continue only tasks without a returned result in the interrupted wave; retain all returned valid and invalid attempts',
            runtime_identity={'hostname': socket.gethostname(),
                              'pod_ip': socket.gethostbyname(socket.gethostname()),
                              'pid1_start_ticks': Path('/proc/1/stat').read_text().split()[21]})
audit = {'oas': {}, 'terminal': {}}
for key, cfg in plan['oas'].items():
    model = cfg['model']
    if cfg['condition'] == 'skills100':
        stage = (f'skills100-{model}-supplement-20260913-r1-full' if model != 'gptoss'
                 else 'skills100-gptoss-local-20260913-r1-retry1')
        returned = read_stage(model, stage)
    else:
        # Neither baseline phase had started when the Pod restarted.
        assert not (OLD / f'state-oas-{key}.json').exists()
        returned = {}
    prior = list(cfg['tasks'])
    cfg['tasks'] = [task for task in prior if task not in returned]
    cfg['prior_valid'] += sum(valid(row) for row in returned.values())
    cfg['already_returned_in_parent'] = sorted(returned)
    audit['oas'][key] = {'parent_planned': len(prior), 'returned': len(returned),
                         'resume_tasks': len(cfg['tasks'])}
for model, cfg in plan['terminal'].items():
    local = model == 'gptoss'
    base = plan['local_terminal_plan'] if local else plan['terminal_plan']
    stage = ('rick-saber-tbgptoss-20260913-r1-retry1' if local else
             f'rick-saber-tbapi-{model}-20260913-r1-retry1')
    returned = {}
    for p in (Path(base['results_root']) / stage).glob('*/result.json'):
        row = json.loads(p.read_text())
        returned[row['task_name'].removeprefix('terminal-bench/')] = row
    prior = list(cfg['tasks'])
    cfg['tasks'] = [task for task in prior if task not in returned]
    cfg['already_returned_in_parent'] = sorted(returned)
    audit['terminal'][model] = {'parent_planned': len(prior), 'returned': len(returned),
                               'resume_tasks': len(cfg['tasks'])}
total = sum(len(c['tasks']) for group in ['oas', 'terminal'] for c in plan[group].values())
assert total == 375, (total, audit)
plan['planned_tasks'] = total
(NEW / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
(NEW / 'preflight/resume-selection.json').write_text(json.dumps(audit, indent=2) + '\n')
shutil.copy2(OLD / 'preflight/before-retry-snapshot.json', NEW / 'preflight/before-retry-snapshot.json')
(NEW / 'README.md').write_text('''# 重启后的补跑恢复

2026-09-13 用户授权恢复。原补跑在 Pod 于 14:50 重启时中断；此次只接续没有返回结果的 375 个模型任务，已经返回的 42 个结果（包括有效 0 分和异常）全部保留。

- OAS skills：GLM 4、DeepSeek 2、Qwen 82、gpt-oss 6 题。
- OAS baseline：DeepSeek 13、Qwen 184 题，分别排在同模型 skills 后；Qwen 仍先验证两题隔离。
- Terminal skills：GPT 15、Gemini 51、gpt-oss 18 题。
- 沿用原并发、模型、100 步 OAS 配置、Terminal 官方超时及修复后的完整 skills/hooks；共享上批冻结代码。
- 动态获取当前 Pod 地址；本机接口与宿主 Docker 直连，外部 API 使用既有代理。
- GPU 0 跑 gpt-oss OAS、GPU 1 跑 gpt-oss Terminal，均通过 gpu-idle 预约完整生命周期。
- 仅清理上批 OAS 对应阶段中同时符合原前缀和会话标签的已授权容器；Terminal 保留容器。
- 原始输出、旧控制状态和有效成绩不覆盖。恢复阶段另用 supplement-r2 / resume2 名称。

逐题清单见 plan.json；选择依据见 preflight/resume-selection.json；运行状态见 progress.py。
''')
(NEW / 'submission-sha256.json').write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in NEW.iterdir() if p.is_file()}, indent=2) + '\n')
print(json.dumps({'job': str(NEW), 'total': total, **audit}, ensure_ascii=False, indent=2))
