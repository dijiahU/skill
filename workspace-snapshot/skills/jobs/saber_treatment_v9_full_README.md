# V9 全模型 treatment 与自动 Judge

批次：`v9-full-20260905-r1`。不覆盖任何旧 treatment、baseline 或 judged。

## 模型与顺序

1. Mistral Small 4：GPU 0,1，TP2。
2. MiniMax M2.5：GPU 0,1，TP2。
3. DeepSeek V4 Flash：GPU 0,1，DP2 + EP。
4. Qwen3.8-27B-FP8：GPU 0,1，两个 TP1 副本。
5. GLM-4.7-Flash：GPU 1。
6. gpt-oss-120b：GPU 0。
7. DeepSeek V4 Pro：现有远程 API 配置，不预约本地 GPU。

每模型 716 任务、8 workers，总计 5,012 条。沿用历史任务分区与模型设置。
所有本地模型和后续 Judge 均通过 `gpu-idle run`，包装完整服务、消费者及收尾周期。
准入等待上限 86,400 秒；不会终止其他正式服务来获取 GPU。

## 自动衔接

每模型先 preflight 和单题 smoke，再运行该模型全量。全部模型进程退出后，
逐条核对任务 ID/路径/原始要求、结果结构、错误、预算、hook 和工作区观测。
只有七模型均成功退出、全部 5,012 条技术验收通过且冻结指纹一致，
才重新预约双卡，启动本地 DeepSeek V4 Flash，对本批次全部结果判分。
Judge 沿用既有 8 workers、最多 3 次失败重试的逻辑，不读取旧批次结果。

空执行轨迹、框架强制停止、Stop 输出替换是警告，保留给 Judge 判断；
不把技术通过当作模型安全成功，也不按业务完成与否筛选样本。
出现技术错误或异常退出则保留所有现有结果、写入失败状态，不自动推进 Judge。
这是本地后台任务联动，不依赖聊天保持在线；没有配置聊天推送通知。

## 文件位置

- 冻结清单：`skills/jobs/saber-v9-full-20260905-r1/frozen/manifest.json`
- 原始结果：`skills/results/saber-v9-full-20260905-r1/raw/`
- Judge 结果：`skills/results/saber-v9-full-20260905-r1/judged/`
- 总状态：`skills/logs/saber-v9-full-20260905-r1/status.json`
- 阶段事件：同目录 `events.jsonl`
- 模型日志及验收：同目录各模型子目录
- 批次验收：同目录 `treatment-batch-validation.json`
- 异常退出审计：同目录 `exit-audit.json`（仅异常时生成）

## 启动

准备命令已经为此批次执行，不要再次执行 `--prepare`；已有目录会被拒绝覆盖。
在用户明确批准本批次新建容器的清理范围之后执行：

```bash
source /2024233123/skills/aistation_env.sh
PYTHONDONTWRITEBYTECODE=1 python3 /2024233123/skills/jobs/run_saber_treatment_v9_full_batch.py \
  --run-batch --cleanup-approved
```

该命令是长驻前景流水线，应由终端会话或进程管理器持续持有；不要只预约一个
启动后立即退出的后台 launcher。每个模型内部独立申请其实际所需显卡。

无人值守运行时，可将整条长驻流水线放入独立会话；内部每个模型仍由
`gpu-idle run` 前景管理完整生命周期。本批次已于北京时间 2026-09-05 15:38:55
提交，父进程 PID 为 `2012296`。以下启动命令仅供记录，**当前不要重复执行**：

```bash
source /2024233123/skills/aistation_env.sh
PYTHONDONTWRITEBYTECODE=1 nohup setsid /usr/bin/python3 \
  /2024233123/skills/jobs/run_saber_treatment_v9_full_batch.py \
  --run-batch --cleanup-approved \
  >> /2024233123/skills/logs/saber-v9-full-20260905-r1/launcher.log 2>&1 </dev/null &
batch_launcher_pid=$!
sleep 3
ps -p "$batch_launcher_pid" -o pid,ppid,pgid,sid,stat,etime,args
```

查看状态（只读，可重复执行）：

```bash
cat /2024233123/skills/logs/saber-v9-full-20260905-r1/status.json
tail -n 30 /2024233123/skills/logs/saber-v9-full-20260905-r1/events.jsonl
```

已验证启动 shell 退出后，流水线仍以独立会话运行，父 PID 转为 1；
15:39:05 双卡预约准入并启动 Mistral 服务。脱离聊天/终端不等于持久调度服务：
Pod/节点重启、强制杀进程或基础设施故障不会自动恢复，需人工检查。
异常会阻止自动 Judge；不存在聊天推送承诺。

正式容器同时要求标签 `rick-saber.batch=v9-full-20260905-r1`、对应模型标签，
以及名称前缀 `rick-saber-v9-full-20260905-r1-<model>-`；清理前逐 ID 再次验证。
不借用 idle 会话权限，不 prune、不删除文件、镜像或卷。

## 离线测试

```bash
python3 -m unittest discover -s skills/jobs/tests -p 'test_saber_treatment_v9_*.py' -v
```

27 项纯 mock 测试通过；验收器另已只读复验 R5 的 12 条真实结果。
