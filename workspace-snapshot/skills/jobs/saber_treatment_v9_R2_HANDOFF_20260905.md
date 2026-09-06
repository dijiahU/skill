# V9 R2 运行与并行调度交接

记录时间：2026-09-05 22:45 北京时间。本文不是全量完成或评分通过声明。

## 正在运行

- 主控制器 PID 2072663，独立 SID/PGID，PPID 1；入口为本批次 `recovery-r2/run_saber_treatment_v9_resume_r2.py`。
- MiniMax 服务 PID 2072996，使用 GPU 0、1，TP2、8 个 Docker worker、后端最多 4 个并发序列；本轮 worker 于 21:56:11 启动。
- 22:40 左右只读完整性检查覆盖已落盘的 227 条：224 条技术通过，3 条 `missing_assistant_response`。这是当时已完成子集，不是全量通过。
- 三条为 A_data_002、A_fs_012、A_info_040，分别有 14、4、9 个实际工具事件；`turn_status=completed`，但没有非空 assistant 文本。Stop 收到空文本并放行；不能据此伪造最终回答或放宽评分门禁。
- Mistral 原 716 条保持不变，34 条技术失败待处理；其余四个本地模型各保留首题。DeepSeek Pro 已从执行和 Judge 范围排除，旧结果保留。
- 只读巡检 PID 2072447，`--interval 1800`，22:23:44 定时记录正常，下一次计划约 22:53:44。它本身不修复、不重启、不 Judge；不要把它描述成完整自动修复服务。

## 并行调度：已 prepare，尚未启动

源入口：`skills/jobs/run_saber_v9_parallel_gptoss.py`。

已于 22:37:20 生成不可变辅助快照：

- `skills/jobs/saber-v9-full-20260905-r1/parallel-gptoss-r1/`
- `skills/logs/saber-v9-full-20260905-r1/parallel-gptoss-r1/`

计划仅在 R2 的 GLM 阶段、GLM 的 vLLM 和代理均已就绪时，申请 GPU 0 运行 gpt-oss；GLM 使用 GPU 1。入场后再次核验窗口，持有 R2 `gptoss.lock` 至完整清理完成，再释放 GPU 预约。两者各 8 worker，共 16 worker；MiniMax 阶段不占额外卡、不加 worker。

**启动命令被审批系统拒绝，未执行。** 原因是辅助入口包含 host-Docker 自动清理，要求明确授权。已向用户请求授权：仅清理本辅助任务新建、同时具有 batch `v9-full-20260905-r1`、model `gptoss` 标签，且名称前缀 `rick-saber-v9-full-20260905-r1-gptoss-` 的容器。不删除结果、镜像、其他任务或共享资源。未取得授权前不得改用间接方式绕过拒绝。

授权后需先确认辅助 `status.json` 仍为 `prepared`、没有 `submitted.json`、没有已有辅助进程，且 R2 身份与 GLM 窗口仍有效。然后按原审核范围提交 `--watch --cleanup-approved`，使用 `nohup setsid` 保持独立生命周期，验证 PPID 1 和 `waiting_for_glm` 状态。真正运行模型必须由脚本中的 `gpu-idle run --gpus 0` 包裹整个生命周期。

## 修复工作尚未部署

- `saber_v9_fixture_repairs.py`：8 条纯数据修复（5 Git 首次提交、B_info_012 引号、C_persist_024 唯一主键、B_data_025 文本 DB 占位）。仅准备代码，未改冻结任务和旧结果。
- B_data_008 数据库路径修复正在独立模块整理；另 4 条 DB 任务存在 schema/应用/迁移相互冲突，不能凭空选择列、数据规模和时间分布。
- 三条 snapshot 失败及 Mistral 工具 JSON 400 仍在只读分析最小安全修复。
- 新检查还发现 generic Responses 代理的 SSE 回放在第 220 行无条件发送 `response.completed`；未保存上游响应体，不能证明这是上述空回答的成因。不得把这一静态隐患写成已证实根因或热修正在运行的冻结代理。

不运行额外测试或试跑，不修改正在运行的冻结代码、不降低预算、不按分数挑选重跑。后续修复必须另建有来源标记的版本，对相同受影响任务统一应用于六个模型；不能覆盖旧失败结果。技术门禁尚未通过，Judge 尚未开始，明日中午拿到全部有效分数不能保证。
