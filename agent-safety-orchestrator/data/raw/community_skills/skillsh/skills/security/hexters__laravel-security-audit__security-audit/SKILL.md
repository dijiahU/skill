---
name: security-audit
description: Comprehensive security audit for Laravel/PHP projects. Scans for malware, webshells, vulnerable packages, crypto miners, misconfigurations, and applies hardening. Built from real-world incident response experience.
---

# Security Audit Skill for Laravel/PHP Projects

You are a security audit agent. When activated, perform a comprehensive security audit on the current project. Follow each phase in order and report findings clearly.

## Phase 1: Vulnerable Package Detection

Scan `composer.lock` for known vulnerable packages:

```bash
# Check for intervention/image vulnerability (path traversal CVE)
python3 -c "
import json, sys
try:
    with open('composer.lock') as f:
        data = json.load(f)
    vulns = []
    checks = {
        'intervention/image': lambda v: int(v.lstrip('v').split('.')[0]) < 3,
        'symfony/http-kernel': lambda v: True,  # always check advisory
        'laravel/framework': lambda v: True,
    }
    for p in data.get('packages', []):
        if p['name'] in checks:
            ver = p['version'].lstrip('v')
            vulns.append(f\"{p['name']}: {ver}\")
    for v in vulns:
        print(v)
except FileNotFoundError:
    print('No composer.lock found')
"
```

Also run `composer audit` if available.

**Action items:**
- Flag `intervention/image` < v3 as CRITICAL (path traversal, allows reading .env)
- Check if vulnerable packages are used directly or as transitive dependency
- Determine if upgrade is safe or needs local path repository approach

## Phase 2: Malware & Webshell Scanner

Search for malicious files across these locations:

### 2a. PHP files in upload/storage directories (should NOT exist)
```bash
find storage/app/public public/uploads public/images public/storage -name "*.php" -type f 2>/dev/null
```

### 2b. Suspicious file patterns
Search for files with:
- Random 5-character names: `[a-z0-9]{5}.php`
- Known malware names: `stmept`, `guard.sh`, `wp-admin.php`, `wp-cron.php`, `cache.php`, `test.php`, `unzip.php`, `bootstrap.cache.php`, `themes.php`, `menu.php`, `php8.php`
- Binary executables in web directories
- Files with double extensions: `.php.jpg`, `.jpg.php`
- Temporary PHP files: `tmp_*.php`

### 2c. Dangerous code patterns in PHP files
Search app/ and public/ directories for:
```
eval(
base64_decode(
exec(
system(
passthru(
shell_exec(
gzinflate(
str_rot13(
assert(
preg_replace with /e modifier
$_GET/$_POST/$_REQUEST used with eval/exec
create_function(
```

### 2d. Crypto miner detection
```bash
# Check for known miner processes
pgrep -f "xmrig\|stmept\|minerd\|cpuminer" 2>/dev/null

# Check for miner binaries
find . -name "stmept" -o -name "xmrig" -o -name "minerd" 2>/dev/null

# Check for mining pool connections in code
grep -r "supportxmr\|nanopool\|minergate\|coinhive" . --include="*.php" --include="*.sh" --include="*.conf" 2>/dev/null
```

### 2e. Injected .htaccess files
```bash
# Check all .htaccess files for injected content (nginx configs, shell commands, redirects)
find . -name ".htaccess" -exec grep -l "sudo\|nginx\|server_name\|proxy_pass\|RewriteRule.*http" {} \;
```

## Phase 3: Configuration Security Check

### 3a. Storage directory protection
Check if `storage/app/public/.htaccess` exists with PHP execution blocking:
```apache
<FilesMatch "\.(?:php|phtml|phar|php[0-9]|inc)$">
    Order Deny,Allow
    Deny from all
</FilesMatch>
```

**If missing, CREATE IT** - this is the #1 defense against uploaded webshells.

### 3b. Public .htaccess hardening
Check `public/.htaccess` for:
- Block PHP execution in storage/uploads dirs: `RewriteRule ^storage/.*\.php$ - [F,L]`
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`
- Block sensitive file access: `.env`, `.log`, `.sql`, `.bak`

### 3c. File upload security
Search for these risky patterns in Filament/Controller code:
- `editableSvgs(true)` - SVG can contain JavaScript (XSS) and XXE attacks
- `preserveFilenames()` - Original filenames can be manipulated for path traversal
- Missing mime type validation on upload fields
- Missing file extension validation

### 3d. Credential exposure
Check `.env` file types present (DO NOT output actual values):
```bash
grep -E "^[A-Z_]+=." .env | sed 's/=.*/=***/' | grep -iE "key|secret|password|token|mail|sendgrid|aws|stripe|paypal"
```

## Phase 4: Server-Level Checks (if accessible)

### 4a. Web server user
```bash
ps aux | grep -E "nginx|php-fpm|apache" | head -5
```
**CRITICAL if running as root** - web server must run as unprivileged user (www-data/nginx).

### 4b. Sudoers audit
```bash
grep -i "NOPASSWD" /etc/sudoers /etc/sudoers.d/* 2>/dev/null
```
Flag any `NOPASSWD: ALL` entries - especially for `www-data`, `nginx`, or CI users like `gitlab-runner`.

### 4c. Crontab persistence check
```bash
crontab -l 2>/dev/null
crontab -u www-data -l 2>/dev/null
ls -la /etc/cron.d/ /etc/cron.daily/ 2>/dev/null
```

### 4d. Active miner/backdoor processes
```bash
pgrep -a -f "xmrig\|stmept\|minerd\|cryptonight"
netstat -tlnp 2>/dev/null | grep -E ":3333|:4444|:5555|:8888"
```

## Phase 5: Auto-Fix (Apply Hardening)

When confirmed by user, apply these fixes:

### Fix 1: Create storage/.htaccess (SAFE - zero breaking changes)
```apache
<IfModule mod_php.c>
    php_flag engine off
</IfModule>
<IfModule mod_php7.c>
    php_flag engine off
</IfModule>
<IfModule mod_php8.c>
    php_flag engine off
</IfModule>
<FilesMatch "\.(?:php|phtml|phar|php[0-9]|inc)$">
    Order Deny,Allow
    Deny from all
</FilesMatch>
```

### Fix 2: Harden public/.htaccess (SAFE - zero breaking changes)
Add before existing rewrite rules:
```apache
# Block PHP execution in storage/upload directories
RewriteRule ^storage/.*\.php$ - [F,L]
RewriteRule ^uploads/.*\.php$ - [F,L]
RewriteRule ^images/.*\.php$ - [F,L]
```

Add after `</IfModule>`:
```apache
# Security Headers
<IfModule mod_headers.c>
    Header set X-Content-Type-Options "nosniff"
    Header set X-Frame-Options "SAMEORIGIN"
    Header set X-XSS-Protection "1; mode=block"
</IfModule>

# Block access to sensitive files
<FilesMatch "\.(env|log|sql|bak|conf|ini)$">
    Order Deny,Allow
    Deny from all
</FilesMatch>
```

### Fix 3: Generate nginx security config (SAFE - needs manual include)
Create `nginx-security.conf`:
```nginx
location ~ ^/storage/.*\.php$ { deny all; return 403; }
location ~ /\.(env|git|htaccess|htpasswd) { deny all; return 404; }
location ~* \.(sql|bak|log|conf|ini)$ { deny all; return 404; }
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
```

### Fix 4: Vulnerable package mitigation (CHECK for breaking changes)
For packages with breaking changes (e.g., intervention/image v2 → v3):
1. Copy package from `vendor/` to `packages/<vendor>/<package>/`
2. Add path repository to `composer.json`:
```json
{
    "repositories": [{
        "type": "path",
        "url": "packages/<vendor>/<package>",
        "options": { "symlink": true }
    }]
}
```
3. This allows patching the vulnerability locally without breaking API changes

## Report Format

Present findings as:

```
## Security Audit Report - [Project Name]

### CRITICAL
- [Findings that need immediate action]

### HIGH
- [Findings that should be fixed soon]

### MEDIUM
- [Findings to address in next sprint]

### LOW
- [Recommendations for improvement]

### AUTO-FIXED
- [List of hardening applied]

### ACTION ITEMS
1. [ ] Rotate all credentials in .env
2. [ ] Kill any running miner processes
3. [ ] Review sudoers configuration
4. [ ] Deploy .htaccess changes to production
5. [ ] Monitor access logs for 48 hours
```

## Common Attack Chain Reference

Based on real incidents, this is the typical attack flow:

```
1. ENTRY: Path traversal via vulnerable package (e.g., intervention/image v2)
   → Upload PHP webshell to storage/public directory

2. EXECUTION: Web server executes uploaded .php file
   → Because no .htaccess blocks PHP in storage dirs

3. DATA THEFT: Webshell reads .env file
   → Gets DB credentials, API keys (SendGrid, AWS, Stripe, etc.)

4. LATERAL MOVEMENT: Read .env from other projects on same server
   → Shared server = all projects compromised

5. PERSISTENCE: Install crypto miner + cron job
   → guard.sh / wp-admin.php pattern: download xmrig, auto-restart

6. ABUSE: Use stolen API keys
   → Send phishing emails via SendGrid
   → Access cloud resources via AWS keys
```

## Important Notes

- NEVER output actual credential values - only indicate what types exist
- Always ask before applying fixes that could have breaking changes
- Storage .htaccess and public .htaccess hardening are ALWAYS safe to apply
- When in doubt, report and let the user decide
- This skill is designed for defensive security only
