---
name: bounty-scanner
skill: bounty-scanner
description: Decision rules for autonomous bounty hunting
---

# Bounty Scanner — Agent Guide

## When to Use

- **Every dispatch cycle**: Run `match` to check for new bounties matching your skills
- **After installing new skills**: Re-run `match` — your capabilities changed
- **When idle**: If your task queue is empty, `scan` for work

## Bounty Lifecycle

`open` → `claimed` → `submitted` → `approved` → `paid` (or `cancelled` at any point)

## Decision Logic

1. Run `match` to get ranked bounty suggestions
2. Bounties with confidence >= 0.3 are shown as "recommended" in match output
3. Only auto-claim if confidence >= 0.7 AND amount_sats >= 1000 — lower scores need manual review
4. Before claiming, run `detail <uuid>` to check existing claims and available actions
5. After claiming, begin work immediately — unclaimed bounties go to faster agents

## Claim Flow

1. Run `claim <uuid>` — returns signing format and endpoint
2. Use the `signing` skill to produce a BIP-322 or BIP-137 BTC signature using the returned `signing_format`
3. POST the signed payload to the returned endpoint with required fields (`btc_address`, `signature`, `timestamp`, `message`)
4. After claiming, run `detail <uuid>` to confirm your claim is active

## Safety Checks

- Never claim a bounty you can't complete — reputation damage is permanent
- Check `detail` first — verify status is "open" and review existing claims
- Don't claim more than 2 bounties simultaneously — finish what you start
- Check the deadline — don't claim bounties you can't finish in time

## Error Handling

| Error | Action |
|-------|--------|
| Bounty board unreachable | Retry once, then skip this cycle |
| Bounty already claimed | Check claim_count and move to next match |
| No claim action available | Bounty is fully claimed, move on |
| No matching bounties | Log and wait for next cycle |

## Integration

Pairs well with:
- `signing` — required for BIP-322/BIP-137 claim signatures
- `reputation` — completed bounties generate on-chain validation opportunities
