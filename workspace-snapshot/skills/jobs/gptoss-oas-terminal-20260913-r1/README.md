# gpt-oss-120B：OAS 与 Terminal skills 评测

用户授权：本机 GPU 部署，两组均带完整 skills/hooks。

- GPU 0：OAS 原 222 道题排除 38 道不可评分题，共 184 题，100 步、8 并发，DeepSeek 官方 API NPC。
- GPU 1：Terminal-Bench 2.1 固定版本 7131e437，共 89 题、4 并发、每题单次，官方任务超时，最多 1000 次工具尝试。
- 每组先跑 2 道真实验证题，再跑剩余题目。验证题计入总成绩，0 分保留，不挑最高分。
- 两个单卡副本通过 gpu-idle run 分别预约 GPU 0/1；各服务使用已有本地 MXFP4 权重、32K 上下文、8 个序列。OAS 在 22K token 时压缩历史以适应本机上下文。
- OAS 复用原 API 会话明确授权的容器前缀、会话标签与逐阶段清理守卫；Terminal 容器与网络保留，不执行停止/删除。
- 模型推理在本机；OAS 的 NPC 仍产生 DeepSeek API 用量。未启动任何 baseline。
- 各组状态见 state-oas.json / state-terminal.json；部署状态见 lifecycle-oas.json / lifecycle-terminal.json。所有输出写在 skills/jobs 和 skills/results。

## 启动兼容修复

首次与第二次部署在任务开始前退出。第二次诊断捕获到 BF16 logits 矩阵计算的 SIGFPE：继承的 LD_LIBRARY_PATH 将 CUDA 12.1 的 libcublasLt 混入 PyTorch 2.10+cu128。第三次仅为本任务服务进程前置虚拟环境的 cuBLAS 12.8 与 nvjitlink 路径，并在两张卡上验证同类 BF16 计算通过。保留 eager 模式、2048 个批处理 token 与每服务 8 个序列；题目、评分器、skills 和超时未因本次修复改变。

详见 startup-diagnosis.json 和 preflight/*-cuda.json。各次部署日志分别保留，部署失败不算任务评分失败。

只读进度命令：`python3 /srv/benchmark/skills/jobs/gptoss-oas-terminal-20260913-r1/progress.py`。
