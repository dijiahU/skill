# Claude Opus 5 Terminal-Bench 2.1

用户授权启动 Claude 的 Terminal 正式评测。共 89 题，skills/hooks 条件、每题首次一次、2 并发。

主模型 claude-opus-5，APINebula Claude Key；通过已验证的 Responses→Chat 转换层接入。转换层持久化每个完成请求的 token usage，便于费用核对；结果及请求日志不存 API Key。

数据集 commit 7131e4375048a0e408a8fb404b5f499d726b695b。上下文 65536 tokens，工具尝试上限 1000，沿用官方逐题 agent/verifier 超时。使用当前修复版完整 skills/hooks 与工作区读取容量。

先运行 openssl-selfsigned-cert、fix-git 两道真实验证题；两题须都有有效官方评分、完整 skills 接入证据，且至少一题实际执行工具。有效 0 分保留。通过后自动运行剩余 87 题，验证题不重复运行。验证失败则暂停，保留原因与原始结果。

API 验证与运行状态：state-claude.json。逐题结果保存在原 terminal-api-foreign-20260913-r1 根目录的 claude-smoke/full 阶段。Docker 资源继续保留，不进行删除或停止操作。无 GPU 预约需求。
