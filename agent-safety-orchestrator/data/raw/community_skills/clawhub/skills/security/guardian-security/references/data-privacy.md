# Data Privacy — Reference Guide

What data is stored, who can access it, PII handling, and the privacy standards
that protect customers and keep the company compliant.

---

## 1. DATA CLASSIFICATION

### What Data We Handle
```
TIER 1 — HIGHLY SENSITIVE (protect most strictly):
  Customer payment information: Stripe handles this; we never see full card numbers
  Customer email addresses: PII, can be used to identify individuals
  Customer purchase history: Linked to identity + purchase behavior
  
TIER 2 — SENSITIVE (protect carefully):
  Order amounts and products purchased
  Download link status and access
  Any names provided at checkout
  
TIER 3 — INTERNAL (protect from public):
  Business metrics, revenue figures
  Product pricing strategies
  Marketing copy and product roadmaps
  
TIER 4 — PUBLIC (already public):
  Product descriptions
  Published prices
  Our public profile information
```

---

## 2. PII HANDLING RULES

### What Constitutes PII
```
PII (Personally Identifiable Information):
  - Name
  - Email address
  - Phone number
  - Physical address
  - IP address
  - Any combination that identifies a person

SPECIAL PII (higher protection):
  - Financial data
  - Health information
  - Religious beliefs
  - Government IDs
```

### PII Handling Protocol
```
COLLECTION: Only collect what you need
  Don't collect data "just in case"
  If Gumroad provides it and we don't need it: don't store it

STORAGE: Protect all stored PII
  Don't store in plain text files without protection
  Don't store in public repositories
  Minimum: store only in platforms with proper security
  
ACCESS: Limit who can see PII
  Not all agents need customer email lists
  Airtable CRM: use column-level permissions if available
  
RETENTION: Don't keep PII forever
  Clear old customer data that's no longer needed for service
  
LOGGING: Never log PII
  Customer emails, names, addresses → never in application logs
```

---

## 3. PLATFORM DATA HANDLING

### Stripe
```
- Stripe handles all payment card data (PCI compliant)
- We never see full card numbers (only last 4 digits)
- Customer email may appear in payment metadata
- Webhook events contain customer data → handle securely
```

### Gumroad
```
- Stores customer purchase data, email, IP
- Webhook events include customer email → treat as PII
- Don't export and store customer lists without need
```

### Airtable
```
- Our CRM: may contain customer contact info
- Treat all Airtable records containing name/email as PII
- Don't share Airtable base publicly
```

---

## 4. PRIVACY CHECKLIST

```
DATA WE HOLD:
- [ ] Do we know what PII we have and where it lives?
- [ ] Is it stored only where necessary?
- [ ] Access limited to who needs it?

DATA WE COLLECT:
- [ ] Are we collecting only what we need?
- [ ] Is there a legitimate reason for each data point?

DATA WE PROCESS:
- [ ] PII never in logs?
- [ ] PII never in error messages?
- [ ] Webhook data with PII handled securely?

DATA WE SHARE:
- [ ] Customer data not shared with unauthorized third parties?
- [ ] Any data sharing disclosed in privacy policy?
```

---

## 5. PRIVACY POLICY BASICS

### Minimum Privacy Policy Requirements
If we have a website that collects any data:
```
MUST DISCLOSE:
  - What data we collect
  - How we use it
  - Who we share it with (payment processors, email service)
  - How to contact us for data requests
  - How long we keep data

PLATFORMS THAT REQUIRE PRIVACY POLICY:
  - Google (if using Google Analytics)
  - Apple App Store (Prayful app)
  - Any form that collects email addresses

GDPR NOTE: If any European users purchase from us:
  - We technically need GDPR compliance
  - At minimum: unsubscribe works, don't send unsolicited email
  - Practical: treat all customer data with European privacy standards
```
