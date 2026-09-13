# OAS 222 API 并发试验

当前测试模型：硅基流动 `Pro/zai-org/GLM-5.1`，baseline `none`。任务源为内容固定的 222 个 `dependencies=[]` 任务，117 题含 NPC。NPC 使用 `Qwen/Qwen2.5-7B-Instruct`。

已通过：容器路径映射冒烟、2-worker 两题完整执行、4-worker 四题完整执行。原 8-worker 批次保持运行；目前 7 题已产出有效原生评分，剩余一题仍在执行。

用户要求提高测试档位后，停止了旧的排队控制进程，保留正在执行的独立任务进程。新的 64-worker 批次使用 64 个未跑过的任务，下一档为 128 workers；高档全部通过后再安排余下任务。所有阶段选择清单均保留在本目录，已分配的任务不会混入后续批次。

资源：小档每容器 1 CPU，高档（64/128）每容器 0.25 CPU，均 2 GiB 内存、512 PIDs；因此不同档位的 CPU 限制不同，耗时不能仅归因于 worker 数量。128 容器的 CPU 上限合计 32 核。实际峰值和样本资源用量记录在 `resources.jsonl`。已经观察到 64 个当前批次的容器同时运行；这不等同于 64 个 API 请求同时在推理。

API 限额：[官方说明](https://docs.siliconflow.cn/docs/userguide/rate-limits/rate-limit-and-upgradation)给出聊天模型 RPM 1000–10000、TPM 50000–5000000 的范围，按账号和模型生效，具体模型与等级不同。此范围不是本账号实际配额。此次 GLM 响应未返回限额头。旧 `/user/info` 已由[官方公告](https://docs.siliconflow.cn/docs/release-notes/overview)宣布于 2026-08-14 停用；没有据此推算本账号额度。

主要记录：`plan.json`、`lifecycle-approval.json`、`active-stage.json`、`controller-handoff.json`、`glm5-capacity-w4-summary.json`、`glm5-high-capacity.json`（高档结束后生成）、`high-capacity.log`。

原始结果：`/srv/benchmark/skills/results/oas-api222-20260912-r1/`。有效零分计为正常完成；API/会话异常、缺少评分、仅部分轨迹评分不计为有效完成。仍将保留已知 5 个异常题在总共 222 题的范围中，单独检查它们的失败原因。

容器回收范围只包括此次批准的名称前缀和会话标签。不会删除已有镜像、卷、文件或其他任务资源。
