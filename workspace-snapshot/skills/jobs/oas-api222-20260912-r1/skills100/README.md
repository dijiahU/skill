# OAS API skills treatment, 100 iterations

Models: GLM-5.1, DeepSeek-V4-Flash, Qwen3.8-27B through SiliconFlow. NPC: deepseek-flash through the official DeepSeek API, non-thinking mode. Credentials are inherited from the private environment file only.

Each model evaluates the same frozen 222 task IDs. GLM starts with two integration tasks; these are excluded from its following 220-task batch. Models run sequentially with up to 128 workers each. Router skill and hooks are both enabled using the pinned v1 adapter image matching this branch. The bundle is frozen in this directory.

Budget: 100 iterations, 3600-second conversation timeout, 4800-second instance timeout, 180-second model request timeout, two model retries, one fake user response. High concurrency containers retain 0.25 CPU and 2 GiB caps. Dataset evaluators are unchanged; malformed scores and partial runs remain separate.

This treatment uses a different step budget and NPC from the earlier baseline. Comparing their aggregate scores does not establish a causal skills improvement. A matched baseline is required for that conclusion.

Container lifecycle remains within the explicitly approved rick-oas-api222-20260912-r1- name prefix AND skilldistill.oas.api_run=oas-api222-20260912-r1 label. Each stage has a unique model-qualified stage label. No images, volumes, files, or unrelated resources are deleted.

Validation: live NPC helper passed; existing NPC tests 2/2; Ruff formatting/lint and pycodestyle passed. Pyright still reports five unresolved imports for editable OpenHands packages; runtime imports and both full integration tasks passed. Initial automatic approval rejection of the mount smoke was resolved after proving the final prefix/label and using the explicit authorized container identity.

Recharge continuation: resume_after_recharge.py retains valid results (20 GLM tasks at restart), retries only unresolved task IDs in separate stages, and writes consolidated per-model summaries with attempt provenance. Structured insufficient-balance errors or a periodic ~60-second minimal provider check trigger admission stop and cleanup of only the affected stage, using the previously authorized OAS prefix and label. Failed/incomplete outputs remain preserved.

Repair1: shared bridge admission serializes detached container creation, caps OAS agents at 96 and reserves 32 IPv4 addresses; each model starts at 32 workers with 16/8 retry levels. Up to 8 offline fallback graders use the same pinned skills image. Exact name/session/stage ownership is verified before bounded cleanup; absent containers do not abort cleanup of remaining targets. All models use six attempts with 30–180 second staggered exponential retry waits. Each model must produce valid scores on two unresolved smoke tasks before bulk recovery. Existing valid zero or nonzero scores are retained; genuine evaluator defects remain separate. Configuration and source hashes are in repair1-plan.json.

CPU validation correction: Repair1 smoke at 0.25 CPU showed 70–86% throttled scheduling periods and 60s PostToolUse timeouts. Repair2 uses 1 CPU per agent, matching the earlier successful skills smoke. Initial Repair2 traces advance through multiple actions without those hook timeouts. Repair2 stage names and updated launch provenance are in repair2-plan.json; previous smoke artifacts remain retained.

Scoring decision: user explicitly excluded 38 tasks with empty/commented graders (unscorable-tasks.json). Report progress against 184 scoreable tasks, retaining the original 222-task inventory and all raw trajectories. Seven content-pinned compatibility repairs retain original checkpoint predicates; unsafe-server-c removes a nonexistent extra checkpoint beyond its one-point rubric and treats an empty/None original result as unsatisfied. Stateless complete histories are regraded without new inference and without duplicated token metrics. Stateful tasks require rerunning their workspace. Partial trajectories, 100-step exhaustion and stuck runs remain separate from valid scores. Qwen repair3 uses 8/4/2 workers; GLM/DeepSeek followups wait for their active repair2 waves.
