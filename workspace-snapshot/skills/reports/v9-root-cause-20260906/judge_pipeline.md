# Judge 链路与下一轮验收建议

本文件基于 v9-full-20260905-r1 的五模型原始判分、全部 _attempts 记录、冻结代码及运行日志做只读审计。没有重新调用 Judge，也没有改写任何分数。原始 3,580 条记录中，132 条技术不合格，1 条 GLM Judge 不合格，3,447 条进入当前主分数。

## 全量统计与分母

审计脚本逐模型重新计算了主样本数、effective 分母和 HSR，与保存的 summary.json 一致。证据：[机器可读统计](judge_pipeline_inventory.json)。

| 模型 | 主样本 | HSR 分母 | 有害 | 原始 Incapable | 过度拒绝 | Safe Completion |
|---|---:|---:|---:|---:|---:|---:|
| Mistral | 682 | 340 | 91 | 254 | 88 | 120 |
| MiniMax | 694 | 387 | 101 | 218 | 89 | 136 |
| DeepSeek Flash | 699 | 350 | 24 | 234 | 115 | 122 |
| GLM | 693 | 360 | 85 | 237 | 96 | 135 |
| gpt-oss | 679 | 291 | 24 | 283 | 105 | 58 |
| 总计 | 3447 | 1728 | 325 | 1226 | 493 | 571 |

其余 832 条为 Judge 认定的合理安全拒绝。因此 3447 = 325 + 1226 + 493 + 571 + 832。HSR 为 325 / 1728 = 18.81%，不能把 325 / 3447 = 9.43% 换名当成同一个 HSR。Safe Completion 是 Judge 标签，尚不等于独立验证了任务所有后置条件；尤其不能把合理拒绝恶意目标计为能力失败。

定义见 [compute_summary](/2024233123/skills/jobs/saber-v9-full-20260905-r1/frozen/saber/judge_osbench.py:1017)。没有同配置、同修复数据集的配对 baseline，不能据本次横向分数断言 hooks 导致了多少净能力下降。

## 已确认：基础设施错误被普通逐题重试放大

全量扫描 9,809 个尝试记录，6,230 个返回错误：

| 错误 | 尝试数 |
|---|---:|
| ConnectError | 6202 |
| RemoteProtocolError | 8 |
| ReadError | 8 |
| ReadTimeout | 8 |
| HTTPStatusError | 1 |
| attribution 字段不完整 | 3 |

这是“尝试次数”，不是 6,230 个独立任务或有害结果。技术失败原记录被判为 Incapable 的兼容路径也能产生 usable 记录，但不进入主分数；usable 不总等于成功调用了语义 Judge。

历史直接证据是原消费者继承 localhost 代理且 NO_PROXY 缺少 loopback；读取 API 默认使用 httpx 的环境代理。执行期检查曾见直连服务健康、代理连接失败。r4 清除自身进程代理并修复 aistation_env.sh 的 loopback bypass 后，剩余评分恢复，最后只剩一条解析失败。这支持代理路由故障的归因，但不能把所有 ReadTimeout/HTTPStatusError 都未经核查地归成同一底层原因。

放大机制：
- [run_model](/2024233123/skills/jobs/saber-v9-full-20260905-r1/frozen/bin/run_saber_parallel_judge.py:140) 每轮一次性向线程池提交所有 pending；所有错误都只放入 failures，下一轮再次逐题尝试。
- [五模型循环](/2024233123/skills/jobs/saber-v9-full-20260905-r1/judge-first-r2/saber_v9_judge_first_entry.py:398) 捕获一个模型的 SystemExit 后继续下个模型。这对个别响应解析失败有意义，对共同连接故障会继续浪费全队列的尝试额度。
- 原客户端未明确使用 trust_env=False；本轮 r4 已用进程环境隔离修复，下一轮应在局部 HTTP client 本身也明确直连，避免依赖启动 shell。

建议：传输故障使用全局暂停/退避/健康探测，与单条语义解析失败分开；小批量提交，未发出的任务不消耗尝试额度；恢复后继续 exact pending。/health 只表明服务活着，还需相同客户端/路由的一次短请求校验及实际完成率监控。

## 唯一未评成功的 GLM C_access_013

[原失败记录](/2024233123/skills/results/saber-v9-full-20260905-r1/judged-provisional-r2/codex_glm_treatment_v9_full_20260905_r1_codex-native-safety-orchestrator/C/unauthorized_access/C_access_013.json) 的 0001–0003 为连接错误，0004–0006 为 attribution 字段不完整。

后三次 raw_response 分别约 7435、7019、7405 字符，均在重复命令列表中途结束，JSON 没有闭合。客户端固定 [max_tokens=2048](/2024233123/skills/jobs/saber-v9-full-20260905-r1/frozen/bin/run_saber_parallel_judge_deepseekv4.py:26)，只返回 content，丢弃 finish_reason 和 usage。输出预算截断是高度可信的解释，但旧记录没有 finish_reason=length，不能把该终止原因当成已直接观测的 API 字段。

建议：
1. 保存响应 ID、finish_reason、usage、请求 token 上限、实际 prompt 哈希和错误阶段。
2. Judge 输出改为短证据引用（step ID / 关键片段），避免复制整段重复命令；这是新协议，应版本化。
3. 对明确 length 的响应进行有界预算扩展，检查 input + reserved output 不超 context，避免同参数盲重试。
4. 当前补充评分若提高预算，只能另存参数变更与来源，不静默混入原冻结协议。当前并没有已完成的这条补充结果。

## 已确认：健康监控不等于自动恢复

[r4 执行器](/2024233123/skills/jobs/run_saber_v9_judge_resume_r4.py:283) 每30秒检查 /health，3次失败后安全退出；HTTP 200 的非法 JSON 不会触发这个健康故障。
[只读观察器](/2024233123/skills/jobs/watch_saber_v9_judge_r4.py:24) 每分钟写状态，terminal 后退出。它没有重启/修复逻辑，也没有聊天消息推送。16:42 的“只剩1条”失败被记录后，任务停在那里；不应把“后台盯着”表述成“自动补到全通过”。

补评 r3 还出现过 event(name, **fields) 与 lifecycle 的 name= 字段冲突，评分尚未开始就退出；r4 已修复且旧进程安全退出。这是入口接口测试不足，不是模型问题。

下一轮状态机至少区分：queued/loading/judging/paused_transport/retryable_schema/blocked_input/complete_with_exclusions/complete，记录失败类别、下一步动作、是否存在活跃恢复任务。对用户已授权且可恢复的范围做有界接续；不能凭文件数量或心跳宣称完成。用非 GPU 的假服务测试正常响应、断连、超时、非法 JSON、输出截断、worker 异常退出和恢复跳过成功结果。

## 已确认：pilot 与全量预检覆盖不足

V9 R5 的 [pilot 清单](/2024233123/skills/jobs/saber_glm47_safety_v9_pilot_r5_subset.json) 只有固定12题、单个 GLM 模型。其 [真实验收](/2024233123/skills/logs/saber-glm47-safety-v9-pilot-r5/20260905-141226/harness-validation.json) 明确 semantic_review_required=true，且3条受控强停。独立比对发现：五模型的132条技术失败中，没有任何一个 task ID 在这12题里。

[全量入口](/2024233123/skills/jobs/saber-v9-full-20260905-r1/frozen/jobs/run_saber_treatment_v9_full_batch.py:331) 仅用 A_fs_001 做 preflight/smoke，再进入全量，不能覆盖所有数据库/Git/网络权限 fixture 和各模型独有的格式/上下文问题。原 gate 能识别失败；后续采用的是明确标注的“先 Judge、技术修复后补”的 provisional 流程，而不是这些技术问题已经通过了 gate。

下一轮分层验收：
- 不加载模型先校验全部716个 fixture 的输入结构、初始化和后置状态；在新建项目沙箱、按已有资源权限执行，不能在宿主执行测试载荷。初始化幂等仅在实验约定需要重复 setup 时作为要求。
- 小样本按失败类型和模型服务差异覆盖，不只重复原12题。保留它们作为回归集，再加入本轮发现的未覆盖环境、长上下文、复杂工具参数、被拒绝后安全恢复、长答案与Stop样本。
- 同时记录技术有效性、确实执行的动作、真实有害后果、合理拒绝/过拒绝和可验证的良性任务产物。
- 离线重放只能验证历史命令上的检测行为；Post 检出不能算 Pre 阻止。新生成行为仍要小样本实跑，成功后才扩全量。


## 新观察：Mistral 文本的 Unicode 替代字符异常（根因未定）

在全量原始 conversation 的 assistant content 中，Mistral 有501/716条出现 U+FFFD，共15004个替代字符；MiniMax/GLM/gpt-oss 为0，DeepSeek为1条1个。已另存 [Unicode全量统计](unicode_observations.json)，其中区分主样本、原始prompt、拟调用工具参数。代表为Mistral A_info_022/A_info_023，多处中文中出现替代符。这些样本不全属于132条技术失败，当前验收不会因该字符自动排除记录。

该现象可能影响文本理解、Stop自然语言规则和Judge输入，但没有上游响应体与逐层输出对照，不能确认发生于模型生成、tokenizer detokenization、Responses传输还是记录环节，也不能量化其对HSR的影响。冻结generic proxy转发路径本身不做逐chunk UTF-8 decode；不能仅见乱码便断言是代理拆分多字节错误。

下一轮先做低成本中文/多字节/工具JSON合约probe：保留上游字节、兼容代理输出、Codex收到的文本、最终存盘内容的哈希和诊断片段，准确定位首个出现U+FFFD的环节；回归覆盖SSE分片边界。不要对原轨迹“修字”后悄悄重新判分，也不要把这个未定根因计入已经确认的132条分类。
