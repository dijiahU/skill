# 重启后的补跑恢复

2026-09-13 用户授权恢复。原补跑在 Pod 于 14:50 重启时中断；此次只接续没有返回结果的 375 个模型任务，已经返回的 42 个结果（包括有效 0 分和异常）全部保留。

- OAS skills：GLM 4、DeepSeek 2、Qwen 82、gpt-oss 6 题。
- OAS baseline：DeepSeek 13、Qwen 184 题，分别排在同模型 skills 后；Qwen 仍先验证两题隔离。
- Terminal skills：GPT 15、Gemini 51、gpt-oss 18 题。
- 沿用原并发、模型、100 步 OAS 配置、Terminal 官方超时及修复后的完整 skills/hooks；共享上批冻结代码。
- 动态获取当前 Pod 地址；本机接口与宿主 Docker 直连，外部 API 使用既有代理。
- GPU 0 跑 gpt-oss OAS、GPU 1 跑 gpt-oss Terminal，均通过 gpu-idle 预约完整生命周期。
- 仅清理上批 OAS 对应阶段中同时符合原前缀和会话标签的已授权容器；Terminal 保留容器。
- 原始输出、旧控制状态和有效成绩不覆盖。恢复阶段另用 supplement-r2 / resume2 名称。

逐题清单见 plan.json；选择依据见 preflight/resume-selection.json；运行状态见 progress.py。
