# 三个 Benchmark 的 API 测试流程

这套入口使用当前 `skill/` 工作区的 SABER、OpenAgentSafety 和 Safety Orchestrator；不启动 vLLM、不下载权重、不要求 GPU。Docker 负责运行任务环境，模型推理由远程 API 提供。

## 接口与实验条件

| Benchmark | Agent/harness | 模型接口 | 评分 |
| --- | --- | --- | --- |
| SABER | 现有 Codex-native + SABER TaskRuntime | **流式 Responses，支持工具调用** | 现有规则 + 独立 judge API |
| OAS | 本地 OpenHands SDK，保留现有 hook 修复 | Chat Completions 或 Anthropic Messages | 环境内 evaluator；NPC 另用 Chat Completions |
| Terminal-Bench 2.1 | Harbor 0.22.0 + `SafetyCodex`，Codex 0.149.1 | **流式 Responses，支持工具调用** | Harbor 任务 verifier，无额外 LLM judge |

默认 `--mode both --limit 1`：每个 benchmark 的 `none` 与 `safety-orchestrator` 各跑一个任务，顺序执行。SABER treatment 只预加载 Router 与健康状态；模型按 Router 路由调用 `saber_skill_read` 读取所需的 archetype reference，14 个文档正文不会全量注入。Hooks 由适配层执行。OAS 的 skills 条件显式要求先 `invoke_skill("safety-router-skill")`，并启用 SDK hooks；Terminal-Bench 在独立任务容器安装 Router 与 Codex hooks。是否实际读取 reference 以轨迹为准。不同 benchmark 的 harness 不相同，比较各自内部的 A/B 差异。

仅支持 Chat Completions 的供应商不能直接驱动这两条 Codex 流程。Terminal-Bench 可设置 `TERMINALBENCH_CHAT_BRIDGE=1`，由本地转换层接入；此时 `RESPONSES_*` 填上游 Chat Completions 模型、URL 和 Key 别名。SABER 仍需直接支持 Responses 的远程 API。`BENCH_*`、`RESPONSES_*`、`JUDGE_*`、`NPC_*` 可以独立选择供应商，不会自动复用另一角色的密钥。

## 1. 本地配置

所有命令从 `skill/` 目录运行：

```bash
python3 api_benchmarks/bench.py init
# 编辑 api_benchmarks/.env，填写四组模型、Base URL 和 API Key
python3 api_benchmarks/bench.py plan all
```

`init` 保留已有 `.env`。密钥只填本地文件，或通过同名环境变量传入；环境变量优先。配置文件不会执行 shell 语法。模型 ID 填供应商实际 ID，OAS 的 `BENCH_PROVIDER` 再添加 `openai/` 或 `anthropic/` 路由前缀。Base URL 不要包含 `/responses`、`/chat/completions` 等操作路径。

### 已验证的供应商组合（2026-09-12）

| 角色 | 供应商 / 模型 | 实测状态 |
| --- | --- | --- |
| OAS agent | 硅基流动 / `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 已完成单题 A/B、Router 调用、hooks 和原生评分 |
| SABER judge | 硅基流动 / `deepseek-ai/DeepSeek-V3.2` | 已完成 SABER 单任务两组评分 |
| OAS NPC | 硅基流动 / `Qwen/Qwen2.5-7B-Instruct` | 文本调用通过 |
| SABER、Terminal-Bench agent | API Nebula / `gpt-5.6-sol` | 两项单题 A/B 链路完成；TB 2.1 基线 5/6、skills 6/6 项测试通过 |

国内接口使用 `https://api.siliconflow.cn/v1`，国外接口使用 `https://apinebula.ai/v1`。本地 `.env` 每个供应商只保存一份 Key：`SILICONFLOW_API_KEY`、`APINEBULA_API_KEY`。四个角色通过 `BENCH_API_KEY_ENV`、`JUDGE_API_KEY_ENV`、`NPC_API_KEY_ENV`、`RESPONSES_API_KEY_ENV` 指向相应变量名；设置别名后，直接角色 Key 不再生效。更换 Key 时修改供应商变量即可，无须同步多份副本。

API Nebula 的 Key 改为 **CODEX 分组**后已列出 GPT 模型，`gpt-5.6-terra`、`gpt-5.6-sol`、`gpt-6-astra` 文本调用均通过。Terra 的一次工具请求超时，故当前选择完成工具往返验证的 Sol；原来的 `gpt-5.4` 不在当前模型列表中。分组决定 Key 的模型和协议范围，详见供应商 [令牌分组说明](https://docs.apinebula.ai/docs/model-groups/token-groups/)。硅基流动实测 `/responses` 返回 404，不能直接替代此角色。最新结果见 [9 月 12 日测试记录](RUN_20260912.md)，初始安装及历史失败见 [验证记录](VALIDATION.md)。

当前本地配置已切换为 GLM-5.1，`BENCH_RUN_ID=glm51-tb21-four-20260912`，Terminal-Bench 转换层开启、并发 4、每题一次。详见 [GLM Terminal-Bench 2.1 实验](GLM_TERMINAL_20260912.md)。旧的 GPT/Qwen 流程详见 [剩余两项测试记录](REMAINING_20260912.md)。SABER 按需读取结果保存在 `nebula-sol-ondemand-20260912`（当时步数上限为 6）。旧的 `nebula-sol-smoke-20260912` 误用了 14 文档全量预加载，仅作为链路调试记录，不能用来评价按需路由。正式实验请使用新 run ID 并设置合适的步数。SABER judge 入口自动适配上游自行附加 `/v1` 的行为；`.env` 中仍填写标准 `/v1` Base URL。

最新 [按需读取验证](ON_DEMAND_20260912.md) 已观察到模型实际读取 5 份文档，未全量注入；尚不能据此认定所有阶段均遵循 Router。

追加的 [GLM-5.1 / MiniMax 测试](GLM_MINIMAX_20260912.md)：GLM 已通过文本、工具往返和 OAS 单题 A/B；MiniMax 已按用户要求移出当前测试计划，历史失败记录保留。[GLM Terminal-Bench 2.1 四题对照](GLM_TERMINAL_20260912.md) 已结束：基线 3/4 通过，skills 2/4 通过；skills 的 Git 题执行超时且原生评分为 0，因此该组不属于无异常完成。使用本地 Responses → Chat Completions 转换层、原生 Codex 与远程硅基流动 API；SABER 尚未运行 GLM。

## 2. 安装测试依赖、准备环境

```bash
bash api_benchmarks/setup.sh deps
python3 api_benchmarks/bench.py doctor
bash api_benchmarks/setup.sh saber-image
python3 api_benchmarks/bench.py preflight saber
bash api_benchmarks/setup.sh oas-images
```

`setup.sh` 使用系统 `uv` 或 `api_benchmarks/.venv-tools/bin/uv`，并管理隔离的 Python 3.12 环境。OAS 依赖来自仓库 `uv.lock` 与已包含的 SDK 源码；无须重新拉取 submodule。SABER 在宿主机使用 PATH 中的 Codex；实际版本应随实验记录，Terminal-Bench 容器版本单独固定。

本次同时修复了扁平化备份缺少 SDK submodule 元数据时的启动问题：版本标识使用 `snapshot-<源码摘要>`，不会冒充上游 commit；SDK Dockerfile 按源码位置查找。正常 submodule checkout 保留原有 commit 标识。

OAS 中声明共享服务依赖的题目还需要独立的 TheAgentCompany 服务栈及 fixture 数据，具体见 [OAS 环境说明](../openagentsafety/benchmarks/openagentsafety/README.md)。本次 smoke 选择 `safety-unsafe-feedback-form`，其 `dependencies=[]`、无 NPC，使用任务容器和原生 evaluator 即可。其他题目的 AIStation 服务复位及 ownCloud/GitLab 健康检查仍保留，不能把任意同名业务容器当作测试服务。`doctor` 不等于服务栈已就绪。

OAS 的基础服务和任务镜像占用较大，不由 `deps` 自动下载。`oas-images` 构建 agent-server 与带 SDK hook 修复的派生镜像，默认标签为 `api-openagentsafety`。Docker Desktop 的容器访问宿主机使用 `host.docker.internal`；Linux 上改成容器可达的地址。Terminal-Bench 的任务镜像由 Harbor 在运行时准备。

OAS 的依赖 wheel 在官方 Linux/amd64 基础镜像中构建，缓存以 SDK 源码与 `uv.lock` 摘要校验，避免 macOS 二进制依赖混入容器。需要代理时，在本地 `.env` 设置 `OAS_BUILD_HTTP_PROXY` 为容器可访问的地址。

Terminal-Bench 明确使用 **2.1**：`TERMINALBENCH_DATASET=terminal-bench/terminal-bench-2-1`，subset 中使用带命名空间的任务 ID，例如 `terminal-bench/cancel-async-tasks`。Harbor 的 `lock.json` 保存实际任务包版本。此前 Docker Hub TLS 超时的尝试没有模型结果；当前已通过宿主机下载并导入相同官方任务镜像。

本机可运行 `bash api_benchmarks/setup.sh terminalbench-cli` 下载官方 npm Linux x64 原生 Codex 0.149.1 包并校验 SHA-512，再把输出的 `TERMINALBENCH_CODEX_ARCHIVE` 路径填入 `.env`。适配器在两组中安装同一完整原生包、核验运行版本，避免 npm 的系统依赖安装超时；任务镜像及 verifier 不变。若容器需要代理，可配置 `TERMINALBENCH_HTTP_PROXY`，两组的 agent 和 verifier 均使用同一设置。

## 3. API 连通性与小样本 A/B

以下 probe 会产生少量 API 用量，只打印检查状态：

```bash
python3 api_benchmarks/bench.py probe --role responses
python3 api_benchmarks/bench.py probe --role agent
python3 api_benchmarks/bench.py probe --role judge
python3 api_benchmarks/bench.py probe --role npc

python3 api_benchmarks/bench.py run saber --limit 1
python3 api_benchmarks/bench.py run oas --limit 1
python3 api_benchmarks/bench.py run terminalbench --limit 1
```

`probe --role responses` 检查上游原生 Responses 端点；GLM 转换模式应使用上面的 Terminal-Bench 单题运行验证端到端链路，直接探测硅基流动 Responses 仍返回 404。

Responses probe 检查流式完成及工具 schema 接受情况；多步工具调用、实际 hook 生效仍需以单任务 smoke 的轨迹与审计日志为准。尚未填写密钥或占位模型时，`run` 会在调用模型前退出。

`--mode none` / `--mode safety-orchestrator` 可单独跑一组。SABER 的 `BENCH_MAX_STEPS` 和 OAS 的 max iterations 默认 30；Terminal-Bench 使用数据集原生超时上限，不能把任务数限制理解成 token/费用硬上限。

## 4. 评分与结果

```bash
python3 api_benchmarks/bench.py judge saber
python3 api_benchmarks/bench.py judge oas --output /absolute/path/to/output.jsonl
python3 api_benchmarks/bench.py judge terminalbench
```

- SABER 原始轨迹沿用 `saber/results/<BENCH_RUN_ID>_codex-native-<mode>/`；评分写到 `reports/api_benchmarks/<BENCH_RUN_ID>/saber/judged/`。现有 `saber/config.json` 会优先于 judge 环境变量，入口遇到它会停止评分，避免误用旧模型配置。
- OAS 结果在 `reports/api_benchmarks/<BENCH_RUN_ID>/oas/<mode>/` 下的模型子目录；`output.jsonl` 含环境评分，eval 命令做汇总。
- Terminal-Bench 在 `reports/api_benchmarks/<BENCH_RUN_ID>/terminalbench/<mode>/` 保存 Harbor job/trial 结果、Codex sessions、`safety-condition.json` 和 treatment 的 `safety-audit/`。

成功率与安全性要分别看；SABER 的 `Incapable`、over-refusal 不能算安全提升，OAS API/环境错误不能当模型拒绝。Terminal-Bench 用来衡量引入 skills 后的任务完成率变化。

入口会检查 OAS / Harbor 的结果文件，遇到缺少评分、对话异常或仅部分轨迹评分时返回失败；有效的零分仍是完成的任务结果。

## 5. 扩大实验与复现

设置新的 `BENCH_RUN_ID`，然后显式增加 `--limit`。每个 benchmark 可用 `--select` 固定任务：SABER 接受 JSON ID 数组（例如 `["A_fs_001"]`），OAS/Terminal-Bench 接受每行一个 task ID 的文本。不能把同一 subset 文件传给三个 benchmark。

入口记录脱敏配置、任务选择摘要和 bundle hash；同一 run ID 的配置变化会被拒绝，避免旧结果混入新实验。SABER/OAS 保留上游续跑行为；Terminal-Bench 每次创建新的 Harbor job，重复运行会重新计费。正式比较前固定任务列表、供应商模型版本与相同 A/B 参数，保留 manifest 和原始结果。

离线回归：

```bash
python3 -m unittest api_benchmarks.test_bench -v
api_benchmarks/.venv-harbor/bin/python -m unittest api_benchmarks.test_harbor_codex -v
```

上游依据：[SABER](https://github.com/sssr-lab/saber)、[OAS 推荐的 OpenHands 实现](https://github.com/OpenHands/benchmarks/tree/main/benchmarks/openagentsafety)、[Terminal-Bench / Harbor](https://www.harborframework.com/docs/tutorials/running-terminal-bench)。本地改动和未跑通的环境条件应随结果披露。
