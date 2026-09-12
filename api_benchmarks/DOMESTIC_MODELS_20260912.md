# 原国内测试模型的 API 可用性

检查日期：2026-09-12。依据工作区历史实验记录与硅基流动实时 `/v1/models`，本次只查询模型目录及官方文档，没有发起模型推理或 benchmark。

## 原实验范围

[v10 模型配置](../workspace-snapshot/skills/jobs/saber_v10_model_specs.py)沿用 v9 的五模型，其中国内模型为 GLM-4.7-Flash、MiniMax-M2.5、DeepSeek-V4-Flash-0731；Mistral、gpt-oss 属于国外模型。较早的[实验进度](../workspace-snapshot/skills/SABER_EXPERIMENT_PROGRESS.md)还记录了 Qwen3.8-27B-FP8 的 716 题 baseline。

## 查询结果

现有硅基流动 Key 查询 `https://api.siliconflow.cn/v1/models` 返回 HTTP 200，共 94 个 ID；原始响应保存在 [siliconflow-models.json](../reports/api_benchmarks/domestic-model-availability-20260912/siliconflow-models.json)。

| 原模型 | 硅基流动当前目录 | 其他官方 API / 版本限制 |
| --- | --- | --- |
| GLM-4.7-Flash | 未列出 | 智谱官方支持 `glm-4.7-flash`，需要智谱 Key |
| MiniMax-M2.5 | 未列出；公告确定于 2026-09-11 下线 | MiniMax 官方仍列出 `MiniMax-M2.5`，需要其官方 Key |
| DeepSeek-V4-Flash-0731 | 有 `deepseek-ai/DeepSeek-V4-Flash` | 目录未提供 `0731` 固定版本 ID，不能证明与原 checkpoint 完全相同 |
| Qwen3.8-27B-FP8 | 有 `Qwen/Qwen3.8-27B` | 目录没有标明 FP8，不能证明与原量化部署相同 |

此外，原项目中出现过的 DeepSeek-V4-Pro 当前有 `deepseek-ai/DeepSeek-V4-Pro`；Qwen3.5-27B/9B/4B 也列在目录中。下载过权重或存在作业配置不等于已经完成实验，不能将它们混入上面的已测模型范围。

## 对现有流程的影响

坚持所有国内模型使用硅基流动，当前只能覆盖上表中 Qwen 和 DeepSeek 的对应模型系列，不能完整复现原模型名单。GLM-5.1 等新型号不是 GLM-4.7-Flash 的同模型替代品。

目录存在只证明服务公开列出，未证明具体账户的推理请求或工具调用成功。OAS 使用 Chat Completions；当前 SABER / Terminal-Bench 2.1 的 Codex 路径要求流式 Responses。此前硅基流动 Responses 探测返回 404，本次未重测，后续仍需验证/实现协议适配及多轮工具往返。

## 官方依据

- [智谱 GLM-4.7-Flash：模型与调用示例](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash)：`https://open.bigmodel.cn/api/paas/v4/chat/completions`。
- [MiniMax 官方模型列表](https://platform.minimaxi.com/docs/api-reference/models/openai/list-models)：`https://api.minimaxi.com/v1/models`，列出 `MiniMax-M2.5`。
- [硅基流动下线公告](https://docs.siliconflow.cn/docs/release-notes/overview)：2026-09-03 公告，MiniMax-M2.5 普通/Pro 服务于 2026-09-11 下线。

本次没有修改当前运行配置，也未将现有两个供应商的 Key 发送给智谱或 MiniMax。
