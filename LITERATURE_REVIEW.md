# 文献综述：确定性守卫 vs 语义守卫（2026）

> 生成时间：2026-09-01 · 用途：为 Safety Plane 论文的"enforcement placement"论证提供文献定位
> 范围：7 篇 2026 年相关文章（已逐篇精读），给出支持/挑战矩阵与论文措辞建议

---

## 1. 七篇文章一览

| # | 文章 | 类型 | 核心一句话 |
| --- | --- | --- | --- |
| 1 | [DROS: Four-Layer Deterministic Runtime Operation System](https://zenodo.org/records/21903475) | preprint（未评议） | 用四层（LLM 语义过滤 + PKI 身份 + ABAC + C-ABI 确定性强制）弥合"代理-执行归因鸿沟" |
| 2 | [Why Sandboxes Can't Secure AI Agents（Manifold）](https://www.manifold.security/blog/the-sandboxing-illusion-how-to-isolate-agents) | 厂商博客 | 沙箱为确定性软件设计，智能体会把约束当输入绕行；需要运行时行为监控 |
| 3 | [Deterministic Policy vs LLM-Based Filters（Data443）](https://data443.com/blog/deterministic-policy-vs-llm-filters/) | 厂商博客 | 确定性策略放在执行边界承重，LLM 只做下游 advisory |
| 4 | [Deterministic vs LLM-Judge Evals: Layer, Don't Choose（FutureAGI）](https://futureagi.com/blog/deterministic-vs-llm-judge-evals-2026/) | 技术博客 | 确定性地板(30-60%) → classifier → judge(5-10%) 三级级联，成本差约 30 倍 |
| 5 | [LLM Guardrails 2026: Failure Taxonomy（MorphLLM）](https://www.morphllm.com/llm-guardrails) | 厂商博客 | 六类守卫失败五类语义；"意图恒定，字符串不恒定"；难的守卫都是语义的 |
| 6 | [Classifier-based vs LLM-driven guardrails（F5）](https://www.f5.com/de_de/company/blog/classifier-based-vs-llm-driven-guardrails-what-actually-works-at-ai-runtime) | 厂商博客 | 分类器抓已知模式、LLM 推理意图；生产答案是混合纵深防御 + Day Two 演进 |
| 7 | [LLM 提示注入攻击深度解析（阿里云/Deephub）](https://developer.aliyun.com/article/1690311) | 技术博客 | 注入"从数学上防不住"；规则只能防后果，真正的承重是架构边界 |

---

## 2. 支持 / 挑战矩阵（相对"60 hook + 21 hybrid + 14 semantic"设计）

### 支持的论点（论文可引用的背书）

| 文章 | 支持的具体点 |
| --- | --- |
| Data443 | "确定性承重、LLM 不承重"——hook 放执行边界 deny-by-default 是正解；规则本身即策略（可读、可单测、可版本化）；p99 亚 10ms |
| FutureAGI | 60/21/14 与"确定性地板→classifier 中间层→judge 模糊余量"三级级联结构同构；确定性命中真实失败 30-60%、judge 只留 5-10% 余量 |
| MorphLLM | 六类失败分类学为 60/21/14 提供依据：格式校验（第 6 类）→ hook；语义类 → skill；混合 → 逐轮分类器 |
| F5 | "分类器是纵深防御的必要部分、混合是生产答案" |
| 阿里云注入 | hook 防注入后果（危险 shell 操作不发生）而非注入文本本身——正是 SABER 场景的设计意图 |
| Manifold（部分） | 推理层无法用穷举规则封死 → 14 个 semantic skill 必要；SABER 状态式评测回应"沙箱成功≠安全成功" |
| SABER 论文 | 判最终工作区状态并按原因分类违规，方法论上优于"命令是否被拒" |

### 审稿人的弹药（必须提前防住的攻击点）

| 攻击点 | 来源 | 具体内容 |
| --- | --- | --- |
| 分类学偷换 | MorphLLM | 六类失败五类语义——60 hook 只覆盖"格式类 + 语义类的字面情形"，真实故障空间占比可能相反 |
| cooperative enforcement 失效 | Manifold | 按命令名/路径/正则匹配可被别名、改名、软链、库调用绕过 |
| 指标不能说明全部 | F5 | 静态基准只测已知模式检测率，测不了适应性/对抗泛化/跨轮；Day Two 规则集过期 |
| 假阳性是无声杀手 | jacar/particula 实测 | 不按层报 FPR 会被质疑"用召回换可用性" |
| 成本转嫁 | jacar 实测 | 语义层用大 LLM judge：+200-800ms/轮、+15-40% 账单、捕获 60-85%、误报 5-15% |
| "你的策略"缺失 | MorphLLM | 哪些路径/文件/工具调用被允许是组织策略，静态枚举无法覆盖运行时策略细微差别 |
| DROS 抢占"分层"概念 | DROS | "确定性运行时分层"已被命名（虽有独立评测缺失、无 compression、无 hybrid 灰区） |

---

## 3. 关键量化数据（来自原文或第三方实测）

| 指标 | 确定性/规则 | 分类器 | LLM judge |
| --- | --- | --- | --- |
| 延迟 | 亚毫秒（规则）/ 亚 10ms p99（策略） | 10-100ms（NeMo <50ms GPU） | 100ms-数秒（实测 +200-800ms/轮） |
| 成本 | $0 | 几分之一美分/次 | $0.005-0.05/次（judge-only 百万日评估 $5000/天） |
| 捕获率 | 命中真实失败 30-60%（安全负载近 50%） | — | 严重问题捕获 60-85% |
| 误报率 | 低（语法可定义） | Llama Guard 3 约为 GPT-4 的 1/3 | 5-15% |
| 可复现性 | 字节级一致 | 概率+校准阈值 | 随模型版本漂移 3-8 分 |

**级联方案（FutureAGI）**：百万日评估 ~$260/天，比 judge-only（$5,000/天）便宜约 30 倍。

---

## 4. 对论文的启示（措辞 + 实验 + 指标）

### 4.1 措辞（最重要）

- ❌ 不说："hook 解决大部分安全能力"
- ✅ 改说："**hook 确定性解决 60 个语法可定义的原子（零假阳性、亚毫秒）；21 hybrid 用规范化+轻量分类器；14 semantic 承载最高爆炸半径的原子**"
- ✅ 把"安全主张"降级为**可证伪的"覆盖主张"**："检测层解决大部分已知语法类攻击"——这是 7 篇都认可的诚实口径

### 4.2 实验设计（回应攻击点）

1. **规范化先手**：hook 匹配前做 shell 语义规范化（变量展开、glob/符号链接解析、引号转义、按工具 flag 解析、命令链拆分），把混淆还原成规范形式再匹配——回应 Manifold 的 "cooperative enforcement 失效"；
2. **out-of-distribution 测试**：用 SABER 对抗集（混淆载荷、新颖 flag 组合、跨轮命令链）报 OOD 结果——回应 F5 的"测不了泛化"；
3. **Day Two 演进**：hook 规则版本化 + 持续红队流水线；语义层用可微调专用分类器（<90ms 级）而非大 LLM judge——回应 jacar 的成本/延迟陷阱；
4. **按层指标**：FPR/FNR + 延迟预算（"4ms 前门 + 40ms 混合层 + 120ms 语义层，总量在 SLA 内"）+ 剩余攻击成功率。

### 4.3 引用 DROS 的定位（novelty 差异化）

- DROS 已做"确定性运行时分层 + LLM 语义层"，**但**：层级在 OS/二进制边界（C-ABI/eBPF），语义层是防火墙式过滤（无技能分类学）；**无 ecosystem compression（95→60/21/14）**；无 hybrid 灰区；无第三方基准配对实验（自建语料 + 零社区验证）。
- 定位：把 DROS 当作"确定性分层已被提出、但缺独立评测"的对照——**你们的增量 = 操作/技能级原子分类压缩 + hybrid 灰区机制 + SABER 可复现配对证据**。
- 引用时明确区分"ABI 级确定性"与"操作/技能级确定性"。

---

## 5. 来源列表

1. DROS: https://zenodo.org/records/21903475 （配套：[VEP-lite](https://github.com/Top-Celestial-Company-Ltd/DROS-VEP-lite)、[VajraClaw](https://github.com/Top-Celestial-Company-Ltd/DROS-VajraClaw-Hacker)、[独立评测警告](https://clawdbytes.com/article/2026-08-31-show-hn-vajraclaw-deterministic-1s-execution-guardrail-for-ai-agents)）
2. Manifold: https://www.manifold.security/blog/the-sandboxing-illusion-how-to-isolate-agents
3. Data443: https://data443.com/blog/deterministic-policy-vs-llm-filters/
4. FutureAGI: https://futureagi.com/blog/deterministic-vs-llm-judge-evals-2026/
5. MorphLLM: https://www.morphllm.com/llm-guardrails （Markdown 镜像：https://www.morphllm.com/llm-guardrails.md）
6. F5: https://www.f5.com/de_de/company/blog/classifier-based-vs-llm-driven-guardrails-what-actually-works-at-ai-runtime
7. 阿里云注入: https://developer.aliyun.com/article/1690311

**第三方实测补充**：[jacar.es 守卫真实成本](https://jacar.es/en/llm-guardrails-frameworks-and-their-real-cost/) · [particula.tech 守卫对比](https://particula.tech/blog/ai-guardrails-compared-nemo-guardrails-ai-llama-guard) · [ClickHouse 守卫延迟表](https://clickhouse.com/resources/engineering/llm-guardrails) · [Infrabase 库清单](https://infrabase.ai/blog/llm-guardrails-compared) · SABER 论文 [arXiv:2606.01317](https://arxiv.org/abs/2606.01317)

**未获取字段**：MorphLLM 各库准确率/误报率/成本基准（文章只给许可证/star/延迟预算）；F5 全文无量化数据；DROS 摘要未声明局限。
