---
name: code-review
description: AI-assisted code review for bugs, style, performance, and security issues. Use this skill when reviewing code changes, pull requests, or when asked to check code quality.
---

# 🔍 Code Review Skill

## Checklist

### 1. Correctness
- [ ] Logic errors ตรวจสอบ if/else, loops, conditions
- [ ] Function returns ค่าที่ถูกต้อง
- [ ] Variables ไม่ถูกใช้ก่อน initialize

### 2. Edge Cases
- [ ] Null/undefined handling
- [ ] Empty arrays/strings
- [ ] Boundary values (0, -1, MAX_INT)
- [ ] Race conditions (async)

### 3. Style
- [ ] Naming conventions (camelCase, UPPER_SNAKE)
- [ ] Consistent indentation (2 spaces)
- [ ] No magic numbers
- [ ] Single quotes for strings

### 4. Performance
- [ ] Unnecessary re-renders (React)
- [ ] N+1 queries (Database)
- [ ] Large loops optimization
- [ ] Memory leaks

### 5. Security
- [ ] Input validation
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] Secrets not hardcoded

---

## 🤖 AI-Assisted Review Features

### Auto-Fix Patterns
| Issue | Auto-Fix Command |
|-------|-----------------|
| Lint errors | `npm run lint -- --fix` |
| Unused imports | ESLint auto-fix |
| Formatting | `npx prettier --write .` |
| Type errors | Add type annotations |

### Common Fix Templates
```javascript
// Fix: Missing null check
// Before
const name = user.name;
// After
const name = user?.name ?? 'Unknown';

// Fix: Unhandled promise
// Before
fetchData();
// After
fetchData().catch(console.error);
```

---

## 📝 PR Summary Generator

### Template
```markdown
## Summary
[Brief description of changes]

## Changes
- ✅ Added: [new features]
- 🔧 Modified: [changed files]
- 🗑️ Removed: [deleted files]

## Testing
- [ ] Unit tests pass
- [ ] Manual testing done
- [ ] No breaking changes

## Screenshots (if UI changes)
[Before/After images]
```

### Auto-Generate Summary
```bash
# Generate commit summary
git log --oneline -10

# Generate diff summary
git diff --stat main
```

---

## Review Output Format

### Severity Levels
| Level | Icon | Action Required |
|-------|------|-----------------|
| Critical | 🔴 | Must fix before merge |
| Warning | 🟡 | Should fix, can be deferred |
| Suggestion | 🔵 | Nice to have |
| Praise | 🟢 | Good code! |

### Feedback Format
```markdown
🔴 **Critical**: [file.js:L15]
Issue: SQL injection vulnerability
```javascript
// Current
const query = `SELECT * FROM users WHERE id = '${id}'`;

// Suggested fix
const query = 'SELECT * FROM users WHERE id = $1';
const result = await db.query(query, [id]);
```

---

## Feedback Guidelines

1. **Be specific** - ชี้บรรทัดและอธิบายปัญหา
2. **Suggest fix** - เสนอวิธีแก้ไข code พร้อมใช้
3. **Prioritize** - Critical > Warning > Suggestion
4. **Be constructive** - ชมเมื่อเห็นโค้ดดี
5. **Batch similar issues** - รวมปัญหาที่คล้ายกัน
