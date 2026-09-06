# Qwen 空闲 GPU 自动填充

入口：/2024233123/skills/bin/gpu-idle

## 工作方式

控制器每约 2 秒检查 GPU 0/1，连续空闲 30 秒才启动 Qwen3.8-27B-FP8。
“空闲”要求显存低于 2 GiB、没有 CUDA 计算进程、没有可见的其他模型服务，
也没有正式任务预约；0% 计算利用率不等于空闲。
每张空闲卡独立运行 1 个 Qwen、4 个 SABER treatment worker；
两张卡空闲就是两个副本，合计 8 worker，不是单模型 TP=2。

每个 worker 独立轮换 8 个任务子集，完成后立即继续。
模型保持驻留，没有“最慢 worker 跑完才能开始下一轮”的屏障。
让卡时终止后台副本、释放显存；重新空闲后自动重新加载、从新一批开始，
不保留断点。模型加载通常需要约 1–2 分钟，不可能在切换期间保持 100% 利用率。

## 启动与查看

~~~bash
/2024233123/skills/bin/gpu-idle start
/2024233123/skills/bin/gpu-idle status
/2024233123/skills/bin/gpu-idle stop
~~~

进程脱离终端运行。Pod/节点重启不会自动重建守护器，需重新执行 start。
旧单卡/双卡 forever 脚本与此控制器共用互斥锁，不要同时使用。

## 正式任务优先

所有新 GPU 作业通过统一入口启动，以便在分配显存之前让卡：

~~~bash
# GPU 1 的已知单卡脚本
/2024233123/skills/bin/gpu-idle run --gpus 1 -- \
  bash /2024233123/skills/jobs/run_saber_glm47_baseline_716.sh

# 双卡任务
/2024233123/skills/bin/gpu-idle run --gpus 0,1 -- \
  bash /2024233123/skills/jobs/run_saber_mistral_small4_119b_baseline_716.sh
~~~

入口先预约对应 GPU，等待后台副本及临时容器退出，确认显存释放后执行命令；
正式命令退出后解除预约，后台自动恢复。默认等待上限 600 秒，
可用 --timeout 调整，超时不会启动正式命令。
单卡预约只影响那一张卡。--gpus 使用物理卡号，作业内不要覆盖为其他卡号。
请将模型服务与测试消费者的完整生命周期放在同一个受管理的命令中，
不要仅用启动即退出的 nohup 命令作为正式任务。
已运行服务尚未退出，即使测试已结束，也视为卡被使用；控制器不会停止它。

对绕过入口的本地 vLLM/torchrun 启动有提前检测，对额外 CUDA 进程有兜底检测，
但这是轮询，无法保证任意直接运行的程序在申请显存前被发现。
其他 Pod/AIStation 训练任务没有接入该入口，不能视为集群级抢占调度器。
可靠的“正式任务先让卡再加载”要求使用上述入口。

## 数据、资源和日志

SABER 结果仅存于每个 runner 的 1 GiB tmpfs，Docker 任务日志关闭。
不写正式 results/、不 judge。服务日志、状态、预约记录保留在
/2024233123/skills/logs/gpu-idle/，无需删除文件。
状态见 status.json，切换记录见 events.log，每次加载日志见 sessions/。

让卡仅终止控制器亲自创建的进程组；容器必须同时具有当前会话 label
及 rick-saber-idle-<session>- 前缀，包含 runner 和嵌套沙箱。
后台临时容器为 --rm，结束时自动移除；不清理任何镜像、共享资源或正式任务。
如果控制器被 SIGKILL 且状态仍记录未清理的副本，start 会拒绝盲目接管，
应先核验残留资源。常规停机使用 gpu-idle stop。

## 验证

~~~bash
/usr/bin/python3 /2024233123/skills/jobs/tests/test_gpu_idle.py -v
~~~

离线测试覆盖空闲判定、单卡/双卡切换、预约抢占和恢复、
worker 自动下一轮、PID 重用拒绝及容器归属检查。

## 实测记录（2026-09-05，北京时间）

- 7 项控制器离线测试及 4 项现有 SABER 沙箱回归测试通过。
- GPU 0 既有 GLM 服务 PID 1795817 全程保持运行；真实抢占只测试 GPU 1。
- 14:50:28 提交 GPU 1 优先任务，14:50:34 Qwen 和所属临时容器已释放，
  正式程序开始前显存实测 1 MiB，随后成功分配 1024 MiB CUDA 张量。
- 14:50:47 正式测试退出；14:51:17 自动重载 Qwen，
  14:52:24 自动恢复 4 个 SABER worker。
- 已修复自动重载时 TCP TIME_WAIT 导致的端口检查误报。
- 双卡切换通过离线状态机测试；当前未抢占 GPU 0 来做双卡现场验证。
