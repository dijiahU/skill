# 2026-09-13 评测轨迹快照

本快照收录 163,820 个分析文件、201 组归档，压缩数据共 966.2 MiB。覆盖本机已有模型、baseline / skills 条件、成功、失败、中断及重试记录。

采集窗口（UTC）：2026-09-13T12:06:46.145249+00:00 至 2026-09-13T12:23:59.248540+00:00。运行中的任务只收录已落盘内容；各文件读取时间不同，不是原子快照，也不表示全部评测已完成。

- [当前评分汇总](summary/评测结果汇总.md)：汇总的采集时间以报告自身为准，有效完成数不等于得分。
- [归档批次索引](archive-index.csv)：按来源、模型/批次分组查看文件数和大小。
- [完整分片清单](manifest.json)、[逐文件来源与哈希](files.jsonl.gz)、[跳过记录](skipped.jsonl)。
- [格式及恢复说明](../../api_benchmarks/analysis/README.md)。

## 下载和恢复

克隆本分支后，在仓库根目录执行。以下操作不调用模型 API：

```bash
python3 api_benchmarks/analysis/restore_results.py evaluation_artifacts/20260913
python3 api_benchmarks/analysis/restore_results.py evaluation_artifacts/20260913 \
  --source oas-api222-20260912-r1 --output /path/to/new-analysis-directory
```

默认仅校验；指定 `--output` 时恢复到新目录。每个 gzip/tar 归档最多按 4 MiB 分片，恢复工具依据 manifest 顺序拼接并校验分片及逐文件 SHA-256。

## 来源覆盖

| 来源 | 归档组 | 文件 | 压缩 MiB |
| --- | ---: | ---: | ---: |
| `oas-api222-20260912-r1` | 47 | 11,228 | 237.0 |
| `openagentsafety` | 10 | 29,764 | 462.2 |
| `saber-api-foreign-20260912-r1` | 0 | 0 | 0.0 |
| `saber-source-judged` | 4 | 2,868 | 1.6 |
| `saber-source-judged_deepseek_v4_flash` | 25 | 8,376 | 2.8 |
| `saber-source-results` | 30 | 8,937 | 113.5 |
| `saber-v10-count-diagnostic-r2` | 1 | 3 | 0.0 |
| `saber-v10-hooks-deepseek_flash-20260908-r1` | 0 | 0 | 0.0 |
| `saber-v10-hooks-glm-20260908-r1` | 0 | 0 | 0.0 |
| `saber-v10-hooks-gptoss-20260908-r1` | 0 | 0 | 0.0 |
| `saber-v10-hooks-minimax-20260908-r1` | 0 | 0 | 0.0 |
| `saber-v10-hooks-mistral-20260908-r1` | 6 | 1,450 | 35.4 |
| `saber-v10-paired-20260906-r1` | 0 | 0 | 0.0 |
| `saber-v10-paired-20260906-r2` | 0 | 0 | 0.0 |
| `saber-v10-paired-20260906-r3` | 0 | 0 | 0.0 |
| `saber-v10-paired-20260906-r4` | 0 | 0 | 0.0 |
| `saber-v10-paired-20260906-r5` | 0 | 0 | 0.0 |
| `saber-v10-paired-20260906-r6` | 0 | 0 | 0.0 |
| `saber-v10-paired-20260906-r7` | 1 | 52 | 0.2 |
| `saber-v10-paired-20260906-r8` | 0 | 0 | 0.0 |
| `saber-v10-paired-20260907-r1` | 1 | 52 | 0.2 |
| `saber-v10-paired-20260907-r2` | 1 | 52 | 0.2 |
| `saber-v10-paired-20260907-r3` | 10 | 520 | 2.9 |
| `saber-v10-paired-20260907-r4` | 10 | 520 | 2.4 |
| `saber-v9-full-20260905-r1` | 2 | 17,080 | 16.3 |
| `terminal-api-foreign-20260913-r1` | 11 | 10,968 | 19.4 |
| `terminal-bench` | 37 | 67,816 | 67.7 |
| `terminal-gptoss-skills-20260913-r1` | 5 | 4,134 | 4.1 |

## 分析口径与限制

- 历史协议、不同 benchmark 版本、条件和重试批次保持独立。不要把所有文件合并计算一个分数，也不要挑选重试中的最高分。
- OAS 的 38 道没有可运行评分逻辑的任务继续标记为不可评分，不计入现有分母；具体结果采用汇总文档说明的有效性判定。
- `saber-api-foreign-20260912-r1` 没有找到结果目录，未将计划或配置视为完成结果。表中 0 文件来源同样没有可收录的分析记录。
- 凭据、敏感字段已脱敏；基准中的合成密码等也可能被替换。原始本地记录保留，哈希可用于核对来源。
- 不包含认证文件、运行缓存、重复安装副本、完整工作区快照、二进制文件或大型任务产物。此处提供轨迹及评分分析材料，不能保证完整重放每个运行环境。
- 未写完的 JSON 文档及无效 JSONL 行记入跳过记录；`source_changed_during_read=true` 标记读取期间仍更新的文件。

## 完整性检查

163,820 个文件及所有压缩分片的 SHA-256、大小和路径检查通过；凭据按 JSON 字段及日志内容检查。详见 [校验报告](verification.json) 和 [下载文件校验和](SHA256SUMS)。

## 公开副本中的部署信息

内网 IPv4 地址已替换为稳定的 `private-host-<哈希前缀>.invalid` 名称，服务器根目录使用 `/srv/benchmark` 和 `/srv/benchmark-host` 占位值。部署配置改为需要自行填写的模板。本机原始记录未修改；公开副本用于分析，重放前需配置自己的环境。

共有 38,172 个归档文件发生部署信息替换。题目归属、数值评分、成功/失败和重试记录保留。`source_sha256` 对应原始文件，`previous_export_sha256` 对应仅凭据脱敏的本地快照，`export_sha256` 对应本次公开文件。

代码中需要数值 CIDR 的位置使用保留的示例网段以维持解析；通过 `TERMINAL_BENCH_NETWORK_POOL` 和 `TERMINAL_BENCH_NETWORK_STATE_DIR` 配置实际网段和分配状态目录。
