---
name: secrets
version: 2.0.0
description: |
  Manage encrypted local credentials for agent tooling with the `secrets` CLI: add, rotate, list,
  enable, disable, and inspect service integrations without exposing secret values in agent output.
allowed-tools:
  - Bash
  - Read
disable-model-invocation: true
user-invocable: true
argument-hint: "[service or secret-management action]"
arguments:
  - request
when_to_use: |
  Use only when the user explicitly asks to manage credentials, wire secrets into MCP servers or
  agent tooling, or inspect secret-management status. Examples: "/secrets add github", "enable the
  Jira secret", "what credentials are configured?", "rotate the OpenAI secret". Do not use
  proactively.
effort: high
---

<EXTREMELY-IMPORTANT>
This skill touches credential infrastructure.

Non-negotiable rules:
1. Never put secret values in arguments, commands, logs, or chat output.
2. Never use `--reveal`.
3. Treat service names as the reporting surface, not secret contents.
4. Prefer the interactive CLI flows for secret entry or rotation.
5. Report status and enablement, not raw credential material.
</EXTREMELY-IMPORTANT>

# secrets

## Inputs

- `$request`: Service name or management action such as `add`, `rotate`, `enable`, or `status`

## Goal

Use the `secrets` CLI to help the user:

- add or rotate credentials safely
- list configured services
- enable or disable integrations
- inspect vault and integration status without exposing secrets

## Step 0: Resolve the requested action

Determine whether the user wants to:

- add
- remove
- list
- show masked status
- rotate
- enable or disable an integration
- initialize the project setup
- inspect status

If the action is ambiguous, ask before running anything.

**Success criteria**: The exact secret-management action is explicit.

## Step 1: Use the safest command shape

Prefer:

- `secrets add <service>` for new credentials
- `secrets rotate <service>` for updates
- `secrets list` or `secrets status` for inspection
- `secrets enable <service>` or `disable <service>` for integration wiring

Rules:

- never pass the secret value as a CLI argument
- never use `--reveal`
- do not echo or restate entered secret material

**Success criteria**: The command path preserves credential secrecy.

## Step 2: Report non-sensitive results

Report:

- which service was targeted
- whether the action succeeded
- whether the service is enabled or disabled
- any follow-up setup the user still needs

**Success criteria**: The user learns the integration state without any credential leakage.

## Guardrails

- Do not run this skill proactively.
- Do not print or summarize raw secret values.
- Do not use non-interactive secret entry patterns that leak values into shell history.
- Do not assume enabling a service is equivalent to testing it successfully unless the command proved that.

## Output Contract

Report:

1. action performed
2. service targeted
3. masked or status-only result
4. any next setup step required
