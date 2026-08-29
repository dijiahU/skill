# API Authentication Guide

Complete guide to implementing authentication in API clients.

---

## Authentication Methods

### API Key Authentication

**When to Use**: Simple services, internal APIs

**Implementation**:
```javascript
const headers = {
  'X-API-Key': process.env.API_KEY
};

fetch('https://api.example.com/data', { headers });
```

**Security**:
- Store key in environment variables
- Never commit to git
- Rotate keys regularly

---

### OAuth 2.0

**When to Use**: Third-party services, user authentication

**Flow**:
1. Redirect user to authorization URL
2. User authorizes
3. Exchange code for access token
4. Use token in requests

**Implementation**: See OAuth 2.0 specification

---

### JWT (JSON Web Tokens)

**When to Use**: Stateless authentication, microservices

**Implementation**:
```javascript
const token = jwt.sign({ userId: 123 }, process.env.JWT_SECRET);

const headers = {
  'Authorization': `Bearer ${token}`
};
```

---

**Last Updated**: October 25, 2025
