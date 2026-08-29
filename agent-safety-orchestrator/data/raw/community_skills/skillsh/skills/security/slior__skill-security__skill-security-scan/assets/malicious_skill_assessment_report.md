# Security Assessment Report for Skill: {{ skill_location }}

## Overview

**Assessment Date**: {{ assessment_date }}  
**Analyzer ID**: {{ analyzer_id }}  
**Skill Source**: {{ skill_location }}  
**Total Flags**: {{ total_findings }}  
**High Severity**: {{ count_high }} | **Medium**: {{ count_medium }} | **Low**: {{ count_low }}

## Summary Conclusion

{{ summary_conclusion }}

## Findings

{{ for finding in findings }}
### {{ finding.severity }}: {{ finding.title }}

**Type**: {{ finding.type }}  
**Location**: {{ finding.location }}  
**Evidence**:  
{{ finding.evidence }}

**Description**:  
{{ finding.description }}

**Recommendation**:  
{{ finding.recommendation }}

---

{{ endfor }}

## Permissions and Scope Review

**Declared Permissions**:  
{{ for perm in declared_permissions }}- {{ perm }}
{{ endfor }}

**Actual Behavior vs Declared Scope**:  
{{ permissions_mismatch }}

## Behavioral Pattern Classification

| Pattern Category | Instances Found |
|------------------|-----------------|
| Destructive Actions | {{ pattern_counts.destructive }} |
| Data Exfiltration | {{ pattern_counts.exfiltration }} |
| Credential Exposure | {{ pattern_counts.credential_exposure }} |
| Propagation / Skill Worm Indicators | {{ pattern_counts.propagation }} |
| Persistence / Startup Hooks | {{ pattern_counts.persistence }} |
| Supply Chain Compromise Patterns | {{ pattern_counts.supply_chain }} |

## Suggested Follow-Up Actions

{{ follow_up_actions }}

---

## Definitions (for interpretability)

**Destructive Actions**  
Operations that delete or modify files/data beyond the skill’s stated purpose.

**Data Exfiltration**  
Attempts to read and transmit secrets, credentials, code, or proprietary data externally.

**Credential Exposure**  
Patterns that handle credentials insecurely or expose them in logs, outputs, or network requests.

**Propagation / Skill Worm Indicators**  
Evidence of self-copying, writing to other skill repositories, lateral spread patterns.

**Persistence / Startup Hooks**  
Scheduled tasks, background processes, or install-time logic that persists beyond invocation.

**Supply Chain Compromise Patterns**  
Dynamic loading from untrusted sources, tampered dependencies, code that rewrites manifests.

---

*End of Report*