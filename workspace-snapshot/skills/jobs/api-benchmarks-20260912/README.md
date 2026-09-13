# API 评测部署（2026-09-12）

代码：`/srv/benchmark/skills/projects/skill-api-20260912`，分支 `api-benchmarks-glm-20260912`，基准提交 `d764079d206e99f8272165648118129da640f2cd`，含本地 AIStation 适配改动。旧 checkout 和 GPU 作业没有切换。

## 环境变量与模型

运行 `source /srv/benchmark/skills/aistation_env.sh` 加载环境。密钥存在源码目录外的 `skills/secrets/api-benchmarks.env`，目录权限 700、文件权限 600，不包含在模型配置中。不要用 `set -x` 加载它。

| 分组 | 环境变量 | 当前选择 / 验证 |
| --- | --- | --- |
| 硅基流动 | `SILICONFLOW_API_KEY` | GLM `Pro/zai-org/GLM-5.1` 文本和转换层通过；DeepSeek `deepseek-ai/DeepSeek-V4-Flash` 文本通过；Qwen `Qwen/Qwen3.8-27B` 单次文本请求超时，待复测 |
| APINebula GPT | `APINEBULA_GPT_API_KEY`，兼容原 `APINEBULA_API_KEY` | `gpt-5.6-sol` 原生流式 Responses 探测通过；未擅自加入正式模型名单 |
| APINebula Gemini | `APINEBULA_GEMINI_API_KEY` | 用户指定 `gemini-3.8-flash`，文本和转换层通过 |
| APINebula Claude | `APINEBULA_CLAUDE_API_KEY` | 当前用户选择 `claude-opus-5`；Chat Completions、Anthropic Messages、流式转换层及两轮工具往返均通过 |

MiniMax 已从新计划排除；未删除历史文件或模型权重。GPT-OSS 待用户指定渠道；Mistral 不在目前三个 APINebula Key 可见目录中。API 模型不能视为原本地 checkpoint/量化版本的完全复现。

## 使用

```bash
/srv/benchmark/skills/bin/api-bench glm5 doctor
/srv/benchmark/skills/bin/api-bench glm5 plan all --limit 1
/srv/benchmark/skills/bin/api-bench gemini plan all --limit 1
```

支持 profile：`glm5`、`deepseek-flash`、`qwen`、`gemini`、`claude`；具体配置在本目录的同名 `.env`，只引用 Key 环境变量。Claude 当前配置为已验证的 Opus 5；下方 Fable 5 的错误记录属于此前选择。正式运行前使用新 `BENCH_RUN_ID` 并固定模型、任务列表和 A/B 参数。

SABER/Terminal-Bench 的国内模型和 Gemini 使用本地 Responses→Chat Completions 转换层，模型推理仍在远端。SABER 控制进程用回环地址，Terminal-Bench 用 Pod 地址；Docker 容器到 Pod 的实际连通性仍待单题端到端验证。OAS 直接使用 Chat Completions。入口不启动本地模型服务器，不需要 GPU。

## 并发结论

- Pod 可见 224 个 CPU，cgroup `cpu.max=5400000 100000`，有效 CPU 配额 **54 核**。
- cgroup 内存上限显示 `max`，这是共享节点视图，不能把整台机器约 1.5 TiB 内存视作独占额度。节点已有大量运行中的容器和其他负载。
- GLM-5.1 短请求（输入约 9 tokens、输出约 1 token）4 并发为 4/4 成功；8 并发为 7/8，一次 `ReadTimeout`，未观察到 HTTP 429。按预设遇错即停，没有继续测 16。
- 当前 OAS 和 Terminal-Bench 每次调用默认 **4 workers**；可用 `OAS_CONCURRENCY` / `TERMINALBENCH_CONCURRENCY` 调整。各调用之间没有全局总并发限制，多开进程会叠加。
- **SABER 当前 runner 仍逐题串行**。此次接通了 API 转换层，没有把串行 runner 宣称为并行实现。
- 尚未测出最大稳定 API 并发，也未测试全量 Docker 评测的容量。长上下文、多轮工具调用还受账号/模型 RPM、TPM 和网络延迟约束。

## 产物与验证边界

模型计划：`model-plan.json`。探测与容量证据：`/srv/benchmark/skills/reports/api-migration-20260912/`。正式结果写到 `/srv/benchmark/skills/results/api-benchmarks-20260912/`，SABER 原始结果及 judge 使用同一外部结果根目录；日志在 `skills/logs/api-benchmarks-20260912/`。

已执行少量文本/流式 API 探测，未启动完整 benchmark 容器、全量评测或付费持续压测。文本/流式探测不等于工具往返、评分、hooks 和容器生命周期的端到端通过。

供应商依据：[硅基流动限流说明](https://docs.siliconflow.cn/docs/userguide/rate-limits/rate-limit-and-upgradation)、[APINebula 分组的 Chat Completions 配置](https://docs.apinebula.ai/docs/advanced/hermes/)。当前 Claude Key 的实际 HTTP 400 与通用文档描述不一致，以上以本次响应为准。

最终环境：SABER、OAS、Harbor 均安装在 `skills/envs/api-{saber,oas,harbor}-20260912`；Harbor 全部依赖与分支 lock 一致（0 项差异）。已有的 `skills/envs/terminal-bench` 保留原状。

最终验证：独立 Harbor 环境下 26 项回归测试通过，`api-bench glm5 doctor` 全部基础检查通过，shell/Python 语法及 Git diff 空白检查通过。

Claude 分组更新后复测（2026-09-12 07:29 UTC）：模型列表 HTTP 200，但已经不含 `claude-fable-5`；Chat Completions 与标准 Anthropic Messages 均返回 HTTP 503 `get_channel_failed`。新分组列出 Haiku 4.5、Opus 4.5/4.6/4.7/4.8/5、Sonnet 4.5/4.6/5。此前的 HTTP 400 为旧分组结果；当前阻塞是选定 Fable 5 在新分组没有可用渠道。未擅自换成其他 Claude 型号。

Claude 最新选择与验证（2026-09-12 07:33 UTC）：已改用 `claude-opus-5`，新 run ID `api-claude-opus5-20260912-smoke`。Chat Completions 和标准 Anthropic Messages 均 HTTP 200。使用正式配置相同的独立 Harbor 环境启动本地流式转换层，第一轮成功返回指定工具调用，第二轮接收固定工具结果并准确返回 `7319`，两轮均 HTTP 200 且收到 `response.completed`。只执行无副作用的模拟工具，没有启动 Docker 评测或全量作业。证据：`claude-opus5-probes.json` 和 `claude-opus5-bridge-probe.json`。
