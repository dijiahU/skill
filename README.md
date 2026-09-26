# Agent Safety Orchestrator

A safety framework for coding agents, with a shared hook engine and a Router skill.
It includes 95 capability definitions, eight hook matchers, 14 Router references,
and installers for Claude Code and Codex.

## Install

```bash
git clone https://github.com/dijiahU/skill.git
cd skill
./install.sh --host codex
# Or: ./install.sh --host claude
# Or: ./install.sh --host both
```

The hook scripts require Python 3.10 or newer. The installers copy or configure
files for the selected host. Existing host configuration may require a manual
merge; review the installer output. For the manual Claude installation, copy
`skills/safety-router-skill` into the host's skills directory as well.

Claude Code can also install the repository as a plugin:

```text
/plugin marketplace add dijiahU/skill
/plugin install agent-safety-orchestrator@safety-tools
/reload-plugins
```

See [Codex adapter details](adapters/codex/README.md) and
[optional configuration](.env.example).

## How it works

- `hooks/scripts/` checks tool arguments, commands, file edits, tool output,
  sensitive data flow, and task scope. A block returns exit code 2.
- `skills/safety-router-skill/` provides the model-facing Router and its
  archetype references.
- `helpers/` provides health checks and cached vulnerability lookups.
- `adapters/` connects the shared engine to each supported host.

The framework performs static effect checks. Protection depends on the host
invoking hooks and supplying trustworthy observations. Use a sandbox to isolate
executable code and enforce filesystem and network boundaries.

## Recovery and unavailable vulnerability data

- `SAFETY_ORCH_RECOVERY_POLICY=recheck` is the default. After a denial, each new
  action receives the normal checks. Passing actions may continue.
- `SAFETY_ORCH_RECOVERY_POLICY=read-only` restricts recovery to diagnostics;
  `SAFETY_ORCH_MAX_RECOVERY_ACTIONS` defaults to 4.
- `SAFETY_ORCH_CVE_UNAVAILABLE_POLICY=warn` records unavailable vulnerability
  data as unknown. Set `block` to require a successful lookup. Known
  vulnerabilities at or above the configured severity threshold still block.

Full definitions and failure policies are in the
[capability reference](docs/SAFETY_ATOMIC_CAPABILITIES.md).

## Repository layout

```text
.claude-plugin/   Plugin and marketplace manifests
.github/         Framework validation workflow
adapters/        Host bridges, configuration and installers
hooks/           Hook configuration and shared checks
helpers/         Health and vulnerability-cache support
skills/          Router and archetype reference documents
docs/            Capability definitions and deployment policies
scripts/         Capability manifest and reference generators
tests/           Framework unit and regression tests
atoms.json       Generated capability manifest
install.sh       Host installer dispatcher
```

## Development

Run from the repository root; validation uses the Python standard library.
Run the full suite on Linux, as its snapshot fixtures use Linux paths.
macOS path redirection can cause fixture assertions to fail:

```bash
python3 scripts/gen_atom_manifest.py --check
python3 scripts/gen_router_atom_catalog.py --check
python3 scripts/gen_archetype_skill_md.py --check
python3 -m unittest discover -s tests -v
```

To update capabilities, edit `docs/SAFETY_ATOMIC_CAPABILITIES.md` and, if needed,
`scripts/atom_enforcement.py`, then run the three generators without `--check`.
Archetype prose is maintained in `scripts/gen_archetype_skill_md.py`.

## License

[MIT](LICENSE). Original authorship and copyright notices are preserved.
