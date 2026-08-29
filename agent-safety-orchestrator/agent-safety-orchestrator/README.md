# 🛡️ Agent Safety Orchestrator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![version](https://img.shields.io/badge/version-1.2.0-blue)
![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2)
![Codex](https://img.shields.io/badge/OpenAI%20Codex-adapter-412991)
![safety atoms](https://img.shields.io/badge/safety%20atoms-95-2ea44f)
![training-free](https://img.shields.io/badge/training--free-✓-success)

**Agent Safety Orchestrator is a safety _meta-skill_ for coding agents.** A model-invoked **Router** — the single entry point — routes to the right **archetype safety check** at each stage of the agent loop (each archetype is a reference doc the Router tells the model to `Read`, bundling several **atomic checks** that together cover the whole attack surface), backed by an always-on **hook layer** that deterministically blocks risky actions before any tool runs. Training-free; installs on Claude Code *and* OpenAI Codex.

Agents that browse the web, run shell commands, install packages, and call MCP tools have a wide attack surface: prompt injection, data exfiltration, supply-chain attacks, destructive commands, secret leaks. Agent Safety Orchestrator covers **95 atomic safety capabilities** across that entire lifecycle: the Router meta-skill routes phase-by-phase to **14 archetype checks** for the model-reasoned atoms, while an always-on hook layer enforces the deterministic ones. No fine-tuning, no model changes, no extra infrastructure.

## ⚡ Quick start

**Claude Code** (plugin):

```text
/plugin marketplace add tychenn/agent-safety-orchestrator
/plugin install agent-safety-orchestrator@safety-tools
/reload-plugins
```

**OpenAI Codex** (or both, or auto-detect) — one installer:

```bash
git clone https://github.com/tychenn/agent-safety-orchestrator
cd agent-safety-orchestrator
./install.sh                 # auto-detect installed agents and install for each
./install.sh --host codex    # Codex only   ·   --host claude   ·   --host both
```

Requires **`python3` ≥ 3.9** on `PATH` (for the hook layer), plus **Claude Code ≥ 2.1.143** and/or **codex-cli ≥ 0.64**. Both layers activate on your next session — nothing else to configure.

## 🎯 What it catches — the agent attack surface

From a pasted AWS key to `rm -rf /`, a typosquatted `npm install`, an SSRF to the cloud-metadata endpoint, or data smuggled out through a DNS tunnel — the **95 atoms** guard **19 threat classes** across **every stage of the agent loop**. Nothing is left unguarded:

> **Stage** ① Input understanding · ② Planning · ③ Tool invocation · ④ Output generation · ⑤ Cross-cutting (always-on)
> **Enforcement** **hook** = deterministic, blocks before execution, model can't bypass · **hybrid** = hook fast-path + model fallback · **skill** = model-reasoned

| Stage | Threat class | Example attack it stops | Atoms | Enforcement |
|:--:|---|---|:--:|---|
| ① | **Prompt injection & jailbreaks** | "ignore previous instructions…"; indirect injection hidden in fetched web/file content; system-prompt extraction | 5 | skill + hybrid |
| ① | **Secrets / PII / credentials in input** | AWS keys, private keys, card numbers (PCI) pasted into the prompt | 5 | hook + hybrid |
| ① | **Ambiguous / destructive intent** | an under-specified or dangerous request acted on without clarifying first | 3 | skill + hook |
| ② | **Excessive tool permission** | the agent reaching for a capability broader than the task needs (least-privilege) | 4 | hook |
| ② | **Task over-reach & scope creep** | the agent expanding past what was asked; autonomy-budget overrun | 4 | skill + hook |
| ② | **Policy-as-code gates** | org rules ("no prod writes", "no PII to third parties") enforced before acting | 2 | hook + hybrid |
| ③ | **Untrusted tools / MCP servers** | tool poisoning, confused-deputy, token pass-through, session hijack, malicious skill loaders | 11 | hook + hybrid |
| ③ | **Dangerous command arguments** | `rm -rf /`, path traversal (`/etc/shadow`), shell / SQL injection, SSRF (`169.254.169.254`) | 8 | hook + hybrid |
| ③ | **Supply-chain attacks** | typosquatted / slopsquatted & hallucinated packages, known CVEs, dependency confusion, malicious postinstall, CI/CD compromise | 8 | hook + hybrid |
| ③ | **Sandbox / filesystem boundary** | writes outside the workspace, unapproved network egress, sandbox escape | 6 | hook |
| ③ | **Vulnerable code the agent writes** | SAST findings, hardcoded secrets, weak crypto, unsafe deserialization | 5 | hook |
| ③ | **Malicious tool / fetch output** | IOC & signature hits, zip-bombs, MIME mismatch, active HTML content | 5 | hook |
| ③ | **Runaway loops / cost & DoS** | unbounded token / request / cost budget, infinite tool loops | 4 | hook + hybrid |
| ④ | **Harmful / policy-violating output** | unsafe code emitted, harmful content, dangerous file writes | 5 | skill + hybrid |
| ④ | **Sensitive output leakage** | PII / secrets / system-prompt text in the response | 4 | hook + hybrid |
| ④ | **Data exfiltration channels** | data smuggled via tool args, DNS tunnels, covert channels | 4 | hook + hybrid |
| ⑤ | **Incident response** | detect & contain an in-flight attack mid-session | 5 | hook + hybrid |
| ⑤ | **Human-in-the-loop escalation** | pause for human approval on high-risk actions | 4 | hook + skill |
| ⑤ | **Tamper-evident audit trail** | every safety decision logged for forensics | 3 | hook |

**Total: 95 atoms · 19 threat classes · 5 lifecycle stages.** Hook-enforced rows block deterministically (`exit 2`) before the action runs, no matter what the model decides; skill/hybrid rows add model reasoning for the semantic threats a regex can't see.

### Mapped to the OWASP LLM Top-10 (2025)

| OWASP LLM risk | Covered | By (threat class above) |
|---|:--:|---|
| **LLM01** Prompt Injection | ✅ | Prompt injection & jailbreaks |
| **LLM02** Sensitive Information Disclosure | ✅ | input secret/PII scan · output redaction · exfiltration detection |
| **LLM03** Supply Chain | ✅ | supply-chain attacks |
| **LLM04** Data & Model Poisoning | ⚪ | out of scope — runtime guard, not model training |
| **LLM05** Improper Output Handling | ✅ | output content policy · code-vulnerability scan |
| **LLM06** Excessive Agency | ✅ | tool permission · task over-reach · tool/MCP trust |
| **LLM07** System-Prompt Leakage | ✅ | sensitive output redaction |
| **LLM08** Vector & Embedding Weaknesses | ⚪ | out of scope — no RAG / vector store in the loop |
| **LLM09** Misinformation | ◐ | output content policy (partial) |
| **LLM10** Unbounded Consumption | ✅ | runaway loops / cost & DoS |

**8 of 10 fully covered.** LLM04 and LLM08 are out of scope *by design* — this package guards an agent's **runtime actions**, not model training or a vector database. Flagged here, not hidden.

## ✨ Why use it

- **Training-free** — pure prompt + hook engineering. Works with any host model (Claude, GPT); nothing to fine-tune or host.
- **Defense in depth** — a deterministic host-layer net *and* a model-reasoning layer. Neither alone is enough; together they cover what the other misses.
- **Phase-aware** — checks are scoped to where they matter: `input-understanding`, `planning`, `tool-invocation`, `output-generation`, `cross-cutting`.
- **Fails loudly, never silently** — network-dependent checks degrade under an explicit `fail_policy` (open-warn / soft-block / closed) and a session-start health banner reports any degraded atom. No silent gaps.
- **Transparent & auditable** — every one of the 95 atoms is documented (definition, scope, signals) in [`docs/SAFETY_ATOMIC_CAPABILITIES.md`](docs/SAFETY_ATOMIC_CAPABILITIES.md). The vocabulary was distilled from 10k+ community safety skills, MCP servers, and standards.

## 🏗️ How it works

At its center is a **meta-skill** — the Router, the single entry point — which orchestrates **95 atomic safety capabilities** through two enforcement layers. On the **skill layer** it routes, phase by phase, to **14 archetype safety checks** (reference docs it tells the model to `Read`), each running its own atomic checks; the **always-on hook layer** enforces the deterministic atoms at the host level, no matter what the model decides.

```
                          user input · tool I/O
                                   │
         ┌─────────────────────────┴──────────────────────────┐
         │                                                     │
   ┌─────▼──────┐  always-on, deterministic            ┌───────▼────────┐  model-invoked
   │ HOOK LAYER │  (exit 2 = block · stdout = warn)     │  SKILL LAYER   │  (router-first hierarchy)
   │            │                                       │                │
   │ 8 matcher  │  UserPromptSubmit · PreToolUse        │ safety-router  │  the only skill; per phase
   │ scripts    │  · PostToolUse · Stop                 │    -skill      │  tells model to Read…
   │ 60 hook +  │                                       │ 14 archetype   │  …14 archetype docs
   │ 21 hybrid  │ ◄────── shared 95-atom vocab ───────► │ docs (14 skill │  (refs, not skills)
   │            │                                       │ + 21 hybrid)   │
   └────────────┘                                       └────────────────┘
```

- **Hook layer** — 8 Python matchers wired into Claude Code's hook events. They run on every prompt and tool call, fan ~8 atom checks into a single process, and block/warn *before* the action. Always on; the model cannot bypass them.
- **Skill layer** — one meta-skill (`safety-router-skill`) is the *only* host-registered skill, read at session start. At each execution phase it routes the agent to the relevant archetype docs by telling it to `Read references/archetypes/<name>.md` (e.g. `detect-prompt-injection` on input, `detect-data-exfiltration` on output). The archetypes are **not** independently-invocable skills, so every check necessarily flows **router-first**; only the Router's description costs session-start tokens (~2k, vs ~19k if all 14 were preloaded), and the archetype bodies load only when the Router routes you to `Read` them.

**The structure is three tiers (a strict hierarchy):**

```
safety-router-skill              ×1    the only top-level skill — routes by execution phase
└── references/archetypes/<n>.md ×14   reference docs the Router tells you to Read
       └── atom                        the granular checks living inside an archetype
```

An **archetype** *bundles several atoms* (e.g. `detect-supply-chain-risk` → typosquat · CVE · dependency-confusion · malicious-postinstall · hallucinated-package · …). **Atoms are not standalone skills** — they're the checks *inside* an archetype doc, or, for the deterministic ones, host hooks. In all there are **95 atoms under 19 archetype groupings**: **14 ship as router-routed reference docs** the model `Read`s; the other **5 are hook-only** (no doc — their atoms run directly on the always-on hook layer, never through the Router).

## 📊 Coverage at a glance

| | |
|---|---:|
| Safety atoms | **95** |
| Archetypes | **19** (14 model-invoked + 5 pure-hook) |
| Execution phases | **5** |
| Enforcement split | **60 hook · 21 hybrid · 14 skill** |
| Ship size | 15 `SKILL.md` + 8 hook matchers + 2 helpers |

Full per-atom reference (definitions, scope, `fail_policy`, packaging): [`docs/SAFETY_ATOMIC_CAPABILITIES.md`](docs/SAFETY_ATOMIC_CAPABILITIES.md).

## 📦 Installation

One safety core, two hosts. The repo-root `./install.sh` is a **dispatcher** — it detects which agents you have and installs the same atoms onto each (`--host claude | codex | both | auto`). Per-host details:

### Claude Code

**Recommended — plugin** (installs both layers at once; hook paths resolve via `${CLAUDE_PLUGIN_ROOT}`, so it's relocatable and survives updates):

```text
/plugin marketplace add tychenn/agent-safety-orchestrator
/plugin install agent-safety-orchestrator@safety-tools
/reload-plugins
```

<details>
<summary><b>Manual install</b> (no marketplace — e.g. air-gapped, or wiring hooks straight into <code>settings.json</code>)</summary>

```bash
git clone https://github.com/tychenn/agent-safety-orchestrator
cd agent-safety-orchestrator
./install.sh --host claude         # render hooks.json → merge into ~/.claude/settings.json + health banner
```

It validates Python ≥ 3.9, substitutes `${CLAUDE_PLUGIN_ROOT}` in `hooks/hooks.json` with the repo's absolute path, and merges the `hooks` block into your settings. Copy `skills/*` into `~/.claude/skills/` (or a project `.claude/skills/`) to enable the skill layer.
</details>

### OpenAI Codex

```bash
./install.sh --host codex                          # into ~/.codex
CODEX_HOME=/tmp/codex-test ./install.sh --host codex   # isolated trial (touches nothing real)
```

A thin **bridge** (`adapters/codex/codex_hook.py`) translates Codex hook events into the **same** matcher core and returns Codex's `permissionDecision: deny` / `exit 2` — so the hook layer is deterministic on Codex too. The installer is safe (never overwrites your `hooks.json`/`config.toml`; writes a sidecar to merge). Codex's `PreToolUse` can't intercept every channel (`unified_exec` streaming shell, `WebSearch`), so back the network/filesystem atoms with the sandbox + approvals in [`adapters/codex/config.backstop.toml`](adapters/codex/README.md). Details: **[adapters/codex/README.md](adapters/codex/README.md)**.

## ⚙️ Configuration (`.env`)

Optional — see [`.env.example`](.env.example). **Tier 0 (zero config)** already covers ~52 pure-local hooks + 3 keyless public-API atoms (osv.dev, npm, PyPI). **Tier 1** (one `.env`) adds VirusTotal hash lookup, internal-registry detection, and online skill-signature revocation. **Tier 2** (air-gap) points endpoints at internal mirrors.

## 🚦 fail_policy — degradation semantics

When a network-dependent check can't reach its source, the atom's declared policy fires automatically, and `helpers/health_status.py` logs it so degradation is never silent:

- `fail-open-warn` — log + proceed (low-stakes informational checks)
- `fail-soft-block` — block unless the user explicitly overrides (high-stakes; e.g. CVE)
- `fail-closed` — block, no override (signature failure, dependency confusion)

## 📂 What's inside

```
install.sh        unified installer / dispatcher (--host claude | codex | both | auto)
.claude-plugin/   plugin.json + marketplace.json (this repo is its own marketplace)
skills/           safety-router-skill/ — the ONE top-level skill            ← shared core
                    └ SKILL.md + references/archetypes/×14 + references/atoms-catalog.md
hooks/            hooks.json   + scripts/ (8 matchers + lib_common)           ← shared core
helpers/          cache_snapshot.py (offline CVE cache) + health_status.py (banner)
atoms.json        machine-readable atom metadata (id / phase / enforcement_mode / …)
adapters/         per-host adapters that reuse the shared core
  claude/         manual (non-marketplace) Claude Code installer
  codex/          Codex hook bridge + backstop config + installer
docs/             SAFETY_ATOMIC_CAPABILITIES.md — the 95-atom vocabulary reference
```

## 🤝 Contributing & license

Issues and PRs welcome. Licensed under the **MIT License** — see [LICENSE](LICENSE).

MIT © 2026 [tychen](https://github.com/tychenn)
