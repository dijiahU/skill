# Mistral U+FFFD 根因、兼容修复与验证

状态：根因已用真实 tokenizer 的 CPU 路径复现；独立 opt-in 修复已实现；Mistral r2 双 GPU 协议探针由根流程运行并通过。本审计没有启动 GPU、Docker 或 SABER 轨迹，也没有修改安装包、旧兼容层或历史结果。

## 历史范围

只读脚本 `scan_mistral_fffd.py` 扫描 v9 五个模型各 716 条真实 raw JSON，排除 `_attempts`。机器清单在 `mistral_fffd_inventory.json`，逐条保存 task ID、raw 路径和 SHA-256。

- Mistral 的 assistant `content` 中有 501/716 条记录、1,374 条消息包含 U+FFFD，共 15,004 个字符。
- Mistral 的 assistant `tool_calls` 序列化字段中有 109 条记录、8,080 个 U+FFFD；与 content 可能重叠，不能和 15,004 直接相加推断独立损坏量。两字段并集为 512 条记录。
- DeepSeek Flash 只有 1 条记录的 assistant content 含 1 个 U+FFFD；MiniMax、GLM、gpt-oss 为 0。

这个模型集中度支持 Mistral 服务路径特有故障，但不证明 501 条全部因此判为能力失败，也不提供 baseline 分数对照。

## 可复现根因

v9 冻结配置 `skills/jobs/saber-v9-full-20260905-r1/frozen/configs/mistral-0.json` 和冻结 model spec 指向本地 vLLM 服务；服务监听 18030，Responses 兼容代理只做协议和预算转换。旧 `mistral_developer_role/sitecustomize.py` 只修消息角色和工具字段。没有通用文本代理参与增量解码。

实际环境是 `deepseekv4-vllm`。Mistral tool parser 在 `vllm/tool_parsers/mistral_tool_parser.py:178-180` 为工具路径设置 `request.skip_special_tokens = False`。`vllm/tokenizers/mistral.py:499-502` 在该模式下逐 token 调 `id_to_piece`。Tekken 的 byte fallback token 可以只包含一个多字节 UTF-8 字符的一部分；slow incremental detokenizer 若先把每片变成字符串，边界信息已经丢失并出现 U+FFFD。Responses streamer只是传递产生的增量文本，不能在流末可靠恢复原始字节。

`mistral_utf8_regression.json` 使用模型真实 tokenizer 文件，证明 batch decode 对中文和 emoji 正确，而未修复的 slow incremental decode 在“让我检查系统的防火墙服务状态。”中产生 4 个 U+FFFD，在“✅ 安全检查完成 🔒”中产生 5 个。ASCII 对照保持正确。这是实际多字节 token 边界复现，不是手工构造的乱码替换。

## opt-in 修复边界

新路径 `skills/compat/mistral_utf8_v10/` 不修改 vLLM、mistral-common、模型 tokenizer 文件或旧 sitecustomize：

- `mistral_utf8_compat.py` 只在 `SABER_MISTRAL_UTF8_COMPAT_V10=1` 时包装 vLLM slow incremental 的定义和 engine 已导入引用。仅对 `vllm.tokenizers.mistral.MistralTokenizer`、Tekken、`skip_special_tokens=False` 生效，让 byte fallback 片段在相邻 token 合并后再解码。
- 修复不按字符过滤 U+FFFD。回归中的真实 literal U+FFFD 保留 1 个，最终累计文本必须逐字等于 batch decode。
- 工具 JSON 和 `[TOOL_CALLS]` framing 逐字等于 batch decode并可解析；tokenizer 类、vocab key 类型和特殊工具 marker 不变。
- `sitecustomize.py` 在旧 developer-role shim 被显式要求却不存在时抛错；因为 Python 对 sitecustomize 异常可能打印后继续，`verify_activation.py` 是启动前 fail-closed gate，核对 utility/engine patch marker及引用一致性。

Responses 的工具对象还有独立问题：`FunctionTool` 会把未指定 `strict` 物化为 `null`，而 Mistral schema要求 bool。r1 服务因此在 `tool-first-count.json` 返回 400。`mistral_tool_strict_compat.py` 仅在 `SABER_MISTRAL_TOOL_STRICT_COMPAT_V10=1` 时，在送入 Mistral converter 前省略 `strict=None`；显式 `False` 和 `True` 原样保留。`mistral_tool_strict_regression.json` 走真实 `FunctionTool -> construct_tool_dicts -> Mistral converter` 路径，baseline复现 ValidationError，三个修复用例均通过。

## 验证结果

CPU 回归：

- `mistral_utf8_regression.json`: `passed=true`；中文、emoji、ASCII/混合文本均与 batch decode 完全一致，工具 JSON 可解析，literal U+FFFD 未被删除。
- `mistral_tool_strict_regression.json`: `passed=true`；None 被省略，False/True 被保留，安装幂等。

根流程的真实 Mistral r2 服务探针位于 `protocol-mistral-r2/`：

- `status.json` 为 `probe_passed`；ASCII 与 Unicode 的 token-count 和 Responses usage 一致。
- `unicode-response.json` 最终文本为 `中文路径/防火墙/🙂`；`unicode-stream-validation.json` 记录 17 个 SSE event、delta 与 final 完全一致、replacement_count=0。
- `tool-first-count.json` 和 `tool-second-count.json` 均为 200，分别计数 130、175 tokens；首轮函数参数和第二轮最终文本都保留 `中文路径/防火墙/🙂`。
- `long-boundary-count.json` 在 32,768 context 限制下计数 28,704，证明兼容层也出现在长上下文计数路径的 marker 中。

r2 验证的是冻结 source hash 对应的兼容模块。以后修改该目录需生成新版本并重新跑 CPU 与真实服务探针；不能把旧 r2 结果移用于新 hash。
