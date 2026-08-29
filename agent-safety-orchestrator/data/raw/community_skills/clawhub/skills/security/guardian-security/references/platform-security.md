# Platform Security — Reference Guide

Stripe security, Gumroad security, API key rotation, and platform-specific
security configurations for Ten Life Creatives.

---

## 1. STRIPE SECURITY

### Stripe Security Checklist
```
API KEY MANAGEMENT:
- [ ] Using sk_live_ for production (not sk_test_ on live transactions)
- [ ] Using sk_test_ for development and testing (never live key in dev)
- [ ] Restricted keys created for specific use cases (not using master key everywhere)
- [ ] Publishable key (pk_live_) only on client-side code
- [ ] Secret key (sk_live_) only in server-side code, never client-side

WEBHOOK SECURITY:
- [ ] Webhook signature verification enabled (using Stripe-Signature header)
- [ ] Webhook secret stored as environment variable
- [ ] Raw request body used for signature verification (not parsed JSON)
- [ ] Webhook endpoint uses HTTPS
- [ ] Replay attacks prevented (check event timestamp)

ACCOUNT SECURITY:
- [ ] Two-factor authentication enabled
- [ ] Login history reviewed periodically
- [ ] No unexpected team members with access
- [ ] Stripe Radar fraud protection configured

MONITORING:
- [ ] Email notifications enabled for new charges, failed payments, disputes
- [ ] Review Stripe Dashboard weekly for unusual activity
```

### Stripe Webhook Signature Verification
```python
import stripe
import hmac
import hashlib
import time

def verify_stripe_webhook(payload: bytes, sig_header: str, secret: str) -> dict:
    """Verify Stripe webhook signature and return parsed event."""
    
    # Parse timestamp from signature header
    elements = {k: v for part in sig_header.split(',') 
                for k, v in [part.split('=', 1)]}
    timestamp = int(elements.get('t', 0))
    
    # Reject if older than 5 minutes (replay attack prevention)
    if abs(time.time() - timestamp) > 300:
        raise ValueError("Webhook timestamp too old")
    
    # Compute expected signature
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    expected_sig = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures (timing-safe)
    received_sigs = elements.get('v1', '').split(' ')
    if not any(hmac.compare_digest(sig, expected_sig) for sig in received_sigs):
        raise ValueError("Webhook signature verification failed")
    
    return stripe.Event.construct_from(
        json.loads(payload),
        stripe.api_key
    )
```

---

## 2. GUMROAD SECURITY

### Gumroad Security Checklist
```
ACCOUNT:
- [ ] Strong, unique password
- [ ] Two-factor authentication enabled
- [ ] Notification emails enabled (new sale, refund request, etc.)
- [ ] Account email is secure and not shared with other services

API ACCESS:
- [ ] Access token stored securely (not in code)
- [ ] Token has minimum required permissions
- [ ] Old/unused tokens revoked

PRODUCT SECURITY:
- [ ] Download links not shared publicly (Gumroad manages this)
- [ ] File versions managed carefully (don't overwrite with wrong file)
- [ ] Product files scanned before upload (no malware in PDFs)
```

---

## 3. API KEY ROTATION SCHEDULE

### TLC Credential Rotation Calendar
```
QUARTERLY (every 90 days):
  HIGH RISK credentials:
  - Stripe Live Secret Key
  - Gumroad Access Token
  - SendGrid API Key
  - GitHub Personal Access Token (if used)

SEMI-ANNUAL (every 180 days):
  MEDIUM RISK credentials:
  - Airtable Personal Access Token
  - Any other platform API keys

TRIGGER-BASED (rotate immediately on):
  - Any credential potentially exposed
  - Team member with access departs
  - Platform security incident
  - Suspicious activity detected
```

---

## 4. PLATFORM INCIDENT MONITORING

### What to Monitor for Security Events
```
STRIPE ALERTS (configure in Dashboard → Settings → Email preferences):
  - New dispute/chargeback created
  - Unusual payment volume
  - Failed payment attempts spike

GUMROAD ALERTS:
  - Monitor for unusual refund patterns
  - Check for duplicate or suspicious purchases

GENERAL PLATFORM MONITORING:
  - Any "new login from unrecognized device" alerts → verify or escalate
  - Any "API key accessed from new IP" alerts → verify or rotate
  - Any platform security advisories → assess and act promptly
```

---

## 5. PLATFORM SECURITY INCIDENTS BY TYPE

### If Stripe Account is Compromised
```
1. Immediately revoke all API keys
2. Change account password
3. Enable/re-enable 2FA
4. Review all recent API activity
5. Check for unauthorized charges or payouts
6. Contact Stripe support
7. Notify Hutch immediately
```

### If Gumroad Account is Compromised
```
1. Change account password immediately
2. Review recent product changes (any unexpected files uploaded?)
3. Review recent sales for suspicious patterns
4. Revoke and regenerate API tokens
5. Notify Hutch
```
