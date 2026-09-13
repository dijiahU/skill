# Terminal-Bench 2.1 评分修复

2026-09-13：Claude 按用户要求保持暂停。控制器、API 桥接器、Harbor 和 Codex 子进程使用 SIGSTOP 暂停；无 Docker 停止或删除操作。暂停记录位于 Claude 任务目录。

## 已完成

- 本轮汇总、API 启动检查及补跑选择共用 verifier_integrity.py：必须具有完整、非空、与奖励一致的真实 CTRF 测试报告；下载/收集失败不计 0 分。
- 新运行器在官方 verifier 执行后再次核验，失败抛出 VerifierIntegrityError；拒绝复用旧评分文件。
- 后续 Harbor 启动脚本加载本目录 adapter；任务下载走已验证的 HTTP 代理，同时配置大小写代理变量和 PyPI 地址，取消强制直连。
- 旧 result.json 保留。对评分无效的已结束尝试，可使用 regrade_retained.py 重跑原测试，仅替换评分输出目录和下载环境。核验容器名称/标签、原测试内容和结果哈希。
- 同一产物仅采用首个有效重评分；原先有效的 0 分不会被替换，不按最高分选取。
- 汇总文档及 CSV 已重新生成，待核查/重评分题在 terminal-verifier-pending.csv 单列。

## 实测证据

- 6 项评分有效性回归检查、3 项运行器检查通过。
- runc、network=none 的新建临时容器从本地 wheels 安装 pytest，1 项测试通过；退出容器保留，未清理。
- Claude fix-git 原产物仅重跑原 verifier，2/2 测试通过，reward=1；此前 DNS 导致的 0 无效。原测试 SHA-256 与容器内内容逐文件一致。未调用模型 API。

## 生效范围与后续

评分汇总修复立即生效。Python 中已加载的旧运行器代码和已创建容器的环境不会热更新；新代理及运行时评分检查在新启动的 Harbor 进程/容器中生效。Claude 未恢复，恢复时应使用新批次补齐未完成项，避免直接续用计时已过的旧进程。其它运行中的模型未中断，新增旧环境异常会被新版汇总排除。

本次没有调整安全拦截预算、skills 规则或测试断言。误拦截及连续三次拦截终止策略需另行分析或配对实验，不应与环境修复混为同一实验条件。尚未批量补跑待重评分清单，也未启动新模型推理。

原代码及原报告保存在 before/、report-before/；变更哈希和验证结果见 changed-sha256.json、validation.json。
