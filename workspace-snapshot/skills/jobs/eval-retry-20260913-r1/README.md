# 2026-09-13 异常补跑

用户授权：把当前分数计入文档，然后开始补跑。启动前成绩已保存至汇总报告及其 archive-before-retry 目录。

- OAS 100 步 skills：GLM 8、DeepSeek 5、Qwen 88、gpt-oss 21 题。
- OAS 100 步 baseline：DeepSeek 13、Qwen 184 题；每个模型先 skills 再 baseline，Qwen 先以其中两题验证 baseline 隔离，验证通过后运行其余题。
- Terminal-Bench 2.1 skills：GPT 19、Gemini 56、gpt-oss 23 题。
- 旧 GLM 30 步 baseline 仅保留为历史数据，不混入 100 步补测。
- 只选择没有有效评分的题目，每题本次最多新增一次；既有有效 0 分同样保留。OAS 排除原定 38 道不可评分题。
- OAS 并发：GLM/gpt-oss 4，DeepSeek/Qwen 2；Terminal 每模型 2。不提高原定步数、官方任务超时、模型上下文。
- 网络修复仅作用于本批任务：外部 API 使用既有 HTTP 代理，本机服务和宿主 Docker 直连，不修改集群 DNS。
- Terminal 读取容量：8192 文件、32768 条目录记录、32 层、单文件 16 MB、总计 128 MB；读取器和校验器同步扩大。保留不可读、范围越界、大小超限时的拒绝行为，安全规则与评分器不变。测试证据在 preflight/observer-capacity.json。
- gpt-oss OAS/GPU0 与 Terminal/GPU1 通过 gpu-idle 匹配预约并行，生命周期覆盖模型服务和消费者。
- OAS 沿用原名称前缀与会话标签双重核验的生命周期授权。Terminal 容器继续保留，不进行停止/删除操作。
- 新补测结果仍位于原结果根目录的 retry1/supplement 新阶段；原始输出不覆盖。Terminal 扩大读取容量会影响可执行题目范围，作为适配器修复后的补测注明，不能推断为同一运行条件下的随机重复。
