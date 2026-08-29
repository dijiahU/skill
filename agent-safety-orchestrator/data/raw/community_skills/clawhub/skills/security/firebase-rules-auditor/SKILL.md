---
name: firebase-rules-auditor
description: Audit Firebase Security Rules for vulnerabilities, data exposure, performance issues, and best practices across Firestore, Realtime Database, and Storage.
metadata:
  tags: ["firebase", "security", "audit", "firestore", "cloud"]
---

# Firebase Rules Auditor

Audit Firebase Security Rules across Firestore, Realtime Database, and Cloud Storage for vulnerabilities, data exposure risks, performance issues, and best practices. Use when reviewing security rules before deployment, after incidents, or during security audits.

## Usage

```
"Audit my Firestore security rules"
"Check Firebase rules for data exposure"
"Review my Realtime Database rules"
"Are my Storage rules secure?"
```

## How It Works

### 1. Rules Discovery

Locate and parse security rules:

```bash
# Firestore rules
cat firestore.rules 2>/dev/null
# Realtime Database rules  
cat database.rules.json 2>/dev/null
# Storage rules
cat storage.rules 2>/dev/null
# Firebase config
cat firebase.json 2>/dev/null
```

### 2. Vulnerability Scan

**Critical vulnerabilities:**
- **Open read/write**: `allow read, write: if true;` — anyone can read/write everything
- **Missing auth check**: Rules without `request.auth != null`
- **Admin escalation**: User can set their own `admin: true` field
- **Cross-user data access**: No ownership validation on user documents
- **Unrestricted deletion**: Any authenticated user can delete any document

**Data exposure:**
- Sensitive fields readable by other users (email, phone, payment info)
- Collection listing enabled on private data
- Subcollection access not scoped to parent document owner
- Query-based rules that can be bypassed with broad queries

**Write vulnerabilities:**
- Missing field validation (user can write arbitrary fields)
- No data type checking (string where number expected)
- Missing size limits (user can write unlimited data)
- Timestamp manipulation (user sets their own `createdAt`)
- Rate limiting not implemented (rapid-fire writes)

### 3. Firestore-Specific Checks

- `get()` and `exists()` calls count toward read quotas
- Recursive rules with `getAfter()` for atomic operations
- Custom claims vs document-based roles
- Collection group queries and their security implications
- Wildcard document access patterns

### 4. Realtime Database Checks

- `.validate` rules for schema enforcement
- `.indexOn` for query performance
- Cascade rules (parent permissions flow to children)
- Data fan-out pattern security
- Presence system exposure

### 5. Storage Rules

- File type validation (content type checks)
- File size limits
- Path-based access control
- Metadata validation
- Public vs authenticated access patterns

### 6. Performance Review

- Rules that trigger excessive `get()` calls
- Complex conditional logic that increases evaluation time
- Missing indexes for common query patterns
- Rules that prevent efficient querying

## Output

```
## Firebase Security Rules Audit

**Services:** Firestore ✅ | RTDB ❌ (not found) | Storage ✅

### 🔴 Critical Vulnerabilities (3)

1. **Open read on users collection** — firestore.rules:12
   ```
   match /users/{userId} {
     allow read: if request.auth != null;
   ```
   Any authenticated user can read ALL user documents
   → Change to: `allow read: if request.auth.uid == userId;`

2. **No write validation** — firestore.rules:15
   ```
   allow write: if request.auth.uid == userId;
   ```
   User can write ANY fields (including `role: "admin"`)
   → Add field validation: only allow specific fields

3. **Storage allows any file type** — storage.rules:8
   No content type validation — users can upload executables
   → Add: `request.resource.contentType.matches('image/.*')`

### 🟡 Warnings (4)
4. No rate limiting on writes (potential abuse)
5. Collection group query on `comments` bypasses parent checks
6. Timestamp field writable by client (should use serverTimestamp)
7. Missing `.indexOn` for 3 query patterns

### ✅ Good Practices
- Auth check present on all rules
- Custom claims used for admin role
- File size limits on storage (10MB)
- Subcollections properly scoped

### 📋 Recommended Rules
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read: if request.auth.uid == userId
                  || request.auth.token.admin == true;
      allow write: if request.auth.uid == userId
                   && request.resource.data.keys().hasOnly(['name', 'bio', 'avatar'])
                   && request.resource.data.name is string
                   && request.resource.data.name.size() <= 100;
    }
  }
}
```
```
