# V9 先 Judge、后单独补跑

用户于 2026-09-06 明确要求：不等待技术失败补跑，先提交 Judge，评分完成后再单独补跑。此流程不修改当前 treatment 或原始结果，不将技术失败伪装为检查通过。

## 已提交状态

- 2026-09-06 00:59:13（北京时间）启动独立等待进程，PID **2117115**。
- 00:59:45 核实 PPID 1、SID/PGID 2117115，状态 `waiting_for_treatment`。
- 当前只提交调度，还没有开始模型评分，也没有预占 GPU。
- 主控制器仍为 2072663，GLM/gpt-oss 并行辅助仍为 2097821，均未中断。
- 00:59:45 DeepSeek Flash treatment 已写 65/716 条，近 5 分钟新增 12 条。

入口源码：`skills/jobs/run_saber_v9_judge_first.py`、`skills/jobs/saber_v9_judge_first_entry.py`。

冻结快照：`skills/jobs/saber-v9-full-20260905-r1/judge-first-r1/`。评分入口 SHA256：`86a73d4e933e52d09a0f0d2b0c2818e5d87a1d2146002f1e858f0d9fbea1b61d`。仅做源码静态复核和 AST 检查，没有额外测试或模型试跑。

## 自动启动条件

等待原 R2 控制器完成所有 treatment 模型、退出，并等待并行辅助退出。原主队列的 `treatment_failed` 是保留技术失败的真实状态，不必改成 passed；当它同时记录 `treatment_queue_finished=true` 时，新流程可以继续。

随后确认：六模型各 716 个可解析、路径和身份一致的原始文件；已有任务清理记录安全；旧任务进程和本批次容器均已退出；原 frozen、依赖和 raw 内容未被改写。技术失败数量不再阻止本次补跑前评分。缺文件、身份冲突、未完成队列或不安全清理仍会阻止评分，明确写状态，不擅自接管未知服务。

Judge 使用本地 DeepSeek Flash，经 `gpu-idle run --gpus 0,1` 包裹完整服务与评分生命周期。8 个评分 worker，沿用原成功判定、提示词和采样配置，最多 3 轮 Judge 请求重试。只清理本评分任务自行捕获的进程；Docker 仅做只读检查，不创建或删除任何容器、镜像。

## 查看状态与结果

- 调度状态：`skills/logs/saber-v9-full-20260905-r1/judge-first-r1/status.json`。
- 调度日志：同目录 `events.jsonl`、`launcher.log`。
- 实际开始标记：同目录 `execution-started.json`；标记不存在时不能声称 Judge 已开始。
- 分模型技术审计：同目录 `technical-audit/<model>.json`。
- 补跑清单和检查汇总：同目录 `pre-judge-report.json` 的 `pending_reruns`。
- 独立评分结果：`skills/results/saber-v9-full-20260905-r1/judged-provisional-r1/`。
- 总汇总：该结果目录下 `_all_summary.json`，每模型也有独立 `summary.json`。

所有评分记录标记 `provisional=true`、`formal=false`，保留 raw SHA256 和技术检查状态。主要汇总只使用技术通过且 Judge 有效的条目，并明确分母；`diagnostics_all_records` 另列包含技术无效条目的诊断口径，不能当作正式全量分数。原始 error 沿用旧 Judge 的 Incapable 归类，但明确不代表安全通过。无效 Judge 响应会重试，不默认认定安全；每次响应和尝试另存私有 `_attempts/`。

六模型都会尝试评分；仍有 Judge 失败时保留失败和汇总、返回非零。全部评分完成也仅表示补跑前版本已完成，技术失败仍需后续另建补跑版本。此脚本不会自动改 fixture 或启动补跑，不覆盖任何旧 raw/正式 judged 数据。DeepSeek Pro 不参与。

旧只读巡检可能仍因主队列 `treatment_failed` 报需要关注；判断新评分是否运行，应同时查看这里的独立状态，不能把旧主状态直接当作 Judge 故障。不要重复提交同一冻结入口；需要恢复时先核对 PID、结果与来源版本。
