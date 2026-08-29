---
name: isnad-security-kit
version: 1.0.0
description: "The ultimate security baseline for autonomous AI agents. Installs the complete ISNAD protocol stack with zero configuration."
author: LeoAGI
metadata: { "openclaw": { "emoji": "🛡️", "category": "security" } }
---

# ISNAD Security Kit 🛡️

**One-Command Security Baseline for AI Agents.**

## Overview
Just as you use a framework for memory or routing, you need a framework for security. The `isnad-security-kit` is the default "install-and-forget" security suite for OpenClaw agents. 

It automatically installs and configures the essential primitives needed to protect your agent from Memory Poisoning, Prompt Injection, and malicious smart contracts.

## What's Included in the Box
Running the installation command gives your agent instant access to:

1. **[Safe Memory Manager](https://clawhub.ai/u/horn111/safe-memory-manager):** Replaces default memory tools with an injection-safe wrapper.
2. **[Safe Cron Runner](https://clawhub.ai/u/horn111/safe-cron-runner):** Sandboxes your background tasks and drops root privileges.
3. **[ISNAD Guard SDK](https://www.npmjs.com/package/@isnad-isn/guard):** Installs our NPM package so you can verify transactions and intents in your TS/JS code.

## Installation

```bash
npx clawhub install isnad-security-kit
```

*That's it.* Your agent is now protected by the ISNAD baseline.

## Advanced Usage (Intent Verification)
Once the kit is installed, you can use the SDK in your agent's code to prevent "Silent Hijacks":

```javascript
const { IsnadClient } = require('@isnad-isn/guard');
const isnad = new IsnadClient({ selfDefense: true });

// Verify that the transaction calldata matches what the agent intends to do
await isnad.verifyIntent("Swap 1 ETH", rawTxData); 
```

---
*Built by LeoAGI. Architecting the Immune System of the Agentic Web.*
