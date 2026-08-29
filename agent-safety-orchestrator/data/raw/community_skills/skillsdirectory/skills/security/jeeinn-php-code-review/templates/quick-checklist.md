# PHP Code Review Quick Checklist

## Pre-Review Setup
- [ ] Run automated security scanner: `php scripts/php-security-scanner.php [directory]`
- [ ] Check PHP CS Fixer compliance: `vendor/bin/php-cs-fixer fix --dry-run --diff`
- [ ] Run static analysis (PHPStan/Psalm)
- [ ] Verify tests pass

## Security Review ⚡ (5 minutes)
- [ ] No direct `$_GET`/`$_POST` usage in SQL queries
- [ ] All output properly escaped (`htmlspecialchars()`)
- [ ] No `eval()`, `exec()`, `system()` calls
- [ ] File uploads properly validated
- [ ] Authentication/authorization checks present
- [ ] No hardcoded credentials or secrets

## Code Quality Review ⚡ (10 minutes)
- [ ] Methods under 50 lines
- [ ] Classes under 500 lines
- [ ] Proper error handling (try-catch blocks)
- [ ] No magic numbers (use constants)
- [ ] Meaningful variable/method names
- [ ] Single Responsibility Principle followed

## Performance Review ⚡ (5 minutes)
- [ ] No N+1 query problems
- [ ] Database queries use indexes
- [ ] Large datasets are paginated
- [ ] Expensive operations are cached
- [ ] Memory usage is reasonable

## PHP Standards Review ⚡ (5 minutes)
- [ ] PSR-12 formatting compliance
- [ ] Proper type declarations
- [ ] DocBlocks for public methods
- [ ] Namespace declarations correct
- [ ] Use statements properly organized

## Modern PHP Features ⚡ (3 minutes)
- [ ] Using PHP 8+ features where appropriate
- [ ] Typed properties (PHP 7.4+)
- [ ] Union types (PHP 8.0+)
- [ ] Match expressions instead of switch
- [ ] Constructor property promotion

## Final Checks ⚡ (2 minutes)
- [ ] No debug code left (`var_dump`, `die`, `exit`)
- [ ] No commented-out code blocks
- [ ] Error suppression (`@`) usage justified
- [ ] Global variables avoided
- [ ] Dependencies properly injected

---

**Total Review Time**: ~30 minutes  
**Use this for**: Quick reviews, pull requests, pre-deployment checks