# GPT and Gemini Terminal-Bench 2.1 API run

Authorized scope: GPT-5.6 Sol and Gemini 3.8 Flash, 89 tasks each, one full-skills-and-hooks condition, one attempt. Claude and baseline are excluded from this batch.

Each model runs openssl-selfsigned-cert and fix-git as two real integration trials. If both have valid official rewards, real tool activity, router and hook evidence, the controller starts the remaining 87 tasks with four workers. Smoke scores are retained and included in the 89-task total; smoke tasks are never repeated in the full phase.

Official per-task timeouts remain authoritative. The native adapter keeps the existing Terminal configuration of 1000 task-tool attempts and a 65536-token context window; these differ from OAS settings. Images and verifier logic reuse the pinned Terminal-Bench 2.1 installation. No host-Docker cleanup is performed; task resources and files are retained.

GPT uses the APINebula Responses API. Gemini uses the previously validated Responses-to-Chat bridge, bound to localhost with ephemeral authentication. Provider keys come from the existing protected environment and are not written into configs. Personal Codex login is not copied. Gemini request usage is recorded in logs/gemini/bridge-requests.jsonl when supplied by the provider.

State: state-gpt.json and state-gemini.json. Integration evidence: preflight/*-smoke.json. Raw results: /srv/benchmark/skills/results/terminal-api-foreign-20260913-r1/. A state of all tasks attempted does not imply all tasks passed or scored successfully.
