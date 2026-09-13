# 轨迹与评分分析

当前公开快照见仓库根目录 `evaluation_artifacts/20260913/README.md`。

快照保留各模型、各条件和各次尝试；失败或中断也是分析样本。历史 SABER/OAS/Terminal 批次与本轮 API 批次分开存储，不能直接混合算分。运行中的文件按导出时已落盘内容收录，完整 JSON 文档未写完时跳过并记入 `skipped.jsonl`。

```bash
# 校验所有分片、归档文件数量、逐文件 SHA-256；不调用模型。
python3 api_benchmarks/analysis/restore_results.py evaluation_artifacts/20260913

# 解压到一个尚不存在的目录；只恢复本轮 OAS。
python3 api_benchmarks/analysis/restore_results.py evaluation_artifacts/20260913 \
  --source oas-api222-20260912-r1 --output /path/to/new-analysis-directory
```

`manifest.json` 给出来源、批次、压缩分片顺序和哈希；`files.jsonl.gz`（gzip 压缩的 JSONL）给出每个原文件的路径、原始字节哈希、脱敏后哈希和修改状态。压缩文件以 `.part0000` 等结尾，同一组按 manifest 顺序拼接后是标准 `.tar.gz`，也可用常规 tar 工具读取。

主要数据格式：

- OAS：`output*.jsonl` 包含任务结果、最终评分和运行错误；`traj_*.json`、实例日志保留对话和执行证据。同一道题可能存在多次尝试，不能按最高分选择。38 道没有可运行评分逻辑的题目应继续单独排除。
- Terminal：每道题的 `result.json`、`agent/native-conversation.json`、`agent/native-metadata.json`、`agent/real-tool-events.json`、`agent/tool-output-*.json`，以及 `verifier/` 下测试日志、CTRF 和 reward。原结果有错误时，`verifier/repair-*` 可能包含只重新评分的记录，应按来源哈希关联，并选择首个有效评分。
- SABER：`raw` / `results` 类目录是模型轨迹；`judged` 类目录是判分结果。实际字段随历史协议版本变化，先检查模型 slug、条件和 harness/judge 配置。

敏感字段与真实凭据已脱敏。运行环境、认证文件、SQLite 缓存、重复技能安装副本、整份工作区快照及大型任务产物不在轨迹归档内；原始本地文件保留。`source_changed_during_read=true` 表示源文件在读取期间仍更新，此快照只能代表已捕获内容。公开快照不是最终榜单。

需要生成新快照时，可运行 `export_results.py --help`。`--secret-file` 只在本地用于识别和替换凭据，文件本身不会打包上传。
