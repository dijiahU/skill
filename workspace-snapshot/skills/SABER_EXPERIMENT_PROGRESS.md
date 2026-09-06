# SABER 实验进度

> 快照时间：2026-09-01 12:36 CST（北京时间）。本文记录当前实验状态；运行中的计数会继续增长。

## 实验目标与固定设置

- 在 SABER 716 个任务上比较 Codex native baseline（`skill-mode none`）与蒸馏 Safety Plane（`skill-mode safety-orchestrator`）。
- 每个任务使用独立 Codex Runner 和临时 SABER sandbox 容器，结果按任务持久化。
- treatment 仅预载 Safety Router 和健康状态；`preload_skill_references=false`，14 份 archetype 文档由模型通过 `saber_skill_read` 按需读取。
- 正式语义判分统一使用单卡 `OpenAI-Mirror/gpt-oss-120b`，上下文长度 131072。

## 已完成

### 框架与验证

- AIStation Docker TCP、Pod/Host 路径映射、Codex Runner、Responses 兼容代理和动态工具链已跑通。
- Safety Orchestrator 的 skill 安装、发现、健康检查，以及 `UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop` hooks 已通过真实 smoke 测试。
- 已恢复 Router-first 按需加载方式，不再把 14 份文档全部放入上下文。
- 四个 baseline 均已生成 716/716 条原始结果，并由同一 gpt-oss judge 完成判分。

| Baseline | Effective | HSR | HSR-A | HSR-B | HSR-C | SRR | Incapable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-4.7-Flash | 610 | 0.5705 | 0.5911 | 0.3822 | 0.6893 | 0.0084 | 14.80% |
| gpt-oss-120b | 354 | 0.5819 | 0.5796 | 0.4615 | 0.6887 | 0.0265 | 50.56% |
| MiniMax-M2.5 | 604 | 0.5182 | 0.4937 | 0.3812 | 0.6537 | 0.0349 | 15.64% |
| Qwen3.8-27B-FP8 | 523 | 0.3231 | 0.2488 | 0.2941 | 0.4379 | 0.0503 | 26.96% |

注意：HSR 以 effective 样本计算，不能脱离 Incapable 比例单独排序；例如 gpt-oss 的 HSR 最高，但一半以上任务被判为 Incapable。

### 模型权重

以下 ModelScope 目录均无 `.incomplete` 文件：

| 模型 | 本地大小 |
| --- | ---: |
| MiniMax-M2.5 | 215G |
| DeepSeek-V4-Flash-0731 | 156G |
| Mistral-Small-4-119B-2603 | 113G |
| gpt-oss-120b | 61G |
| GLM-4.7-Flash | 59G |
| Qwen3.5-27B / 9B / 4B / 2B | 52G / 19G / 8.8G / 4.3G |
| Qwen3.8-27B-FP8 | 29G |

## 进行中：GLM 带 Skill 全量

- 作业：`codex_glm47_flash_treatment_716_codex-native-safety-orchestrator`
- 启动：2026-09-01 11:56 CST，GPU 1，8 个 harness worker。
- 当前：353/716（49.3%）；GPU 0 已在四模型 judge 完成后释放。
- 中期行为：8,147 次 hook、63 个发生阻断的任务、180 个发生 warning 的任务、64 个使用 support tool 的任务。
- 按需读取：191 次有效 archetype 读取；0 个任务预载全部 references。
- 工具误路由：89 次将 benchmark 文件路径错误交给 `saber_skill_read`；读取被 skill-root 边界拒绝，未越权访问宿主文件，但会增加无效调用。
- 预计原始全量结果在 13:05–13:20 CST 完成。

当前 7 条错误必须在正式判分前处理：

- 3 条上下文错误：`A_access_014`、`B_code_006`、`B_code_047` 达到 32768 token 上限。
- 4 条 SABER sandbox 初始化错误：`B_data_008`、`B_data_017`、`B_data_025`、`B_info_012`。

这些是推理/基础设施故障，不能直接计为模型安全失败。最终完成后还需审计全部 716 条并重跑无效样本。

## 暂停或阻塞

- DeepSeek-V4-Flash：权重完整，但当前 vLLM 0.17 未注册 `DeepseekV4ForCausalLM`，尚无 716 条 baseline。
- Mistral-Small-4-119B：权重完整，但当前 vLLM 缺少可工作的 Mistral 4 FP8 backend，尚无 baseline。
- Scaling 实验按当前安排暂停。
- Qwen treatment 未启动；其双卡 baseline 已耗时约 9 小时，不适合作为本轮快速验证模型。

## 下一步

1. 等待 GLM treatment 生成 716 条原始结果。
2. 区分并重跑上下文溢出、sandbox 初始化和其他非模型错误，确保有效任务与 baseline 对齐。
3. 使用同一 gpt-oss-120b judge 对 treatment 判分。
4. 输出 paired A/B 对比：HSR、各场景 HSR、SRR、Incapable、termination 转移、hook 阻断与误拒绝案例。
5. 再决定是修正过度阻断/工具误路由，还是扩展到其他模型；在此之前不启动 scaling。

## 关键路径

- 原始结果：`projects/skill/saber/results/`
- 判分结果：`projects/skill/saber/judged/`
- GLM treatment 日志：`logs/saber-glm47-treatment-716/20260901-115433/`
- GLM treatment 作业：`jobs/run_saber_glm47_treatment_716.sh`
- GLM treatment 配置：`jobs/saber_glm47_treatment_716.json`
- 四模型 judge 日志：`logs/saber-gptoss120b-judge-4models/20260901-114221/`
