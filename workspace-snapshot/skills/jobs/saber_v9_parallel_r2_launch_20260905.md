# V9 GLM / gpt-oss 并行调度已提交

记录时间：2026-09-05 23:07 北京时间。本记录取代此前交接中“等待清理授权、尚未启动辅助调度”的历史状态。

用户在明确说明本批次自建 gpt-oss 容器清理范围后回复“启动”，启动审批已通过。清理仅限本辅助任务新建、同时具有 batch `v9-full-20260905-r1`、model `gptoss` 标签，且名称以 `rick-saber-v9-full-20260905-r1-gptoss-` 开头的容器。不删除结果、镜像或其他任务资源。

启动前静态复核发现旧辅助入口的 `event(name, **fields)` 与生命周期回调 `event('process_started', name=...)` 参数冲突。仅将首参改为 `event_name`，并另建 `parallel-gptoss-r2` 快照。旧辅助 r1 和冻结主队列保持不变，旧 r1 从未启动。仅 AST 检查，没有额外测试或模型试跑。

- 快照：`skills/jobs/saber-v9-full-20260905-r1/parallel-gptoss-r2/`。
- 日志：`skills/logs/saber-v9-full-20260905-r1/parallel-gptoss-r2/`。
- 23:06:56 提交 watcher，PID 2097821；23:07:46 核实 PPID 1、SID/PGID 2097821，进程存活。
- 当前状态 `waiting_for_glm`，尚无 `execution-started.json`：启动的是调度，不是 gpt-oss 推理。
- 主 MiniMax 未中断：23:07:46 写入 346/716 条，近 5 分钟新增 23 条，两卡利用率均 100%。
- 实际顺序：MiniMax（双卡）→ DeepSeek Flash（双卡）→ Qwen（双卡双副本）→ GLM（GPU 1）与 gpt-oss（GPU 0）并行，各 8 worker。
- GLM 服务就绪后辅助自动通过 `gpu-idle run --gpus 0` 申请 GPU 0；持有 R2 `gptoss.lock` 直到完整清理结束，再释放 GPU 预约。
- 主队列之后到达自身 gpt-oss 步骤时按原逻辑跳过已存在结果；仍有服务加载／完整性核验开销，不能声称完全没有收尾时间。
- 主控制器身份失效或错过 GLM 窗口时，辅助会退出，不自动接管未知服务。

后续以新辅助 r2 日志为准，不得重复提交 r2 或再提交旧 r1。技术修复尚未部署，旧结果不修改；本次启动不代表全量完成或 Judge 门禁通过。
