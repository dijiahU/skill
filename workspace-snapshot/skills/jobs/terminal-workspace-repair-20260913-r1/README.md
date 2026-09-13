# Terminal 大工作区与 verifier 修复

2026-09-13；独立冻结版本 `wsrepair1`。Claude 推理保持用户暂停状态。

## 已确认根因与修改

- `large-scale-text-editing` 的两份 CSV 合计 89,133,379 字节，单文件最大 51,066,691 字节；`path-tracing` 的文本 PPM 为 48,262,737 字节。此前 16 MB 单文件上限导致观察失败。
- `reshard-c4-data` 输入含 9,898 文件、817,461,269 字节，超过此前 8,192 文件/128 MB 总量上限。输入与新输出可能同时存在，因此新读取器和验证器同步采用 32,768 文件、64 MB 单文件、2 GB 文本总量、131,072 目录项上限。
- 观察器逐文件序列化内容，只保留路径索引，避免在官方 2 GB 任务容器内累计整份数据。输出仍是原完整 JSON schema；截断输出不能解析成完整快照。范围、软链接、文件变更、遗漏检查保留。
- 已知文件清单通过 Docker Compose stdin 传递，避免近万个路径触发 Linux 单参数长度限制；不经过任务可写临时文件。
- 安全 matcher 同一进程内共享一次快照解析，以文件设备、inode、长度、mtime、ctime 校验缓存；原子替换或内容变更会失效。不缓存失败后返回旧内容。
- matcher 超时/异常现在遵循 `SAFETY_ORCH_FAIL_CLOSED=1` 拒绝执行。原子安全规则和匹配判定未放宽，但错误处理条件与旧批次不同，需在比较中保留此差异。
- 单次观察传输超时从 30 秒增至 120 秒；每题官方 agent/verifier 总时限保持不变，观察与 hook 开销仍计入 agent 总时限。

旧批次冻结源码和原结果均保留；新源码位于 `frozen/`，哈希在 `submission-sha256.json`。本修复不向模型暴露额外工作区内容，不改变模型提示、上下文长度或工具尝试上限。

## 无模型调用验证

`validate_observer.py` 对三个保留工作区逐文件核对原文件 SHA-256，全部相符，无漏读：

| 工作区 | 完整读取时间 | 容器观察器峰值 RSS | 四个 hooks |
|---|---:|---:|---|
| CSV | 3.36 秒 | 260 MiB | 全部通过 |
| PPM | 6.97 秒 | 254 MiB | 全部通过 |
| C4 | 10.50 秒 | 28 MiB | 全部通过 |

`validate_hooks.py` 通过实际 `HarborRuntime` / `RetainedAdapter` 完成 UserPromptSubmit、PreToolUse、PostToolUse、Stop，真实工具仅执行只读 `stat`。C4 首次完整观察与发布约 27.2 秒，后续约 34.3 秒；前置 hook 约 13.1 秒、后置/Stop 约 6.3/6.4 秒。容量修复不消除大快照的时间成本。

证据在 `preflight/{csv,ppm,c4}-observer-evidence.json` 和 `preflight/{csv,ppm,c4}-hooks/evidence.json`。4 项回归测试覆盖缓存原子替换与无效内容、matcher 超时拒绝、软链接越界/截断、静默遗漏后旧快照失效；全部通过。冻结模块及控制器语法检查通过，源仓库四项 vocabulary/catalog/archetype/docs 一致性检查通过。

## 补跑

每个模型仅针对 CSV、PPM、C4 三题筛除已有有效结果后补测。GPT、gpt-oss 先各跑 1 题 smoke，再以 2 并发运行其余两题。smoke 必须取得有效官方评分，0 分也是有效成绩；若出现运行/评分基础设施异常，停止自动扩展并保留证据。不会为了提高分数重跑有效 0 分。

- GPT 控制器已启动。
- gpt-oss 通过 `gpu-idle run --gpus 1` 包裹模型服务和消费者全生命周期。
- Gemini 控制器先等待此前 `eval-retry-20260913-r2` 同模型锁释放，之后重新筛选题目，避免与现有批次重复。
- Claude 不恢复推理。

当前状态见 `state-terminal-*.json`、`lifecycle-terminal.json`；启动身份见 `launch.json`。原任务容器保留，不执行 Terminal 容器停止、删除或 prune。

## 仅重新评分的四题

`repair_verifiers.py` 不调用模型，不改原 `result.json` 或测试断言；输出由原 verifier 完整性检查器审核。

- GPT `crack-7z-hash`：代理修复后正式测试已运行，有效 0 分。
- Gemini `path-tracing-reverse`：代理修复后正式测试已运行，有效 0 分。
- GPT/Gemini `torch-pipeline-parallelism`：原失败为官方 900 秒内依赖尚未下载完成。准备 Python 3.13、pytest 8.4.1、torch 2.7.0、transformers 4.55.0、pytest-json-ctrf 0.3.5 的原包（包括原 CUDA 依赖），准备成功后自动执行原测试，测试仍限 900 秒。没有换成 CPU wheel 或放宽断言。

依赖准备单列、上限 3600 秒；准备失败不产生有效分数。准备日志和每题结束状态位于 `logs/*dependencies.log`、`preflight/*-verifier.json`，正式重评分保存在对应旧任务 `verifier/repair-*`，通过源结果哈希追溯。汇总采用第一个有效原结果或第一个有效 verifier 修复结果。
