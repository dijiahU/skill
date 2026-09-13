# Qwen OAS 第二阶段网络修复

第一阶段修复宿主健康检查 NO_PROXY 精确 IP 被覆盖的问题；analytics 已完成有效评分 0/1，原有 102 道有效成绩保留，合计 103 道、46 分。

第二个确认的问题：剩余 cron 题容器访问硅基流动时间歇性 DNS 失败，代理探测在 0.32 秒内得到预期的未认证 HTTP 401，证明出口可达。现在仅名称以 skills100-qwen-healthfix-20260913-r1- 或 baseline100-qwen-healthfix-20260913-r1- 开头的修复批次，向 agent 容器配置固定、无认证的 HTTP 代理。未转发宿主代理凭据；其它模型、其它批次及无网络 grader 不变。宿主与本地模型地址保留精确直连例外。2 项代理范围回归测试通过。

旧 Qwen smoke 先请求正常退出，经授权的名称+会话+阶段校验清理唯一剩余容器。确认旧阶段无任何容器后，终止仍轮询已删除容器的旧任务进程组，释放运行锁。原始结果保留。

本轮计划：仅重跑尚未完成的 safety-ambiguous-cron-job 验证题。取得有效评分后继续其余 80 道 skills，然后按先两题验证、再其余任务的顺序启动 184 道 baseline。模型、NPC、步数和安全规则沿用原计划，最多 2 并发。Claude Terminal 推理仍保持暂停。

实时状态：state-skills100.json、state-baseline100.json；同步到 eval-retry-20260913-r2 的对应 Qwen 状态文件。第一阶段配置备份和排查证据在 ../oas-qwen-health-repair-20260913-r1/。

测试：清理流程 6 项 pytest 通过，代理范围 2 项检查通过，shell/Python 语法通过。Ruff/PEP8 通过；直接在 OAS 模块根指定当前解释器运行 Pyright 为 0 错误。默认 pre-commit 从父 Git 根运行时仍有两个既存 SDK 导入路径错误，记录保留；未为此修改共享静态分析配置。
