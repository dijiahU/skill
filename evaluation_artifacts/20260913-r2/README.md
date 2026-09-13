# 新代码与补测轨迹（增量快照）

本目录包含上次发布后新增或变化的 OAS、Terminal、SABER API 记录，包括失败、超时及限流重试。旧归档保留在 [上一版](../20260913/README.md)。本快照不是最终排行榜。

新修复包括编辑参数归一化、单 JSON hook 协议、模型可见脱敏与警告、可信参考读取、轨迹完整性标记，以及环境变量和 CI 安全检查。相关测试在隔离源码上通过；发布副本另外检查语法、凭据与部署信息脱敏和归档哈希。

- [本轮逐条行为复核](../../reports/oas-danger-retest-20260913-r1/retest-trajectory-review.md)
- [运行进度快照](../../reports/oas-danger-retest-20260913-r1/progress.json)
- [修复前根因分析](../../reports/oas-danger-analysis-20260913-r1/README.md)
- [评分方向与可比性分析](../../reports/oas-skills-analysis-20260913-r1/README.md)
- [可直接浏览的新轨迹](browse/oas-danger-retest-20260913-r1)
- [文件索引](files.jsonl)、[分片清单](manifest.json)、[验证记录](verification.json)

这些 OAS 任务的风险分为 1 时通常表示命中危险行为；0 不保证安全完成。复核报告区分主动拒绝、危险代码生成、实际执行和评分漏检。合成测试凭据也可能被公开导出规则替换。

恢复：先按上一版说明恢复旧归档，再按 manifest.json 中每个 archive.parts 的顺序拼接分片并解压本次 tar.gz，覆盖同名旧文件。每条 files.jsonl 同时保留原始及公开副本 SHA256；source_changed_during_read=true 表示读取时该文件仍在变化。运行中日志只保留捕获前缀；无效或不完整 JSON 记录列在 skipped.jsonl。

公开副本已替换密钥、内网地址及宿主目录；原始本地数据未改变。报告中的本地轨迹路径可通过文件索引映射至归档。部署重放需要填写自己的环境配置。

捕获时间：2026-09-13T15:59:04.557691+00:00 至 2026-09-13T15:59:56.219356+00:00。新增/变化文件 2494 个；未变化文件 26320 个。
