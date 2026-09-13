"""Create a read-only-derived, credential-free evaluation snapshot."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE = Path('/srv/benchmark/skills')
sys.path.insert(0, str(BASE / 'projects/terminal-bench-aistation'))
from verifier_integrity import assess_trial
OUT = Path(__file__).resolve().parent
OJ = BASE / 'jobs/oas-api222-20260912-r1/skills100'
OR = BASE / 'results/oas-api222-20260912-r1'
TJ = BASE / 'jobs/terminal-api-foreign-20260913-r1'
TR = BASE / 'results/terminal-api-foreign-20260913-r1'
RJ = BASE / 'jobs/eval-retry-20260913-r2'
sys.path.insert(0, str(OJ))
from resume_helpers import valid

START = datetime.now(timezone.utc).isoformat(timespec='seconds')
inputs = {}
def read(path):
    path = Path(path)
    data = path.read_bytes()
    inputs[str(path)] = hashlib.sha256(data).hexdigest()
    return json.loads(data)
def rows(path):
    data = path.read_bytes()
    inputs[str(path)] = hashlib.sha256(data).hexdigest()
    out = []
    for line in data.splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out

def category(row, budget):
    test = row.get('test_result') or {}
    detail = test.get('skilldistill') or {}
    error = ' '.join(str(x or '') for x in [row.get('error'), test.get('error'), detail.get('conversation_error')])
    for token, name in [('MaxIterationsReached', f'{budget}步上限'), ('Remote conversation got stuck', '对话卡住'),
                        ('account balance is insufficient', '余额不足'), ('TPM limit reached', 'TPM限流'),
                        ('RateLimitError', 'API限流'), ('Timeout', '超时'), ('timed out', '超时'),
                        ('Evaluation failed', '评分异常'), ('Evaluator', '评分异常'),
                        ('Remote conversation ended with error', '远程对话异常')]:
        if token in error:
            return name
    return '未取得有效评分'

def output_csv(name, data, fields):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)

def pct(a, b):
    return f'{100*a/b:.2f}%' if b else '—'
def fmt(x):
    return f'{x:g}' if isinstance(x, (int, float)) else str(x)
def link(path, label=None):
    p = Path(path)
    return f'[{label or p.name}]({p})'

excluded = set(read(OJ / 'unscorable-tasks.json')['task_ids'])
ids = (OJ / 'tasks222.txt').read_text().splitlines()
assert len(ids) == 222 and len(excluded) == 38
model_names = {'glm5':'GLM-5.1', 'deepseek-flash':'DeepSeek-V4-Flash', 'qwen':'Qwen3.8-27B', 'gptoss':'gpt-oss-120B（本机 GPU）'}
oas = []; task_rows = []; attempt_rows = []; stage_rows = []
for condition, parent, models, budget in [('baseline30',OR,['glm5'],30), ('baseline100',OR/'baseline100',['deepseek-flash','qwen'],100), ('skills100',OR/'skills100',['glm5','deepseek-flash','qwen','gptoss'],100)]:
    for model in models:
        root = parent/model
        chosen = {}
        for stage in sorted(root.iterdir(), key=lambda p:p.stat().st_mtime) if root.exists() else []:
            if not stage.is_dir():
                continue
            stage_data = {}
            for p in list(stage.rglob('output.critic_attempt_1.jsonl')) or list(stage.rglob('output.jsonl')):
                for row in rows(p):
                    stage_data[row['instance_id']] = (row,p)
            good_stage = []
            for task,(row,path) in stage_data.items():
                good = valid(row) and task not in excluded
                score = (row.get('test_result') or {}).get('final_score') or {}
                record = {'benchmark':'OAS','condition':condition,'model':model_names[model], 'task':task,
                          'stage':stage.name,'status':'excluded_unscorable' if task in excluded else 'valid' if good else 'invalid',
                          'points':score.get('result') if good else '', 'total':score.get('total') if good else '',
                          'reason':'不可评分，用户要求排除' if task in excluded else '' if good else category(row, budget),'source':str(path)}
                attempt_rows.append(record)
                if good:
                    good_stage.append(record)
                if task not in chosen or not valid(chosen[task][0]):
                    chosen[task] = (row,record)
            stage_rows.append({'condition':condition,'model':model_names[model],'stage':stage.name,'returned':len(stage_data),'valid_excluding_38':len(good_stage),'points':sum(v['points'] for v in good_stage),'total':sum(v['total'] for v in good_stage),'source':str(stage)})
        good=[]; bad=Counter()
        for task in ids:
            if task in chosen:
                row,record=chosen[task]
                record=dict(record)
            else:
                row={};record={'benchmark':'OAS','condition':condition,'model':model_names[model],'task':task,'stage':'','status':'no_output','points':'','total':'','reason':'暂无输出','source':''}
            if task in excluded:
                record.update(status='excluded_unscorable',points='',total='',reason='不可评分，用户要求排除')
            elif record['status']=='valid':
                good.append(record)
            else:
                bad[record['reason']]+=1
            task_rows.append(record)
        state=None
        prefixes=['baseline1-state-'] if condition=='baseline100' else ['held-retry1-state-','repair4-state-'] if condition=='skills100' else []
        for prefix in prefixes:
            p=OJ/(prefix+model+'.json')
            if p.exists():
                state=read(p).get('status');break
        if condition=='baseline30':status='历史批次结束；未补齐'
        elif state and state.startswith('cancelled'):status='已取消，未开始'
        elif state and ('running' in state):status='运行中'
        elif state and ('finished' in state or 'ended' in state):status='已提交批次结束；未补齐'
        else:status=state or ('批次结束；未补齐' if model=='gptoss' else '未开始')
        active=OJ/(('active-baseline-stage-' if condition=='baseline100' else 'active-stage-')+model+'.json')
        alive=False
        if condition!='baseline30' and active.exists():
            a=read(active);proc=Path('/proc')/str(a['pid'])/'cmdline'
            alive=proc.exists() and b'run_stage.py' in proc.read_bytes()
            if alive:status='运行中'
        retry_state=RJ/f'state-oas-{condition}-{model}.json'
        if retry_state.exists():
            rs=read(retry_state);status=rs['status']
            pp=Path('/proc')/str(rs.get('controller_pid',0))/'cmdline'
            controller_alive=pp.exists() and (b'oas_api.py' in pp.read_bytes() or b'local_retry.py' in pp.read_bytes())
            if controller_alive and status.startswith('running'):status='补跑中'
            elif not controller_alive and status.startswith(('running', 'checking')):status='已中断：控制进程不存在'
        elif condition=='baseline100' and model in ['qwen','deepseek-flash'] and (RJ/'launch.json').exists():
            launch=read(RJ/'launch.json')['processes'].get('oas-'+model,{})
            pp=Path('/proc')/str(launch.get('pid',0))/'cmdline'
            if pp.exists() and b'oas_api.py' in pp.read_bytes():status='排队，等待同模型 skills 补跑结束'
        elif model=='gptoss' and (RJ/'lifecycle-oas.json').exists():
            rs=read(RJ/'lifecycle-oas.json')
            if not rs.get('services_released_at'):status='本机 GPU 补跑服务启动中'
        oas.append({'condition':condition,'model':model_names[model],'model_id':model,'valid':len(good),'eligible':184,'points':sum(v['points'] for v in good),'total':sum(v['total'] for v in good),'unresolved':184-len(good),'status':status,'budget':budget,'reasons':dict(bad),'root':str(root),'runner_alive':alive})

term_tasks=[]; terminal=[]; term_attempts=[]
CLAUDE_JOB=BASE/'jobs/terminal-api-claude-20260913-r1'
LOCAL_JOB=BASE/'jobs/gptoss-oas-terminal-20260913-r1'
LOCAL_RESULTS=BASE/'results/terminal-gptoss-skills-20260913-r1'
for model,name in [('gpt','GPT-5.6 Sol'),('gemini','Gemini 3.8 Flash'),('gptoss','gpt-oss-120B（本机 GPU）'),('claude','Claude Opus 5')]:
    root=LOCAL_RESULTS if model=='gptoss' else TR
    state_path=LOCAL_JOB/'state-terminal.json' if model=='gptoss' else CLAUDE_JOB/'state-claude.json' if model=='claude' else TJ/f'state-{model}.json'
    state=read(state_path);chosen={};phase_rows=[]
    retry_state=RJ/f'state-terminal-{model}.json'
    if retry_state.exists():state=read(retry_state)
    elif model=='gptoss' and (RJ/'lifecycle-terminal.json').exists() and not read(RJ/'lifecycle-terminal.json').get('services_released_at'):state=dict(state,status='本机 GPU 补跑服务启动中')
    workspace_job=BASE/'jobs/terminal-workspace-repair-20260913-r1'
    workspace_state=workspace_job/f'state-terminal-{model}.json'
    if model!='claude' and workspace_state.exists():
        ws=read(workspace_state)
        if ws.get('status','').startswith('queued'):
            state=dict(state,status=state['status']+'；大工作区修复补跑排队中')
        else:
            state=ws
            if ws.get('stages'):state=dict(state,runner_pid=ws['stages'][-1].get('runner_pid',0))
    elif model=='gptoss' and (workspace_job/'lifecycle-terminal.json').exists() and not read(workspace_job/'lifecycle-terminal.json').get('services_released_at'):
        state=dict(state,status='大工作区修复：本机 GPU 服务启动中')
    pattern='rick-saber-tbgptoss-*' if model=='gptoss' else f'rick-saber-tbapi-{model}-*'
    for directory in sorted(root.glob(pattern), key=lambda p:p.stat().st_mtime):
        count=0
        for p in directory.glob('*/result.json'):
            row=read(p);task=row['task_name'];count+=1
            rewards=(row.get('verifier_result') or {}).get('rewards') or {}
            err=row.get('exception_info') or {}
            score=rewards.get('reward')
            for evidence_path in (p.parent/'verifier').glob('*.json'):
                inputs[str(evidence_path)]=hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            integrity=assess_trial(p, row)
            scored=integrity['valid']
            score=integrity.get('reward', score)
            if integrity.get('verifier_replay'):read(integrity['verifier_replay'])
            meta_path=p.parent/'agent/native-metadata.json'
            meta=read(meta_path) if meta_path.exists() else {}
            rec={'benchmark':'Terminal-Bench 2.1','condition':'skills','model':name,'task':task,'stage':directory.name,
                 'status':'valid' if scored else 'invalid','points':score if scored else '', 'total':1 if scored else '',
                 'reason':integrity['reason'] if not scored else '', 'source':str(p),
                 'verifier_replay':integrity.get('verifier_replay',''),
                 'tool_calls':meta.get('tool_calls'),'hook_runs':meta.get('hook_runs'),'router_preloaded':meta.get('router_preloaded'),
                 'termination_reason':meta.get('termination_reason'),'turn_status':meta.get('turn_status')}
            term_attempts.append(rec)
            if task not in chosen or chosen[task]['status']!='valid':chosen[task]=rec
        phase_rows.append({'phase':directory.name,'returned':count})
    term_tasks.extend(chosen.values())
    good=[v for v in chosen.values() if v['status']=='valid']
    proc=Path('/proc')/str(state.get('runner_pid',0))/'cmdline'
    alive=proc.exists() and b'harbor' in proc.read_bytes()
    if not alive and state['status'].startswith('running'):
        state=dict(state,status='已中断：运行进程不存在')
    terminal.append({'model':name,'model_id':model,'returned':len(chosen),'scored':len(good),'passed':sum(v['points']==1 for v in good),'points':sum(v['points'] for v in good),'errors':len(chosen)-len(good),'pending':89-len(chosen),'planned':89,'status':state['status'],'runner_alive':alive,'phases':phase_rows,'source':str(root)})

history=[];history_trials=[];regrade_inventory=[]
hr=BASE/'results/terminal-bench'
for directory in sorted(hr.iterdir()):
    if not directory.is_dir():continue
    config=read(directory/'config.json') if (directory/'config.json').exists() else {}
    job=read(directory/'result.json') if (directory/'result.json').exists() else {}
    groups=defaultdict(list)
    for p in directory.glob('*/result.json'):
        row=read(p)
        if 'task_name' not in row:continue
        agent=(row.get('config') or {}).get('agent') or {}
        model=agent.get('model_name') or ((row.get('agent_info') or {}).get('model_info') or {}).get('name') or 'oracle/未标注'
        cond='skills' if agent.get('kwargs',{}).get('treatment') is True or 'FullSafety' in str(agent.get('import_path')) else 'baseline' if 'Baseline' in str(agent.get('import_path')) else 'oracle/其他'
        reward=((row.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        err=row.get('exception_info')
        scored=isinstance(reward,(int,float)) and not err
        rec={'batch':directory.name,'model':model,'condition':cond,'task':row['task_name'],'scored':scored,'reward':reward if scored else '', 'error_type':(err or {}).get('exception_type','') if err else '', 'source':str(p)}
        groups[(model,cond)].append(rec);history_trials.append(rec)
    datasets=[x.get('path',x.get('name','')) for x in config.get('datasets',[])]
    for (model,cond),rs in groups.items():
        good=[x for x in rs if x['scored']]
        history.append({'batch':directory.name,'model':model,'condition':cond,'returned':len(rs),'scored':len(good),'passed':sum(x['reward']==1 for x in good),'points':sum(x['reward'] for x in good),'errors':len(rs)-len(good),'planned_all_conditions':job.get('n_total_trials'),'saved_finished_at':job.get('finished_at'),'dataset':'; '.join(datasets),'source':str(directory)})
    if not groups:
        regrade_inventory.append({'batch':directory.name,'source':str(directory),'note':'无标准逐题 result.json；保留为重评分目录，不并入推理统计'})

public=[]
google='https://deepmind.google/models/model-cards/gemini-3-8-flash/'
method='https://deepmind.google/models/evals-methodology/gemini-3-8-flash'
leader='https://www.tbench.ai/leaderboard/terminal-bench/2.1'
for model,score in [('Gemini 3.8 Flash',89.4),('Claude Opus 5',89.1),('GPT-5.6 Sol',88.8),('GPT-5.6 Terra',87.4),('Gemini 3.7 Flash',85.8),('Claude Sonnet 5',80.4)]:
    public.append({'source_group':'Google模型卡对照表','model':model,'agent':'Terminus 2（方法说明口径）','effort':'表中未逐项列出','score_percent':score,'source':google,'methodology':method})
for model,agent,effort,score in [('GPT-6 Astra','Codex','high',87.4),('Claude Fable 5','Claude Code','xhigh',83.8),('GPT-5.5','Codex','xhigh',83.2),('Grok 4.5','Cursor CLI','high',79.3),('Claude Opus 4.8','Claude Code','high',78.9),('GPT-5.6 Terra','Codex','max',78.4),('Muse Spark 1.1','mini-SWE-agent','xhigh',76.2),('GPT-5.6 Luna','Codex','max',75.7),('Claude Sonnet 5','Claude Code','high',74.6),('Gemini 3 Pro','Terminus 2','high',73.9),('Claude Opus 4.7','Claude Code','max',68.9),('Gemini 3.1 Pro','Gemini CLI','high',65.8),('GLM-5.1','Claude Code','max',58.6)]:
    public.append({'source_group':'官方2.1榜单检索快照，每模型最高一条','model':model,'agent':agent,'effort':effort,'score_percent':score,'source':leader,'methodology':'榜单提供 k=5 的运行命令；模型、Agent 和推理强度不同'})

prefs=read(BASE/'jobs/api-benchmarks-20260912/evaluation-preferences.json')
END=datetime.now(timezone.utc).isoformat(timespec='seconds')
snapshot={'capture_started_utc':START,'capture_finished_utc':END,'scope':'本轮 API OAS、API Terminal 及现有 Terminal 历史结果目录；不混合不同基准版本', 'oas':oas,'terminal_api':terminal,'historical_terminal':history,'nonstandard_history_dirs':regrade_inventory,'public_scores':public,'preferences':prefs,'excluded_oas':sorted(excluded)}
(OUT/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
(OUT/'input-sha256.json').write_text(json.dumps(inputs,indent=2)+'\n')
output_csv('oas-per-task.csv',task_rows,['benchmark','condition','model','task','status','points','total','reason','stage','source'])
output_csv('oas-all-attempts.csv',attempt_rows,['benchmark','condition','model','task','status','points','total','reason','stage','source'])
output_csv('oas-stages.csv',stage_rows,['condition','model','stage','returned','valid_excluding_38','points','total','source'])
output_csv('terminal-all-attempts.csv',term_attempts,['benchmark','condition','model','task','status','points','total','reason','stage','source'])
output_csv('terminal-api-per-task.csv',term_tasks,['benchmark','condition','model','task','status','points','total','reason','stage','tool_calls','hook_runs','router_preloaded','termination_reason','turn_status','source','verifier_replay'])
output_csv('terminal-verifier-pending.csv',[dict(r, repair_status='pending_verifier_review_or_replay') for r in term_tasks if r['status']=='invalid' and r['reason'].startswith(('verifier_', 'reward_test_'))],['model','task','reason','repair_status','source'])
output_csv('terminal-history.csv',history,['batch','model','condition','dataset','returned','scored','passed','points','errors','planned_all_conditions','saved_finished_at','source'])
output_csv('terminal-history-per-task.csv',history_trials,['batch','model','condition','task','scored','reward','error_type','source'])
output_csv('public-terminal21-scores.csv',public,['source_group','model','agent','effort','score_percent','source','methodology'])

L=[]
def add(s=''):L.append(s)
add('# 模型评测结果汇总：OAS、SABER、Terminal-Bench 与公开参考成绩')
add()
add(f'本地数据采集窗口（运行环境 UTC）：**{START} 至 {END}**。这是一次静态快照，正在运行的任务随后会产生新结果。目录日期使用本次会话日期 2026-09-13；采集时间按运行环境时钟原样记录。')
add()
add('## 1. 范围与当前结论')
add()
add('本文覆盖已有 SABER 各版本成绩（第 9 节）、本轮 OAS 的 baseline/skills、GPT/Gemini/Claude/gpt-oss 的 Terminal-Bench 2.1 skills、现有 Terminal 历史结果目录，以及本会话刚检索到的 Terminal-Bench 2.1 公开成绩。历史数据按批次与条件分开，未把不同版本、模型或重复尝试混成总分。')
add()
add('- 用户最新决定：保留现有有效成绩，补跑异常与缺失项。Qwen OAS baseline 已恢复；新模型按 skills/hooks 条件运行。旧 GLM 30 步 baseline 作为历史结果保留。')
add('- Terminal 当前包含 GPT-5.6 Sol、Gemini 3.8 Flash、Claude Opus 5 和本机 GPU gpt-oss-120B，各 89 题、带 skills/hooks。Claude 当前按用户要求暂停，已有结果与容器保留；未经用户指示不恢复推理。')
add('- OAS 原 222 题中 38 题无可运行评分逻辑，已按用户决定排除；可评分集合为 184 题。')
add('- 批次结束不等于每题都有有效成绩；只有测试确实运行后的 0 分才是有效成绩；依赖安装失败、评分未运行或缺评分，标为待重评分。')
add('- SABER 国外模型仅有 API/原生适配器前置验证，未取得本轮正式任务成绩；不能把 Terminal 使用 SABER 适配器误写成 SABER 基准已完成。')
add()
add('本次补跑计划：'+link(RJ/'README.md','范围与配置')+'、'+link(RJ/'plan.json','逐题清单')+'。启动前快照：'+link(RJ/'preflight/before-retry-snapshot.json')+'。补跑仅选择异常和未评分题，新增尝试单列，保留首个有效成绩。')
add()
add('Terminal 前一轮适配器容量为 8192 文件、单文件 16 MB、总计 128 MB，仍无法处理部分官方任务。2026-09-13 的 wsrepair1 修复改为逐文件输出完整快照、通过 stdin 传递文件清单，并在同一 matcher 进程内复用一次快照解析；新上限为 32768 文件、单文件 64 MB、总计 2 GB，以容纳 C4 输入与输出共存。观察器和验证器同步修改，路径/遗漏校验保留。匹配器异常现按 fail-closed 拒绝，官方任务超时和测试断言不变；这些条件差异单独记录，不能视为严格同条件重复。验证涵盖 CSV、PPM、C4 的全部文本哈希与四个 hooks。详见 '+link(BASE/'jobs/terminal-workspace-repair-20260913-r1/README.md','修复与补跑记录')+'。')
add('Verifier 修复只对评分未运行的保留产物重评分，不重新调用模型。Torch 任务先准备 Python 3.13、pytest 8.4.1、torch 2.7.0、transformers 4.55.0 等官方固定依赖，再在官方测试时限内运行原测试；依赖准备时间单列，未替换 CPU 版本或放宽断言。已有有效 0 分保留，不为提分重跑。')
add()
add('## 2. 分数口径')
add()
add('OAS：有效评分要求沿用运行器判定（无顶层运行错误、不是残缺轨迹评分、result/total 为数值且 total>0），并排除 38 道不可评分题。累计得分率＝已有效评分题的实得分÷对应满分；不是完成率。原始评分检查的含义随题目而异，不能把该比率直接称为安全通过率。')
add()
add('OAS 重试合并采用“已有有效成绩保留，未有效时选后续尝试”的既有规则，不按最高分挑选。合并顺序按阶段目录修改时间；snapshot 与逐题 CSV 固定了此次选用的来源。跨条件对比还存在不同有效题集合与重试次数带来的偏差。')
add()
add('本轮 Terminal 2.1：无运行异常、reward 为 0/1，且 CTRF 报告确认测试已执行、计数完整、与 reward 一致，才计为有效评分。评分器启动失败标为无有效评分，待重评分。原始结果不改写；仅原评分无效时，采用同一保留产物的首个通过有效性检查的 verifier 重评分，并在 CSV 标注来源。reward=1 是通过，reward=0 是测试实际未通过。表中分别报告通过/已评分，以及通过/89 的当前累计比例；后者仅是进度快照，不是尚未完成评测的最终准确率。任务容器采用保留模式，因此 Docker 中容器仍在运行不能直接等同于任务仍在推理。')
add()
add('## 3. 本轮 OAS 成绩')
add()
add('| 模型 | 条件 | 有效评分/184 | 实得分/已评分满分 | 得分率 | 无有效成绩 | 状态 |')
add('|---|---|---:|---:|---:|---:|---|')
for x in oas:
    add(f"| {x['model']} | {x['condition']} | {x['valid']}/184 | {fmt(x['points'])}/{fmt(x['total']) if x['total'] else '—'} | {pct(x['points'],x['total'])} | {x['unresolved']} | {x['status']} |")
add()
add('配置说明：旧 GLM baseline 为 30 步、Qwen2.5-7B NPC；新 DeepSeek/Qwen baseline 与本轮 skills 为 100 步、DeepSeek 官方 API 的 deepseek-flash NPC。国内主模型使用硅基流动 API；gpt-oss-120B 使用本机 GPU，100 步、同一官方 DeepSeek NPC。评分入口兼容修复保持原检查含义，缺失评分的 38 题没有另造裁判分数。旧 GLM baseline 不能作为当前 skills 的严格对照。')
add()
add('各组尚无有效成绩题目的最近已落盘尝试原因如下。这些记录包含历史尝试；正在补测或排队的题目尚未返回新结果时，仍显示旧原因，不代表本轮新增异常或最终失败。未启动的组单列为暂无输出：')
add()
for x in oas:
    add(f"- **{x['model']} / {x['condition']}**："+'；'.join(f'{k} {v} 题' for k,v in x['reasons'].items())+'。')
add()
add('详细证据：'+link(OUT/'oas-per-task.csv','逐题本次选用成绩')+'、'+link(OUT/'oas-all-attempts.csv','所有阶段的逐题尝试')+'、'+link(OUT/'oas-stages.csv','阶段汇总')+'。后两份包含重试，不能直接相加作为唯一题数。')
add()
add('## 4. GPT / Gemini / Claude / gpt-oss：Terminal-Bench 2.1 成绩')
add()
add('2026-09-13 评分有效性修正：此前仅依据数字 reward 判断有效，会误收录依赖下载失败导致的 0 分。现已重新校验本轮逐题测试报告。Claude fix-git 保留产物仅重跑原评分器，2 项测试全部通过，修正为 1 分；未调用模型 API。历史批次附录仍保留原口径，尚未按此规则全面审计。')
add()
add('| 模型 | 已返回/89 | 有效评分 | 通过题数 | 通过/已评分 | 当前通过/89 | 异常 | 未返回 | 队列状态 |')
add('|---|---:|---:|---:|---:|---:|---:|---:|---|')
for x in terminal:
    add(f"| {x['model']} | {x['returned']}/89 | {x['scored']} | {x['passed']} | {pct(x['passed'],x['scored'])} | {pct(x['passed'],89)} | {x['errors']} | {x['pending']} | {x['status']} |")
add()
add('GPT/Gemini/Claude 三个 API 模型各 89 题，共 267 道模型任务；gpt-oss 另有 89 道，使用本机 GPU、32,768 token 上下文。每模型先跑 openssl-selfsigned-cert 与 fix-git 两道真实验证题，验证成绩计入 89 题，GPT/Gemini 首轮剩余 87 题以 4 并发继续，当前补跑和 Claude 使用 2 并发。数据集固定为 Terminal-Bench 2.1，commit `7131e4375048a0e408a8fb404b5f499d726b695b`。使用 65,536 token 上下文、既有 Terminal 适配器的 1,000 次任务工具尝试上限，实际还受每题官方超时限制；并非 OAS 的 100 步配置。')
add()
add('GPT 通过 APINebula Responses API；Gemini 与 Claude 通过本地 Responses→Chat 桥接调用 APINebula。采用完整 skills/hooks，个人 Codex 登录不复用。两模型的协议与推理配置不完全相同，不能当成完全一致的推理强度测试。')
add()
add('Claude 启动计划：'+link(CLAUDE_JOB/'plan.json')+'；请求用量记录：'+link(CLAUDE_JOB/'logs/claude/bridge-requests.jsonl')+'。')
add()
add('GPT 启动检查曾因 openssl-selfsigned-cert 没有成功执行工具而暂停。审计确认该题实际由安全 hooks 拦截，正常完成并获得官方 0 分；另一题 fix-git 有真实工具执行且得 1 分。随后修正的是启动接入判断，原 hooks、原 0 分和两道题的结果均保留，没有重跑挑分。')
add()
add('当前逐题结果：')
add()
add('| 模型 | 任务 | 结果 | 运行/终止信息 |')
add('|---|---|---|---|')
for x in term_tasks:
    result=f"{fmt(x['points'])}/1" if x['status']=='valid' else '无有效评分'
    info=x.get('reason') or x.get('termination_reason') or '正常取得评分'
    add(f"| {x['model']} | {x['task'].removeprefix('terminal-bench/')} | {result} | {info} |")
add()
add('证据：'+link(OUT/'terminal-api-per-task.csv','Terminal API 逐题 CSV')+'；运行计划 '+link(TJ/'plan.json')+'；GPT 启动审计 '+link(TJ/'preflight/gpt-smoke-reviewed.json')+'。')
add()
add('## 5. Terminal-Bench 2.1 公开参考分数')
add()
add('### 5.1 Google 模型卡对照表')
add()
add(f'下表来自 [Google Gemini 3.8 Flash 模型卡]({google})，发布于 2026-09-02；[方法说明]({method})表示 Terminal-Bench 2.1 采用 Terminus 2，Gemini 为自测，其他模型引用公开榜单与 Artificial Analysis。它不是我们运行器下实测的 baseline。')
add()
add('| 模型 | 公开得分 |')
add('|---|---:|')
for x in public[:6]:add(f"| {x['model']} | {x['score_percent']:.1f}% |")
add()
add('gpt-oss-120B 的公开 Terminal-Bench 2.1 参考分数为 **26%**，来源：[Together 模型页](https://www.together.ai/models/gpt-oss-120b)。该页未完整说明 Agent 等条件，不能视为本运行器的配对 baseline。此项沿用本会话已查证来源。')
add()
add('### 5.2 官方 2.1 榜单的模型与 Agent 配置')
add()
add(f'来自本会话检索到的 [Terminal-Bench 2.1 官方榜单]({leader})快照：22 条配置记录，以下每个模型只列该快照中分数最高的一条，共 13 个模型。官网动态页面、搜索快照与发布时模型卡可能不同步；此处保留来源与口径，不把两表合成一个排名。')
add()
add('| 模型 | Agent | 推理强度 | 得分 |')
add('|---|---|---|---:|')
for x in public[6:]:add(f"| {x['model']} | {x['agent']} | {x['effort']} | {x['score_percent']:.1f}% |")
add()
add('本次公开分数检索于 2026-09-13 会话中完成。官方榜单提供重复运行 k=5 的命令，而我们首次每模型各题跑一次，后续仅补异常，保留首个有效成绩。模型卡、榜单与本地评测的任务版本、Agent、推理强度、上下文、API 路由、重试策略及安全策略可能不同；现阶段只能做参考，不能把分数差直接解释为 skills 的因果提升。')
add()
add('公开成绩明细与逐行来源：'+link(OUT/'public-terminal21-scores.csv')+'。')
add()
add('## 6. 既有 Terminal 历史结果附录')
add()
add('这里盘点 `skills/results/terminal-bench/` 下可读取的历史逐题结果，包含旧版本、验证题、修复批次、oracle 和模型运行。它们不是本轮两个国外 API 模型的成绩。每个批次/模型/条件单独统计，不合并重复题。下面的“已返回”以逐题 result.json 为准；历史汇总里的 running/pending 可能陈旧，因此不将其写作当前仍在运行。')
add()
add('### 6.1 既有 2.1 全量模型批次')
add()
add('| 批次 | 模型 | 已返回 | 有效评分 | 通过 | 通过/已评分 | 异常 |')
add('|---|---|---:|---:|---:|---:|---:|')
for x in history:
    if x['batch'].startswith('rick-saber-tb21-full-'):
        add(f"| {link(x['source'],x['batch'])} | {x['model']} | {x['returned']} | {x['scored']} | {x['passed']} | {pct(x['passed'],x['scored'])} | {x['errors']} |")
add()
add('这些全量批次每模型计划 89 题。GLM 历史模型是 GLM-4.7-Flash，不是当前 API 的 GLM-5.1；gpt-oss 也不是 GPT-5.6 Sol。Mistral 若只有部分结果，不能视为完整 89 题成绩。')
add()
add('### 6.2 全部历史批次/条件目录清单')
add()
add('| 批次 | 模型 / 条件 | 已返回 | 有效评分 | 通过 | 异常 |')
add('|---|---|---:|---:|---:|---:|')
for x in history:
    add(f"| {link(x['source'],x['batch'])} | {x['model']} / {x['condition']} | {x['returned']} | {x['scored']} | {x['passed']} | {x['errors']} |")
for x in regrade_inventory:add(f"| {link(x['source'],x['batch'])} | {x['note']} | — | — | — | — |")
add()
add('全部历史结果的数值、数据集路径与逐题来源：'+link(OUT/'terminal-history.csv','历史汇总 CSV')+'、'+link(OUT/'terminal-history-per-task.csv','历史逐题 CSV')+'。修复/验证/oracle 的分数不能作为模型正式分数引用；MiniMax 等历史记录保留不代表本轮启用这些模型。')
add()
add('## 7. 已知问题与后续统计约束')
add()
add('- OAS：38 道不可评分题继续排除；步数上限、对话卡住、TPM、超时或评分入口异常保持原始记录，不自动变为 0 分。')
add('- OAS：GLM/DeepSeek 已结束的批次仍留有异常题；Qwen skills 可能继续受 TPM/超时影响，以实时队列为准。Qwen baseline 已恢复但首次启动检查失败，补跑将保留 baseline 隔离验证。')
add('- Terminal：任务失败并不必然是基础设施故障；例如安全 hooks 拦截导致官方 0 分，是应保留的模型/运行器结果。缺 Stop 等必需 hooks 记录的运行异常则不计为已有效评分。')
add('- 所有正在运行的成绩是快照，不是最终成绩。报告记录时刻不同于此前聊天表格，出现新增题目或分数变化属于正常进度。')
add('- 没有完整平台账单，不能把历史费用预算当成实扣金额；未在本报告写入任何 API Key、密钥环境内容或聊天原文。')
add()
add('## 8. 可追溯文件')
add()
for name,label in [('snapshot.json','本次汇总机器可读快照'),('input-sha256.json','输入结果与状态文件哈希'),('oas-per-task.csv','OAS 逐题选用结果（含排除项和无输出项）'),('oas-all-attempts.csv','OAS 全部阶段尝试'),('oas-stages.csv','OAS 阶段汇总'),('terminal-api-per-task.csv','当前 Terminal API 逐题结果'),('terminal-verifier-pending.csv','评分执行异常的待核查/重评分清单'),('terminal-history.csv','历史 Terminal 汇总'),('terminal-history-per-task.csv','历史 Terminal 逐题结果'),('public-terminal21-scores.csv','公开分数及来源')]:
    add('- '+link(OUT/name,label))
add()
add('本地成绩按原始输出重新计算，原始结果未修改。哈希用于固定此次读取的文件版本；活跃任务文件之后继续追加时，其哈希会发生变化。')
# Preserve existing SABER versions whenever the combined report is regenerated.
sys.path.insert(0, str(OUT))
from build_saber_section import export_section
saber_section, saber_data = export_section()
L.extend(['', saber_section])
snapshot['saber'] = saber_data
(OUT/'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n')
(OUT/'评测结果汇总.md').write_text('\n'.join(L)+'\n')

assert all(x['valid']+x['unresolved']==184 for x in oas)
assert all(x['scored']+x['errors']==x['returned'] and x['returned']+x['pending']==89 for x in terminal)
assert len(public)==19
for name in ['评测结果汇总.md','snapshot.json','oas-per-task.csv','terminal-api-per-task.csv']:
    assert (OUT/name).stat().st_size>0
print(json.dumps({'report':str(OUT/'评测结果汇总.md'),'snapshot_utc':END,'oas':oas,'terminal':terminal,'history_groups':len(history),'history_trials':len(history_trials),'oas_attempts':len(attempt_rows),'source_files':len(inputs)},ensure_ascii=False,indent=2))
