# Workspace snapshots for offline hook replay

Set `SABER_WORKSPACE_SNAPSHOT_ARCHIVE` to an absolute, durable results directory in the **host harness environment** before starting a run. For example, use a new directory under `/2024233123/skills/results/<run>/snapshot-archive`. Leave the variable unset to retain the existing transient-only behavior. This setting does not launch a model or execute any recorded command.

Each successful workspace observation optionally archives the actual initialized/current file view and the immutable policy view. Text is UTF-8, gzip-compressed and addressed by SHA-256. Repeated files across observations share a blob. Manifests reference the blobs; observation metadata contains `archive.root` and `archive.manifest_sha256`, plus the `PreToolUse` tool call ID or `Stop` stage. Match by tool call ID; observation index is not a trajectory step number because denied calls also have observations.

The archive contains raw workspace evidence, potentially including benchmark credentials. New blobs/manifests have mode 0600, storage subdirectories mode 0700. Store it with private result artifacts, exclude it from source commits, and do not feed archive contents or ground-truth labels to the model. Model-visible tool output continues through the existing filtering path. No archive body is added to result metadata or trace output.

Restore a specific observation without shell execution:

```python
from pathlib import Path
from harness_adapters.workspace_snapshot_archive import restore_snapshot
snapshot = restore_snapshot(Path(observation['archive']['root']),
                            observation['archive']['manifest_sha256'])
```

Restoration verifies every blob digest and byte length. Concurrent writers synchronize publication. An interrupted/corrupt stored object causes an explicit verification error; it is never silently trusted or overwritten. If archiving is enabled but fails, the observation fails and the action does not proceed through that observation.

This supplies file content evidence, not full OS state: permissions, database effects, command success and model behavior still need their own evidence. Historical records containing only observation counts cannot be upgraded to exact snapshots retroactively. Replay must distinguish direct prevention, prior safe-prefix refusal, output filtering, unknown context, and semantic-label uncertainty.

Validation: `python -m unittest tests.test_workspace_snapshot_archive tests.test_workspace_snapshot`.
