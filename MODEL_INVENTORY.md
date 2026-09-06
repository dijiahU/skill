# 本地模型清单（2026-09-01 快照）

> 位置：`/2024233123/skills/models/modelscope/` · 硬件：2×NVIDIA H20-3e（各 ~140G，共 ~280G）
> 全部 10 个模型均无 `.incomplete` 文件（下载完整）。

## 1. 计划内 Open-weight Main（6 个）——全部就位

| # | 模型 | 大小 | 量化 | 架构 | 部署（2×H20） | 实验状态 |
| --- | --- | ---: | --- | --- | --- | --- |
| 1 | Qwen3.8-27B-FP8 | 29G | FP8 | Qwen3_5 | ✅ 单卡 | ✅ SABER baseline 716 判分完成（HSR 0.3231） |
| 2 | GLM-4.7-Flash | 59G | BF16 | Glm4MoeLite (30B-A3B) | ✅ 单卡 | 🔄 treatment 716/716 原始结果完成，待判分 |
| 3 | gpt-oss-120b | 61G | mxfp4 | GptOss | ✅ 单卡 | ✅ baseline 716 + 四模型 judge 均完成 |
| 4 | DeepSeek-V4-Flash-0731 | 156G | FP8 | DeepseekV4 | ⚠️ 需两卡 TP2 | ❌ vLLM 0.17 未注册架构（需 vllm018-overlay） |
| 5 | Mistral-Small-4-119B-2603 | 113G | FP8 | Mistral3 | ⚠️ 两卡更稳 | ❌ vLLM 缺 Mistral 4 FP8 backend |
| 6 | MiniMax-M2.5 | 215G | FP8 | MiniMaxM2 | ⚠️ 两卡 TP2（0.90 利用率） | ✅ baseline 716 判分完成（HSR 0.5182） |

## 2. 计划内 Scaling 系列（4 个）——全部就位

| 模型 | 大小 | 部署 | 状态 |
| --- | ---: | --- | --- |
| Qwen3.5-27B | 52G | ✅ 单卡/双卡 | ✅ baseline 完成 |
| Qwen3.5-9B | 19G | ✅ 单卡 | 待 scaling |
| Qwen3.5-4B | 8.8G | ✅ 单卡 | 待 scaling |
| Qwen3.5-2B | 4.3G | ✅ 单卡 | smoke 已跑，待 scaling |

## 3. 计划内 Frontier API（3 个）——不占本地显存，需确认 key/预算

GPT-5.6 Sol（OpenAI）· Claude Fable 5（Anthropic）· Gemini 3.7 Flash（Google）

## 4. 2026-09 查漏清单（7 家族完整调研，2026-09-01）

### ✅ 280GB 内可部署的新增候选（按推荐度排序）

| 模型 | 参数 | 部署 | 备注 |
| --- | --- | --- | --- |
| Qwen3.8-Flash / Flash-Next | 125B / 6B active | ✅ 单卡 ~125G 即可 | 首选：全新架构、Agent 定位、SGLang Day-0 + vLLM 配方成熟，训练成本降 90% |
| Qwen3.6-35B-A3B | 35B / 3B active, 256K ctx | ✅ 单卡 ~35G | Terminal-Bench 51.5，agent 强，vLLM 支持 tool_calling |
| Qwen3.7-35B | 35B（结构待确认） | ✅ 单卡 | Ollama 已有开源权重（3.7-Plus 是闭源 API） |
| Qwen3.6-27B | 27B Dense 原生视觉-语言 | ✅ 单卡 ~27G | Agentic coding 增强 |
| Qwen3.6-Flash（≈ Qwen3-Next-80B-A3B） | ~80B / A3B | ✅ 两卡/单卡边缘 | 命名对应关系待确认 |
| GLM-4.7（旗舰） | ~185B（A19B? 待官方确认） | ⚠️ 双卡 ~185G | Flash 之外 GLM-4.7 还有旗舰级，可双卡 |
| Mistral Magistral-Small-2506 | 24B Dense | ✅ 单卡 | Mistral 首个透明 CoT 推理系列，vLLM 教程齐全 |
| Gemma 4 | 26B-A4B | ✅ 单卡 | Apache 2.0 首次允许商用，端侧定位，agent 能力待实测 |
| OLMo 3 | 32B / 7B | ✅ 单卡 | 学术小模型补充 |
| Llama 4 Scout | 109B / 17B active | ✅ 两卡 ~109G | Meta 家族唯一可部署候选 |

### ❌ 排除（FP8 远超 280G，只能 API 或激进量化）

Qwen3.8-Max（2.4T）· GLM-5（381B）· GLM-5.2（~381B）· GLM-5.3-Flash（320B）· GLM-5.3 旗舰（743B）· DeepSeek-V4 / V4-Pro（1.6T）· MiniMax-M3（427B，仅 VQ-2.4bit 可试）· Kimi K2.5（1T）· Kimi K3（2.8T）

### ❌ 未找到/未发布

Qwen3.6 的 2B/4B/9B 档 · InternLM 2026 新 Agent 模型 · Llama 5（仅传闻）· OpenAI gpt-oss 之后的新开源 · MiniMax M3 之后的新旗舰

### ⚠️ 待核实（影响选型）

DeepSeek-V4-Flash 官方总参数（本地已有 0731 版，13B 激活报道）· GLM-4.7 旗舰 / GLM-5.2 官方参数 · Qwen3.6-Flash 命名对应

> 注：280G 总量下，凡 FP8 权重估算 >280G 的一律排除（1T/1.6T/2.4T/400B 均不可本地部署）；>280G 但 ≤400G 的 MoE 可看 NVFP4 量化是否压低到两卡内（如 GLM-5.3-Flash）。
