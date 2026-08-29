---
name: mova-compliance-audit
description: Submit documents for AI-powered compliance audit against GDPR, PCI-DSS, ISO 27001, or SOC 2 via MOVA HITL. Trigger when the user uploads a document and mentions compliance, regulation, or audit, asks to validate against a regulatory framework, or says "check GDPR compliance", "run PCI-DSS audit", "validate ISO 27001". Human sign-off is mandatory before any audit report is finalized.
license: MIT-0
metadata: {"openclaw":{"plugin":{"name":"MOVA","installCmd":"openclaw plugins install openclaw-mova"},"dataSentToExternalServices":[{"service":"MOVA API (api.mova-lab.eu)","data":"document URL or ID, organization name, selected regulatory framework, AI findings, human decision, audit metadata"},{"service":"Document OCR connector (read-only)","data":"document content extracted for structure parsing and checklist evaluation"},{"service":"Compliance rules engine connector (read-only)","data":"document structure evaluated against framework-specific rule set"}]}}
---

> **Contract Skill** — A ready-to-use MOVA HITL workflow. Requires the `openclaw-mova` plugin.

# MOVA Compliance Audit

Submit an organization's documents to MOVA for automated regulatory compliance audit — with framework-specific rule matching, a structured findings report, and a mandatory human sign-off gate backed by a tamper-proof audit trail.

## What it does

1. **Document ingestion** — OCR extraction and structure parsing from uploaded file or URL
2. **Rules engine check** — automated evaluation against the selected regulatory framework (GDPR, PCI-DSS, ISO 27001, SOC 2)
3. **Findings report** — checklist with pass/fail items, severity codes, and recommended remediation actions
4. **Human gate** — compliance officer reviews findings and chooses: approve / approve with conditions / reject / request corrections
5. **Audit receipt** — every check, source, and decision is signed, timestamped, and stored in an immutable MOVA audit trail for regulatory inspection

**Mandatory escalation rules enforced by policy:**
- Critical findings present → mandatory human review, cannot auto-approve
- Regulated framework (GDPR, PCI-DSS) → full audit report artifact required
- Rejection or conditions → remediation items must be recorded with reason

## Requirements

**Plugin:** MOVA OpenClaw plugin must be installed in your OpenClaw workspace.

**Data flows:**
- Document URL/ID + org metadata → `api.mova-lab.eu` (MOVA platform, EU-hosted)
- Document content → OCR extraction connector (read-only, no data stored)
- Extracted structure → compliance rules engine (framework-specific, read-only)
- Audit journal → MOVA R2 storage, cryptographically signed
- No data sent to third parties beyond the above

## Demo

**Step 1 — Document submitted for GDPR audit**
![Step 1](screenshots/01-input.jpg)

**Step 2 — AI findings: 3 critical violations, missing DPIA, reject recommended**
![Step 2](screenshots/02-analysis.jpg)

**Step 3 — Audit receipt + signed decision log**
![Step 3](screenshots/03-audit.jpg)

## Quick start

Say "run GDPR compliance audit on this document" and provide a document URL or ID:

```
document_url: https://example.com/privacy-policy.pdf
framework: gdpr
org_name: Acme Corp
```

The agent submits the document, shows the AI findings checklist with pass/fail items and severity, then asks for your compliance decision.

## Why contract execution matters

- **Framework rules are policy, not prompts** — GDPR and PCI-DSS checks trigger mandatory gates that cannot be bypassed by the AI
- **Full checklist traceability** — every pass/fail item is linked to a specific rule ID and source citation
- **Immutable audit trail** — when a regulator asks "who signed off this audit and what did they see?" — the answer is in the system with an exact timestamp
- **EU AI Act / GDPR Article 22 ready** — automated compliance decisions require human oversight, full explainability, and a documented decision chain

## What the user receives

| Output | Description |
|--------|-------------|
| Framework | Selected regulatory standard (GDPR, PCI-DSS, ISO 27001, SOC 2) |
| Checklist score | Pass / fail count per framework section |
| Critical findings | Count and list of critical violations |
| Findings list | Per-item: rule ID, description, severity (critical / high / medium / low) |
| Remediation hints | Recommended corrective actions per finding |
| Recommended action | AI-suggested compliance decision |
| Decision options | approve / approve_with_conditions / reject / request_corrections |
| Audit receipt ID | Permanent signed record of the compliance decision |
| Compact journal | Full event log: ingest → rules check → human decision |

## When to trigger

Activate when the user:
- Uploads a document and mentions compliance, regulation, or audit
- Says "check GDPR compliance", "run PCI-DSS audit", "validate ISO 27001", "SOC 2 check"
- Asks to prepare for a regulatory inspection

**Before starting**, confirm: "Run compliance audit on [document] — framework: [FRAMEWORK]?"

If framework is not specified — ask once: GDPR, PCI-DSS, ISO 27001, or SOC 2.
If document URL is missing — ask once for a direct HTTPS link or document ID.

## Step 1 — Submit document for audit

Call tool `mova_hitl_start_compliance` with:
- `document_url`: direct HTTPS link to the document
- `document_id`: unique identifier (e.g. DOC-2026-001)
- `framework`: one of `gdpr` / `pci_dss` / `iso_27001` / `soc2`
- `org_name`: organization name

## Step 2 — Show findings and decision options

If `status = "waiting_human"` — show the audit findings summary:

```
Document:   document_id
Framework:  FRAMEWORK
Score:      PASS_COUNT / TOTAL_CHECKS passed
Critical:   CRITICAL_COUNT critical findings
Findings:   [list top findings with rule ID and severity]
Recommended action: ACTION ← RECOMMENDED
```

Then ask compliance officer to choose:

| Option | Description |
|---|---|
| `approve` | Sign off audit report as compliant |
| `approve_with_conditions` | Approve with listed remediation items |
| `reject` | Document fails compliance — block processing |
| `request_corrections` | Return document for corrections |

Call tool `mova_hitl_decide` with:
- `contract_id`: from the response above — this is `ctr-cau-xxxxxxxx`, NOT the document ID
- `option`: chosen decision
- `reason`: officer reasoning (required for reject and request_corrections)

## Step 3 — Show audit receipt

Call tool `mova_hitl_audit` with `contract_id`.
Call tool `mova_hitl_audit_compact` with `contract_id` for the full signed event chain.

## Connect your real compliance systems

By default MOVA uses a sandbox mock. To route checks against your live infrastructure, call `mova_list_connectors` with `keyword: "compliance"`.

Relevant connectors:

| Connector ID | What it covers |
|---|---|
| `connector.ocr.document_extract_v1` | Document OCR and structure extraction |
| `connector.compliance.rules_engine_v1` | Framework-specific compliance rule evaluation |

Call `mova_register_connector` with `connector_id`, `endpoint`, optional `auth_header` and `auth_value`.

## Rules

- NEVER make HTTP requests manually
- NEVER invent or simulate compliance results — if a tool call fails, show the exact error
- Use MOVA plugin tools directly — do NOT use exec or shell
- CONTRACT_ID is `ctr-cau-xxxxxxxx` from the mova_hitl_start_compliance response — NOT the document ID
