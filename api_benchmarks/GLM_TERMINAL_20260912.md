# GLM-5.1 / Terminal-Bench 2.1

## 最终结果

四题批次 `glm51-tb21-four-20260912` 已结束，共八次运行。基线 **3/4 通过**；skills **2/4 通过**，其中 Git 题同时记录 `AgentTimeoutError`（900 秒）和原生 verifier 得分 0。入口因此返回非零状态，没有把该组标为无异常完成。

| 任务 | 基线：通过测试数 / 原生 reward | skills：通过测试数 / 原生 reward |
| --- | --- | --- |
| cancel-async-tasks | 6/6；1 | 6/6；1 |
| log-summary-date-ranges | 2/2；1 | 1/2；0 |
| openssl-selfsigned-cert | 6/6；1 | 6/6；1 |
| git-multibranch | 0/1；0 | 0/1；0，执行超时 |

日志题的 skills 输出将最近 30 天 ERROR 总数算成 9949，原生测试要求 9594。Git 基线的 dev 部署仍返回初始化内容；skills 运行反复触发账户创建审批与 `PasswordAuthentication yes` 安全控制规则。这四题单次测试未显示 utility 提升，不能据此确定总体或稳定的因果效果。

四个 skills 任务都实际读取 Router。证书题读取了三份 archetype 文档，其他读取和审计计数见 [机器可读汇总](../reports/api_benchmarks/glm51-tb21-four-20260912/summary.json)。`block` 日志表示规则判定，不等于已验证宿主成功阻止了所有影响；证书题在读取参考文档附近也出现一次注入检测 block，值得单独检查。

本机实测配置为 24 GB 物理内存、10 核 CPU；Docker 分配约 8 GB 内存。本批并发上限为 4，采样时容器内存约 90–130 MB，并非峰值数据。类似轻量题下一批可试 8 并发；原生每题 2 GB 内存上限仍保留，较重任务不能按上述采样值估算。增加并发不会加速单个任务的策略重试或 900 秒超时。

## 当前实验

MiniMax 已移出当前测试计划。GLM 使用硅基流动 `Pro/zai-org/GLM-5.1` API，不部署模型。Terminal-Bench 版本固定为 **2.1**，原生 Harbor 0.22.0、Codex 0.149.1、任务镜像和 verifier 保持一致。

硅基流动没有 Responses 端点，因此在宿主机增加受临时令牌保护的协议转换进程：Codex Responses → LiteLLM 1.100.1 → 硅基流动 Chat Completions。模型及供应商 URL 固定；真实供应商 Key 仅用于宿主机上游请求，容器只获得临时令牌。转换日志仅记录请求数量、工具类型、耗时、token 用量和状态，不记录提示词及密钥。进程随 benchmark 自动关闭。

本轮两组统一设置 `enable_thinking=false`，每次模型响应最多 8192 输出 token。保留任务原生超时；这是明确限定配置下的对照，不代表 GLM 所有推理配置的能力。

## 任务与并发

选择四道任务，每组各一次，共八次：`cancel-async-tasks`、`log-summary-date-ranges`、`openssl-selfsigned-cert`、`git-multibranch`。这是便于本地运行的小样本，不是完整数据集的随机抽样。

每组最多四个任务并发，两组顺序运行。Docker 当前约 8 GB 内存，各题原生内存上限 2 GB，保留原始资源配置。基线不安装 skills/hooks；treatment 安装同一 Router，要求先读取 `SKILL.md`，其余 archetype 文档按需读取。

## 复现

从仓库根目录执行，Key 保留在忽略的 `api_benchmarks/.env`：

```bash
BENCH_RUN_ID=glm51-tb21-new-run \
RESPONSES_MODEL=Pro/zai-org/GLM-5.1 \
RESPONSES_BASE_URL=https://api.siliconflow.cn/v1 \
RESPONSES_API_KEY_ENV=SILICONFLOW_API_KEY \
TERMINALBENCH_CHAT_BRIDGE=1 TERMINALBENCH_CONCURRENCY=4 \
python3 api_benchmarks/bench.py run terminalbench --limit 4 \
  --select api_benchmarks/subsets/terminalbench21-glm-four.txt
```

运行前已验证真实流式工具调用及工具结果回传。完整 Codex 单题预检保存在 `reports/api_benchmarks/glm51-tb21-codex-preflight-20260912/`，不计入四题批次。离线配置、适配器及转换层共 24 项检查通过。最终评分与实际 Router/hooks 行为以批次结果和轨迹为准。
