# 本地验证记录

验证日期：2026-09-11。工作区：`/Users/rick/Desktop/skills/skill`。

**后续更新：** 9 月 12 日用户将 Key 改为 CODEX 分组后，国外 Responses 已恢复；SABER 单任务 A/B 与评分已完成。本文保留初始诊断历史，当前状态以 [最新测试记录](RUN_20260912.md) 为准。

## 已完成

- 已安装项目内 uv、Python 3.12，以及独立的 SABER、Harbor 和 OAS Python 环境；`setup.sh deps` 最终退出码为 0。
- `bench.py plan all` 可生成三个 benchmark 的 baseline/treatment 命令，不展示密钥。
- `bench.py doctor` 确认三个 runner 的 Python imports、Docker daemon、Codex CLI 和 bundle 可用。
- API 工作流 11 项、Harbor 适配器 2 项离线回归通过，包含密钥别名、轮换及各 harness 的凭证传递检查。
- OAS SDK 版本/快照兼容回归：10 passed。
- SABER `preflight` 在 `none`、`safety-orchestrator` 两组均通过；没有开始模型 turn。
- Harbor 0.22.0 已实例化自定义适配器，生成的命令参数通过 CLI 解析。
- 使用本地 `saber-codex-runner:0.149.1` 镜像，在 `--network none` 的一次性容器中验证了 skills/hooks 安装、Python 编译、hooks JSON 和 Codex hook-trust 参数。
- 主项目 95 atoms、Router catalog、14 references、vendored docs 的四项校验及 hook Python 编译通过。
- 新增 API 代码的 Ruff 检查、Python 编译、Bash 语法检查通过；OAS 修改按其 pre-commit 流程检查。
- OAS pre-commit 的格式、lint、PEP8 检查通过。扁平 Git 根目录使其中的 Pyright 未自动读取 OAS 配置；改为在 `openagentsafety/` 显式运行 `pyright --project pyrightconfig.json` 检查全部三个修改文件，结果为 0 errors、0 warnings。

## 供应商 API 实测

2026-09-11 已将用户提供的两个 Key 写入忽略的 `api_benchmarks/.env`，权限为 `0600`。国内角色引用 `SILICONFLOW_API_KEY`，国外 Responses 角色引用 `APINEBULA_API_KEY`；计划、报告及示例不包含 Key。

最终检查：30,769 个 Git 已跟踪或未忽略的候选文件及三个 benchmark 的计划输出均不含这两个 Key。`doctor` 的导入和四组配置字段检查通过；沙箱内 Docker socket 检查受限，单独获准只读检查后确认 daemon 版本为 29.2.1。

| 检查 | 结果 |
| --- | --- |
| 硅基流动模型列表 | HTTP 200 |
| Qwen3-Coder-30B 文本 | 返回 `API_OK` |
| Qwen3-Coder-30B 工具往返 | 正确调用 `lookup_probe(code="ABC")`，收到模拟工具结果后正确返回数值 `7319` |
| DeepSeek-V3.2 裁判模型文本 | 返回 `API_OK`；本次探测关闭 thinking，未运行语义评分 |
| Qwen2.5-7B NPC 文本 | 返回 `API_OK`；未进入 OAS NPC 场景 |
| OAS 原生 SDK + 生成的配置 | 返回 `SDK_API_OK`，零重试，输出上限 128 tokens |
| 硅基流动 Responses | HTTP 404；当前接口不适用于 Codex harness |
| API Nebula 模型列表 | HTTP 200，仅返回两个图片模型 |
| API Nebula `gpt-5.4` Responses | HTTP 503，`get_channel_failed`；文本通道尚未验证 |

六次成功 completion 的供应商 usage 合计 **470 tokens**，包含工具往返的两次请求。不据此推算完整 benchmark 费用；OAS SDK 尚无该模型的内置价格映射，自动 cost 统计不能作为账单依据。

脱敏原始证据保存在忽略目录 `reports/api_benchmarks/provider-check-20260911/`：`initial-api-probes.json`、`siliconflow-functional-probes.json`、`oas-sdk-probe.json`、`apinebula-responses-probe.json`。初期网络探测曾遇连接错误和缺少 `socksio`；SABER/Harbor 环境补齐依赖并更新锁文件后重试，以上表格以最终结果为准。

API Nebula 官方 [快速开始](https://docs.apinebula.ai/docs/quickstart/) 与 [Codex 配置](https://docs.apinebula.ai/docs/cli/codex/) 指向 `https://apinebula.ai/v1` 和 Codex 分组。需核对该 Key 的分组、可用文本模型及通道；503 本身不足以断言 Key 无效。只向经核实的 `.ai` 域名使用此 Key。

### 国外模型复测（北京时间 23:42–23:43）

再次查询 `/v1/models` 成功，仍仅列出 `gpt-image-2` 和 `gpt-image-2.5`。随后进行四次独立短请求，每次输出上限 128 tokens、无自动重试：

| 模型 | 接口 | 结果 |
| --- | --- | --- |
| `gpt-5.4` | `/v1/responses`，流式 | 503 / `get_channel_failed` |
| `gpt-6-astra`（供应商当前 Codex 示例） | `/v1/responses`，流式 | 503 / `get_channel_failed` |
| `gpt-5.6-sol`（供应商 FAQ 示例） | `/v1/responses`，流式 | 503 / `get_channel_failed` |
| `gpt-5.4` | `/v1/chat/completions` | 503 / `get_channel_failed` |

没有返回模型内容或 usage，不能形成国外模型测试成绩。复测证据和供应商 request ID 保存在 `reports/api_benchmarks/provider-check-20260911/apinebula-models-recheck.json`、`apinebula-text-recheck.json`。

供应商 [令牌分组说明](https://docs.apinebula.ai/docs/model-groups/token-groups/) 说明分组决定 Key 能使用的模型、协议和客户端；`CODEX` 是 GPT/Codex 对应分组，图片、Claude、Gemini 有各自分组。因此“国外模型 Key”不一定能调用全部国外模型。

供应商 [503 说明](https://docs.apinebula.ai/docs/faq/codex/) 将此错误解释为模型没有可用通道。当前证据无法区分令牌分组不匹配和该分组服务端通道不可用，也不能仅凭此错误要求换 Key。下一步在 [令牌管理](https://apinebula.ai/zh/console/token) 查看当前 Key 的分组及模型限制：若不是 `CODEX`，选择支持目标 GPT 模型的分组；若已是 `CODEX`，核对模型广场后向供应商排查通道，并提供复测时间和 request ID。这里只记录排查建议，未修改控制台、未向客服发送消息。

## 尚未执行 / 当前阻塞

- 尚未产生 benchmark 分数；API smoke 不等于 skills/hooks 生效验证或 A/B 实验完成。
- SABER、Terminal-Bench 的真实任务等待可用的 API Nebula Responses 文本通道。修复分组或服务端通道后运行 `python3 api_benchmarks/bench.py probe --role responses`；仅更换 Key 时才需更新本地 `APINEBULA_API_KEY`。
- 未下载模型权重、未启动模型推理服务。
- OAS 专用服务栈、fixture 数据及 agent-server/skills 镜像尚未准备并完成检查。现有其他应用的 Docker 容器未改动。
- 未执行真实 Terminal-Bench 任务或验证全部任务镜像；Harbor 会在真实运行时准备环境。

真实运行前按 README 准备 OAS 环境、排除 Responses 通道阻塞，再各跑一条任务的 A/B smoke。安装成功和配置检查通过不能替代真实模型轨迹及 hook 审计验证。
