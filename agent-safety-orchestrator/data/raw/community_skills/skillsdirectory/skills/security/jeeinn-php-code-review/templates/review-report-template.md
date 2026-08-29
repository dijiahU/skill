# PHP Code Review Report

**Project**: [Project Name]  
**Reviewer**: [Reviewer Name]  
**Date**: [Review Date]  
**Files Reviewed**: [Number of files]  
**PHP Version**: [Target PHP Version]

## Executive Summary

[Brief overview of the code quality and main findings]

## Critical Issues (Must Fix) 🔴

- [ ] **[Issue Title]**
  - **File**: `path/to/file.php:line`
  - **Description**: [Detailed description]
  - **Impact**: [Security/Performance/Functionality impact]
  - **Recommendation**: [Specific fix recommendation]
  - **Priority**: Critical

## Standards Violations (Should Fix) 🟡

- [ ] **[Issue Title]**
  - **File**: `path/to/file.php:line`
  - **Description**: [Description of standards violation]
  - **Standard**: [PSR-12/Security/Performance]
  - **Recommendation**: [How to fix]
  - **Priority**: High

## Improvements (Nice to Have) 🟢

- [ ] **[Improvement Title]**
  - **File**: `path/to/file.php:line`
  - **Description**: [Description of potential improvement]
  - **Benefit**: [Expected benefit]
  - **Recommendation**: [Suggested improvement]
  - **Priority**: Medium

## Security Assessment 🔒

### Vulnerabilities Found
- [List of security issues with severity levels]

### Security Score: [X/10]
- **SQL Injection**: ✅ Protected / ❌ Vulnerable
- **XSS Prevention**: ✅ Protected / ❌ Vulnerable  
- **Input Validation**: ✅ Adequate / ❌ Insufficient
- **Authentication**: ✅ Secure / ❌ Weak
- **Authorization**: ✅ Proper / ❌ Missing

## Performance Analysis ⚡

### Performance Score: [X/10]
- **Database Queries**: [Optimized/N+1 Issues/Inefficient]
- **Memory Usage**: [Efficient/Moderate/High]
- **Caching**: [Implemented/Partial/Missing]
- **Algorithm Efficiency**: [Optimal/Good/Poor]

## PHP Compatibility 🐘

### PHP Version Compatibility
- **Minimum PHP Version**: [7.4/8.0/8.1/8.2]
- **Deprecated Features**: [List any deprecated features used]
- **Modern Features**: [List modern PHP features that could be adopted]

## Code Quality Metrics 📊

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Cyclomatic Complexity | [X] | <10 | ✅/❌ |
| Code Coverage | [X%] | >80% | ✅/❌ |
| Technical Debt | [X hours] | <40h | ✅/❌ |
| Maintainability Index | [X] | >70 | ✅/❌ |

## Recommendations Summary

### Immediate Actions (Next Sprint)
1. [Priority 1 action]
2. [Priority 2 action]
3. [Priority 3 action]

### Medium-term Improvements (Next Quarter)
1. [Medium-term improvement 1]
2. [Medium-term improvement 2]

### Long-term Considerations
1. [Long-term consideration 1]
2. [Long-term consideration 2]

## Tools Used

- [ ] Manual Code Review
- [ ] PHP Security Scanner (`scripts/php-security-scanner.php`)
- [ ] PHP CS Fixer (PSR-12 compliance)
- [ ] PHPStan/Psalm (Static Analysis)
- [ ] Custom Security Checklist

## Next Steps

1. **Developer Actions**: [What the development team should do]
2. **Follow-up Review**: [When to schedule next review]
3. **Monitoring**: [What to monitor going forward]

---

**Review Completed**: [Date]  
**Estimated Fix Time**: [X hours/days]  
**Risk Level**: [Low/Medium/High/Critical]