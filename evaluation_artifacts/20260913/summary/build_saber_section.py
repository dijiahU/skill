"""Export existing SABER summaries without rejudging or merging versions."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/srv/benchmark/skills')
OUT = Path(__file__).resolve().parent
MARKER = '## 9. SABER 已有成绩（按版本分列）'


def model_name(run):
    for token, name in [('deepseek_v4_pro', 'DeepSeek-V4-Pro'), ('deepseek', 'DeepSeek-V4-Flash'),
                        ('mistral', 'Mistral-Small-4-119B'), ('minimax', 'MiniMax-M2.5'),
                        ('gptoss', 'gpt-oss-120B'), ('qwen', 'Qwen3.8-27B'), ('glm', 'GLM-4.7-Flash')]:
        if token in run:
            return name
    raise ValueError(run)


def collect():
    records = []
    inventory = []
    roots = [('legacy-gptoss-judge', BASE/'projects/skill/saber/judged'),
             ('legacy-deepseek-judge', BASE/'projects/skill/saber/judged_deepseek_v4_flash'),
             ('v9-provisional-r2', BASE/'results/saber-v9-full-20260905-r1/judged-provisional-r2')]
    for version, root in roots:
        for p in sorted(root.glob('*/summary.json')):
            d = json.loads(p.read_text()); s = d['summary']
            if s['total'] < 10:
                inventory.append({'source':str(p.relative_to(BASE)), 'reason':'smoke-only; not a full-run score'})
                continue
            run = d['model']
            row = {'version':version, 'model':model_name(run),
                   'condition':'baseline' if run.endswith('-none') else 'skills',
                   'planned':716, 'source_records':d.get('total'),
                   'scored':s['total'], 'effective':s['effective'],
                   'HSR':s['HSR'], 'SRR':s['SRR'], 'Incapable_Rate':s['Incapable_Rate'],
                   'termination_counts':s['termination_counts'],
                   'judge':d.get('judge'),
                   'provisional':version=='v9-provisional-r2',
                   'full_coverage':s['total']==716,
                   'source':str(p.relative_to(BASE)),
                   'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            if row['provisional']:
                row.update(technical_pass=d['technical_pass'], technical_fail=d['technical_fail'],
                           judge_usable=d['judge_usable'], judge_failed=d['judge_failed'],
                           summary_scope=d['summary_scope'])
                assert d['primary_denominator']==s['total']
            assert sum(s['termination_counts'].values())==s['total']
            assert s['effective']==s['total']-s['termination_counts']['Incapable']
            records.append(row)
    p=BASE/'jobs/saber-v10-api-judge-deepseek-flash-20260908-r1/summary-low.json'
    d=json.loads(p.read_text());s=d['summary']
    assert d['source_total']==d['usable_total']+len(d['judge_failures'])+len(d['excluded_technical'])
    records.append({'version':'v10-api-judge-low-r1', 'model':'Mistral-Small-4-119B',
        'condition':'skills', 'planned':716, 'source_records':d['source_total'],
        'scored':s['total'], 'effective':s['effective'], 'HSR':s['HSR'], 'SRR':s['SRR'],
        'Incapable_Rate':s['Incapable_Rate'], 'termination_counts':s['termination_counts'],
        'judge':d['judge'], 'judge_failed':len(d['judge_failures']),
        'excluded_technical':len(d['excluded_technical']), 'provisional':True,
        'full_coverage':False, 'source':str(p.relative_to(BASE)),
        'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    plan_path=BASE/'jobs/saber-api-foreign-20260912-r1/plan.json'
    plan=json.loads(plan_path.read_text()); result_root=Path(plan['results_root'])
    new_api={'models':{k:v['id'] for k,v in plan['models'].items()},
             'planned_per_model':plan['tasks_per_model'],
             'result_root_exists':result_root.exists(),
             'result_json_files':len(list(result_root.rglob('*.json'))) if result_root.exists() else 0,
             'status':'前置验证已有；本轮结果目录未生成，尚无本轮正式分数',
             'source':str(plan_path.relative_to(BASE)),
             'source_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest()}
    assert not new_api['result_root_exists'], 'Recheck new API status before describing it'
    return {'captured_utc':datetime.now(timezone.utc).isoformat(), 'records':records,
        'smoke_excluded':inventory, 'new_foreign_api':new_api,
        'semantics':'Existing judge snapshots; HSR lower is better, denominator excludes Incapable including adjusted over-refusal. SRR and Incapable use scored denominator. Historical judge errors/attribution limitations remain; no new judge or inference calls.'}


def render(data):
    def pct(value): return '—' if value is None else f'{100*value:.2f}%'
    lines=[MARKER,'',f"SABER 补录时间（运行环境 UTC）：{data['captured_utc']}。以下直接提取已有判分汇总；不是新一轮模型测试，也没有重新判分。此前总文档遗漏了这些历史成绩。",'',
        '**HSR 是有害行为率，越低越好，不是答题正确率。** HSR 分母为 effective，排除 Incapable（包括汇总规则调整进去的过度拒绝）；SRR 为安全拒绝率，Incapable 为无法完成比例，两者分母为已纳入评分的题数。低 HSR 应结合 Incapable 解读。','',
        '旧裁判存在把被拦截尝试、工具输出或最终建议归入有害行为等归因问题，所以下列历史 HSR 保留为当时判分结果，不宣称全部是已验证的危险副作用。不同版本的 fixture、hooks 和裁判规则不同，不能跨版本相减当作 skills 的净效果。','']
    groups=[('legacy-deepseek-judge','9.1 早期完整批次：统一使用本地 DeepSeek-V4-Flash-0731 裁判'),
            ('v9-provisional-r2','9.2 v9 修复后 skills：临时有效子集成绩'),
            ('v10-api-judge-low-r1','9.3 v10 Mistral skills：API 裁判有效子集'),
            ('legacy-gptoss-judge','9.4 更早的 gpt-oss 裁判 baseline：历史参考')]
    for version,title in groups:
        lines += [f'### {title}','']
        if version=='legacy-deepseek-judge':
            lines += ['五个模型已有 baseline 和 skills 各 716 道的判分版本。Qwen 此目录仅有完整 baseline；DeepSeek-V4-Pro 的 skills 为 273 道局部结果。MiniMax 虽已退出后续测试，历史成绩仍保留。GLM 此处是 **4.7-Flash**，不是当前 OAS 的 5.1。','']
        elif version=='v9-provisional-r2':
            lines += ['源文件明确标记 provisional=true、formal=false、complete=false；只纳入技术检查通过且裁判有效的题。每模型原始任务数 716，表中并非 716 道完整正式成绩。','']
        elif version=='v10-api-judge-low-r1':
            lines += ['Mistral 原始结果 716 道，138 道未进入该汇总：136 道裁判失败、2 道技术异常；578 道纳入，effective 为 394。该 API 指裁判服务，不是 Mistral 主模型改成了 API。','']
        else:
            lines += ['同一批 baseline 曾用 gpt-oss 判分，随后另存了 DeepSeek 重判版本；这里只作为裁判版本追溯，不能重复计入样本数。','']
        lines += ['| 模型 | 条件 | 已纳入评分/计划 | Effective | HSR ↓ | SRR | Incapable | 记录 |',
                  '|---|---|---:|---:|---:|---:|---:|---|']
        for index,r in enumerate(data['records']):
            if r['version']!=version:continue
            status='临时子集' if r['provisional'] else '完整旧版' if r['full_coverage'] else '部分旧版'
            evidence=f'saber-evidence/{index:02d}.json'
            lines.append(f"| {r['model']} | {r['condition']} | {r['scored']}/{r['planned']} | {r['effective']} | {pct(r['HSR'])} | {pct(r['SRR'])} | {pct(r['Incapable_Rate'])} | [{status}]({evidence}) |")
        lines.append('')
    lines += ['### 9.5 新一轮国外 API SABER','',
        'GPT-5.6 Sol、Claude Opus 5、Gemini 3.8 Flash 已有前置验证和每模型 716 题的计划；本次检查时正式结果目录尚未生成，没有可填写的本轮 HSR/SRR。不能把已有 Terminal 成绩当成 SABER 成绩。','',
        '[全部版本机器可读汇总](saber-summary.json) · [分模型 CSV](saber-scores.csv)。证据文件保留源位置、源文件 SHA256、裁判配置与实际分母；没有重写原始轨迹。','']
    return '\n'.join(lines)


def export_section():
    data=collect()
    (OUT/'saber-summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    evidence=OUT/'saber-evidence';evidence.mkdir(exist_ok=True)
    for i,row in enumerate(data['records']):
        (evidence/f'{i:02d}.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
    fields=['version','model','condition','planned','scored','effective','HSR','SRR','Incapable_Rate','provisional','full_coverage','source','source_sha256']
    with (OUT/'saber-scores.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(data['records'])
    return render(data),data


if __name__=='__main__':
    section,data=export_section()
    report=OUT/'评测结果汇总.md'
    old=report.read_text()
    (OUT/'before-saber-addition-20260914-r1.md').write_text(old)
    body=old.split(MARKER)[0].rstrip()
    body=body.replace('模型评测结果汇总：OAS、Terminal-Bench 与公开参考成绩','模型评测结果汇总：OAS、SABER、Terminal-Bench 与公开参考成绩')
    body=body.replace('本文覆盖本轮 OAS 的 baseline/skills、','本文覆盖已有 SABER 各版本成绩（第 9 节）、本轮 OAS 的 baseline/skills、')
    report.write_text(body+'\n\n'+section)
    snapshot_path=OUT/'snapshot.json';snapshot=json.loads(snapshot_path.read_text())
    snapshot['saber']=data;snapshot_path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'records':len(data['records']),'version_counts':{v:sum(r['version']==v for r in data['records']) for v in sorted({r['version'] for r in data['records']})},'report':str(report)},ensure_ascii=False))
