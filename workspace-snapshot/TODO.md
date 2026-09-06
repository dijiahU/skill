# SABER 后续工作计划

> 创建时间：2026-09-01（北京时间）

## 1. 完成 GLM Safety Plane Treatment

- 等待 `codex_glm47_flash_treatment_716_codex-native-safety-orchestrator` 达到 716/716。
- 确认 8 个 worker 正常退出、GLM 服务释放 GPU，并记录总耗时。
- 审计所有原始结果，分类统计上下文溢出、sandbox 初始化失败和模型/API 错误。
- 不把运行故障计作安全失败；只重跑无效任务，使 baseline 与 treatment 的有效 task ID 对齐。
- 验证 `preload_skill_references=false`，确保 14 份 archetype 文档仍按需读取。

## 2. 部署 DeepSeek-V4-Flash

- 复用已下载权重：`skills/models/modelscope/deepseek-ai/DeepSeek-V4-Flash-0731`，不重新下载或删除模型文件。
- 核对 `config.json` 中的 architecture、量化格式、显存需求和 tokenizer 配置。
- 当前 vLLM 0.17 未注册 `DeepseekV4ForCausalLM`；在独立环境中测试兼容 vLLM 或最小适配，不破坏现有 GLM/Qwen 环境。
- 依次验证：模型加载、OpenAI API、流式输出、Responses 兼容、推理内容和工具调用解析。
- 从单请求 smoke 开始，再根据显存占用决定单卡或双卡部署。

## 3. 校准 DeepSeek Judge

- 先复判固定随机种子 `20260901` 抽出的 10 条 gpt-oss 样本。
- 重点检查 `B_access_015`、`C_access_013`、`C_net_005`、`B_code_038`。
- 对照 ground truth、原始轨迹、最终回答和 state delta，记录与人工判断的一致性。
- 再抽取按 A/B/C 和 Safe/Harmful/Incapable 分层的扩展样本。
- 重点检查危险建议漏判、虚构工具步骤、过度拒绝和完成状态误判；校准通过前不跑全量 judge。

## 4. 使用同一 Judge 重判 GLM A/B

- DeepSeek judge 校准通过后，同时重判 GLM baseline 和 GLM treatment。
- 不将 DeepSeek 判的 treatment 与 gpt-oss 判的 baseline 直接比较。
- 每条结果单独保存，支持断点续跑和失败重试。
- 汇总 HSR、HSR-A/B/C、HSR-Local/Propagating、SRR、LRR、CPR、Incapable Rate 和 termination counts。
- 生成 task-level paired 转移表，分析 Harmful→Safe、Safe→Refusal、Completed→Incapable、hook 阻断和误拒绝。

## 5. 后续决策

- 根据 GLM A/B 结果决定是否修正 hook 过度阻断和 `saber_skill_read` 工具误路由。
- DeepSeek-V4-Flash 与 Mistral-Small-4 的推理后端跑通后，再补齐各自 baseline。
- 暂不启动 scaling，也不启动耗时较长的 Qwen treatment。
- 每个阶段完成后更新 `skills/SABER_EXPERIMENT_PROGRESS.md`。
