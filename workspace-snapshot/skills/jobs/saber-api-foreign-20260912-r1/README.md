# SABER overseas API evaluation

GPT gpt-5.6-sol uses APINebula native Responses; claude-opus-5 and gemini-3.8-flash use the authenticated local Responses-to-Chat bridge with their separate APINebula keys. This job never copies the user's Codex auth file.

All three models use the same frozen 716 tasks and the frozen safety-orchestrator bundle. Each has eight disjoint shards, for 24 concurrent sandbox tasks alongside OAS. Each task has a 100-action budget with the native harness's separately bounded skill-support calls, and a 3600-second deadline. Existing task results are skipped by the original harness. Raw results and model skill/hook evidence are preserved.

Containers use the pinned existing osbench-sandbox image, runc, no network, 0.25 CPU, 256 MiB memory and 256 PIDs. Cleanup verifies BOTH the rick-saber-api-foreign-20260912-r1- prefix and exact skilldistill.saber.batch=api-foreign-20260912-r1 label (plus role=sandbox). The OAS authorization is not reused. Files and temporary workspaces are retained. No image/volume/unrelated-resource cleanup is permitted.

Run non-container API and native-harness checks with `./run.sh --preflight`. After explicit lifecycle approval is recorded, launch with `./run.sh`. See plan.json for exact scope. Inference outputs are not safety scores; SABER's rule and LLM judging must be run before reporting HSR/SRR.

After successful inference, each model is judged automatically with the existing shared DeepSeek-V3.2 SiliconFlow judge configuration. Its model catalog entry has been verified. Judge outputs use the frozen task definitions and are stored under the separate judged directory.
