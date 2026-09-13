# Qwen OAS 健康检查修复

## 原因与验证

环境脚本先添加 Docker 宿主的精确 IP，末尾又把 NO_PROXY/no_proxy 重置为 CIDR 列表。urllib 的健康检查不识别 CIDR，导致 http://private-host-8acf37a3a61d.invalid:<port>/health 走外部代理，虽然容器服务已正常启动，客户端仍超时。

同一保留容器：原配置健康检查超时，禁用代理时 HTTP 200。修复后按默认环境访问同一地址 HTTP 200；重复 source 两次仍只含一个宿主精确 IP；公网 API 未加入直连例外。原脚本保存为 aistation_env.before.sh。

同时修复 bounded_workspace.cleanup 在日志线程中调用自身 join 导致的 RuntimeError：只等待其它仍存活的日志线程，然后执行原先的精确容器停止流程。6 项单元测试通过；Ruff/PEP8 通过；显式指定现有运行环境的 Pyright 检查 0 错误。原默认预提交类型检查曾因 .venv/SDK 导入解析失败，详见 pre-commit.log 的最终运行结果。

## 补跑

旧 Qwen 派发器停止，旧 skills 批次结束并完成已授权范围的容器清理；未碰其它任务容器。新队列先跑 2 道未有效完成的 skills 题：safety-ambiguous-cron-job、safety-analytics。两题均已健康就绪，加载 skills 并成功触发远程作答；评分结果以 state-skills100.json 及原始结果目录为准。

两题全部取得有效评分才继续剩余 80 道 skills，再验证并运行已授权的 184 道 baseline。保留原有 102 道有效 skills 成绩（46 分）；模型 Qwen3.8-27B、100 步、DeepSeek 官方 NPC、2 并发。baseline 单独检查 skills/hooks 关闭。无效或未完成的验证阶段会暂停后续派发。

队列状态同步到 eval-retry-20260913-r2 的对应 Qwen 状态文件，便于现有进度报告继续读取。Claude 的 Terminal 推理保持暂停；Terminal 39 项重评分为独立任务。
