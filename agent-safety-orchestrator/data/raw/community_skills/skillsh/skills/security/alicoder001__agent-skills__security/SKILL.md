---
name: security
description: Security best practices for web applications. Use when handling user input, authentication, or sensitive data. Covers XSS, SQL injection, CSRF, environment variables, and secure coding patterns.
---

# Security Best Practices

> Essential security patterns for web development.

## Instructions

### 1. Environment Variables

```bash
# ✅ .env file (never commit)
DATABASE_URL=postgresql://...
JWT_SECRET=your-secret-key
API_KEY=xxx

# ✅ .gitignore
.env
.env.local
.env.*.local
```

```typescript
// ✅ Access with validation
const dbUrl = process.env.DATABASE_URL;
if (!dbUrl) throw new Error('DATABASE_URL required');
```

### 2. XSS Prevention

```typescript
// ❌ Bad - direct HTML injection
element.innerHTML = userInput;

// ✅ Good - use textContent
element.textContent = userInput;

// ✅ Good - sanitize if HTML needed
import DOMPurify from 'dompurify';
element.innerHTML = DOMPurify.sanitize(userInput);
```

### 3. SQL Injection Prevention

```typescript
// ❌ Bad - string concatenation
const query = `SELECT * FROM users WHERE id = ${userId}`;

// ✅ Good - parameterized queries
const user = await prisma.user.findUnique({
  where: { id: userId }
});

// ✅ Good - prepared statements
const [rows] = await db.execute(
  'SELECT * FROM users WHERE id = ?',
  [userId]
);
```

### 4. Authentication

```typescript
// ✅ Password hashing
import bcrypt from 'bcrypt';

const hash = await bcrypt.hash(password, 12);
const isValid = await bcrypt.compare(password, hash);

// ✅ JWT with expiration
const token = jwt.sign(
  { userId: user.id },
  process.env.JWT_SECRET,
  { expiresIn: '1h' }
);
```

### 5. Input Validation

```typescript
import { z } from 'zod';

const UserSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  age: z.number().min(18).max(120)
});

// Validate before use
const result = UserSchema.safeParse(input);
if (!result.success) {
  throw new Error('Invalid input');
}
```

### 6. HTTPS & Headers

```typescript
// ✅ Security headers
app.use(helmet());

// ✅ CORS configuration
app.use(cors({
  origin: ['https://yourdomain.com'],
  credentials: true
}));
```

### 7. Rate Limiting

```typescript
import rateLimit from 'express-rate-limit';

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit per IP
});

app.use('/api', limiter);
```

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Node.js Security Checklist](https://blog.risingstack.com/node-js-security-checklist/)
