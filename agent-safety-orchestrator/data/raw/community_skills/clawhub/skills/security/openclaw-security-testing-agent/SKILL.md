---
name: openclaw-security-testing-agent
description: "安全测试Agent。漏洞扫描、渗透测试、代码审计、安全加固。触发词：安全、渗透、漏洞、xss、sql注入、csrf、扫描、审计。"
metadata: {"openclaw": {"emoji": "🔒"}}
---

# Security Testing Agent

## 功能说明

AI驱动的安全测试和漏洞扫描助手。

## 安全测试类型

| 类型 | 工具 | 覆盖 |
|------|------|------|
| 静态扫描 | SonarQube, Semgrep, CodeQL | SAST |
| 动态扫描 | OWASP ZAP, BurpSuite | DAST |
| 依赖扫描 | Snyk, Dependabot, npm audit | SCA |
| 秘钥扫描 | TruffleHog, git-secrets | 秘钥泄露 |
| 容器扫描 | Trivy, Clair | 镜像安全 |

## 1. 漏洞扫描框架

```python
from dataclasses import dataclass
from typing import Optional
import requests

@dataclass
class Vulnerability:
    id: str
    severity: str  # critical, high, medium, low
    title: str
    description: str
    affected: str
    remediation: str
    cwe: Optional[str] = None
    cvss: Optional[float] = None

class VulnerabilityScanner:
    def __init__(self, target_url: str, api_key: Optional[str] = None):
        self.target = target_url.rstrip('/')
        self.session = requests.Session()
        if api_key:
            self.session.headers['Authorization'] = f'Bearer {api_key}'
    
    # === SQL注入检测 ===
    def test_sql_injection(self) -> list[Vulnerability]:
        vulns = []
        test_payloads = [
            "' OR '1'='1",
            "' OR 1=1--",
            "'; DROP TABLE users--",
            "1' AND '1'='1",
            "admin'--",
            "' UNION SELECT NULL--",
        ]
        
        # 测试URL参数
        params_to_test = ['id', 'user', 'page', 'q', 'search', 'query', 'id', 'cat', 'category']
        
        for param in params_to_test:
            url = f"{self.target}/?{param}=1"
            for payload in test_payloads:
                test_url = f"{self.target}/?{param}={payload}"
                
                try:
                    resp = self.session.get(test_url, timeout=10)
                    
                    # 检测SQL错误
                    sql_errors = [
                        'mysql_fetch', 'mysqli_', 'sqlite_', 'postgresql',
                        'ORA-', 'Microsoft SQL Server', 'ODBC',
                        'SQLite', 'Syntax error', 'Warning: pg_'
                    ]
                    
                    for error in sql_errors:
                        if error.lower() in resp.text.lower():
                            vulns.append(Vulnerability(
                                id='SQLI-001',
                                severity='critical',
                                title=f'SQL Injection - {param}',
                                description=f'Parameter {param} is vulnerable to SQL injection',
                                affected=f'{self.target}/?{param}={payload}',
                                remediation='Use parameterized queries, ORM, or prepared statements',
                                cwe='CWE-89'
                            ))
                            break
                    
                    # 时间盲注检测
                    if 'SLEEP' in payload or 'BENCHMARK' in payload:
                        import time
                        start = time.time()
                        self.session.get(test_url, timeout=30)
                        elapsed = time.time() - start
                        if elapsed > 10:
                            vulns.append(Vulnerability(
                                id='SQLI-002',
                                severity='critical',
                                title=f'Blind SQL Injection - {param}',
                                description='Time-based blind SQL injection detected',
                                affected=f'{self.target}/?{param}={payload}',
                                remediation='Same as SQL injection',
                                cwe='CWE-89'
                            ))
                    
                except requests.RequestException:
                    continue
        
        return vulns
    
    # === XSS检测 ===
    def test_xss(self) -> list[Vulnerability]:
        vulns = []
        xss_payloads = [
            '<script>alert(1)</script>',
            '<img src=x onerror=alert(1)>',
            '<svg onload=alert(1)>',
            '"><script>alert(1)</script>',
            "javascript:alert(1)",
            '<body onload=alert(1)>',
        ]
        
        # 测试输入点
        test_points = [
            ('GET', '/search?q=test'),
            ('POST', '/contact', {'name': 'test', 'email': 'test@test.com', 'message': 'test'}),
        ]
        
        for method, path, *params in test_points:
            for payload in xss_payloads:
                try:
                    if method == 'GET':
                        test_path = path.replace('test', payload)
                        resp = self.session.get(f"{self.target}{test_path}", timeout=10)
                    else:
                        data = params[0] if params else {}
                        resp = self.session.post(f"{self.target}{path}", data=data, timeout=10)
                    
                    # 检查payload是否反射
                    if payload in resp.text:
                        vulns.append(Vulnerability(
                            id='XSS-001',
                            severity='high',
                            title=f'Cross-Site Scripting in {path}',
                            description=f'User input is reflected without sanitization',
                            affected=f'{self.target}{path}',
                            remediation='Escape HTML entities, use Content-Security-Policy',
                            cwe='CWE-79'
                        ))
                        break
                    
                    # 检查存储型XSS
                    if 'stored' in path or 'comment' in path or 'post' in path:
                        check_resp = self.session.get(f"{self.target}{path}")
                        if payload in check_resp.text:
                            vulns.append(Vulnerability(
                                id='XSS-002',
                                severity='critical',
                                title=f'Stored XSS in {path}',
                                description='Malicious script is stored and executed for all users',
                                affected=f'{self.target}{path}',
                                remediation='Strict input validation and output encoding',
                                cwe='CWE-79'
                            ))
                
                except requests.RequestException:
                    continue
        
        return vulns
    
    # === CSRF检测 ===
    def test_csrf(self) -> list[Vulnerability]:
        vulns = []
        
        # 查找敏感表单
        sensitive_forms = [
            '/profile/update', '/password/change', '/admin/settings',
            '/api/user/delete', '/payment/submit', '/settings/security'
        ]
        
        for path in sensitive_forms:
            try:
                resp = self.session.get(f"{self.target}{path}", timeout=10)
                
                # 检查是否有CSRF token
                csrf_patterns = [
                    'csrf', 'xsrf', '_token', 'token', 'nonce', 'csrf_token'
                ]
                
                has_csrf_protection = any(p in resp.text.lower() for p in csrf_patterns)
                
                if not has_csrf_protection:
                    vulns.append(Vulnerability(
                        id='CSRF-001',
                        severity='medium',
                        title=f'CSRF Vulnerability in {path}',
                        description='Sensitive action lacks CSRF protection',
                        affected=f'{self.target}{path}',
                        remediation='Implement CSRF tokens or SameSite cookies',
                        cwe='CWE-352'
                    ))
            
            except requests.RequestException:
                continue
        
        return vulns
    
    # === 头部安全检测 ===
    def check_security_headers(self) -> list[Vulnerability]:
        vulns = []
        expected_headers = {
            'Strict-Transport-Security': 'Enforce HTTPS',
            'Content-Security-Policy': 'Prevent XSS/injection',
            'X-Content-Type-Options': 'Prevent MIME sniffing',
            'X-Frame-Options': 'Prevent clickjacking',
            'X-XSS-Protection': 'Legacy XSS filter (deprecated)',
            'Referrer-Policy': 'Control referrer information',
            'Permissions-Policy': 'Control browser features',
        }
        
        resp = self.session.get(self.target, timeout=10)
        
        for header, description in expected_headers.items():
            if header not in resp.headers:
                severity = 'medium' if 'Content-Security-Policy' in header else 'low'
                vulns.append(Vulnerability(
                    id='HEADER-001',
                    severity=severity,
                    title=f'Missing {header}',
                    description=description,
                    affected=self.target,
                    remediation=f'Add {header} header',
                    cwe=None
                ))
        
        return vulns
    
    # === 完整扫描 ===
    def full_scan(self) -> dict:
        print(f"Scanning {self.target}...")
        
        results = {
            'target': self.target,
            'vulnerabilities': [],
            'summary': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        }
        
        # 执行所有测试
        all_vulns = []
        all_vulns.extend(self.test_sql_injection())
        all_vulns.extend(self.test_xss())
        all_vulns.extend(self.test_csrf())
        all_vulns.extend(self.check_security_headers())
        
        # 去重
        seen = set()
        for v in all_vulns:
            key = f"{v.id}-{v.title}"
            if key not in seen:
                seen.add(key)
                results['vulnerabilities'].append(v)
                results['summary'][v.severity] += 1
        
        return results
```

## 2. 依赖安全扫描

```python
import json
import subprocess
from packaging import version

class DependencyScanner:
    def __init__(self):
        self.vulnerabilities_db = self.load_nvd()
    
    def scan_npm(self, package_json_path: str = 'package.json') -> list:
        """扫描npm依赖"""
        with open(package_json_path) as f:
            pkg = json.load(f)
        
        all_deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
        
        results = []
        
        # npm audit
        try:
            result = subprocess.run(
                ['npm', 'audit', '--json'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(package_json_path)
            )
            audit_data = json.loads(result.stdout)
            
            for vuln in audit_data.get('vulnerabilities', {}).values():
                results.append({
                    'package': vuln['name'],
                    'severity': vuln['severity'],
                    'url': vuln.get('via', [{}])[0].get('url', ''),
                    'fix': vuln.get('fixAvailable')
                })
        except Exception as e:
            print(f"npm audit failed: {e}")
        
        return results
    
    def scan_python(self, requirements_path: str = 'requirements.txt') -> list:
        """扫描Python依赖"""
        results = []
        
        try:
            result = subprocess.run(
                ['pip', 'list', '--format=freeze'],
                capture_output=True,
                text=True
            )
            
            packages = {}
            for line in result.stdout.split('\n'):
                if '==' in line:
                    pkg, ver = line.strip().split('==')
                    packages[pkg.lower()] = ver
            
            # 使用safety检查已知漏洞
            safety_result = subprocess.run(
                ['safety', 'check', '--json'],
                capture_output=True,
                text=True,
                input=result.stdout
            )
            
            if safety_result.returncode != 0:
                try:
                    for vuln in json.loads(safety_result.stdout):
                        results.append(vuln)
                except:
                    pass
        
        except Exception as e:
            print(f"Python scan failed: {e}")
        
        return results
```

## 3. 秘钥扫描

```python
class SecretScanner:
    """敏感信息扫描"""
    
    PATTERNS = {
        'AWS Access Key': r'AKIA[0-9A-Z]{16}',
        'AWS Secret Key': r'[A-Za-z0-9/+=]{40}',
        'GitHub Token': r'ghp_[a-zA-Z0-9]{36}',
        'GitHub OAuth': r'gho_[a-zA-Z0-9]{36}',
        'Private Key': r'-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----',
        'Generic API Key': r'[a-zA-Z0-9]{32,64}',
        'Slack Token': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*',
        'Stripe Key': r'sk_live_[0-9a-zA-Z]{24}',
        'Database URL': r'(mysql|postgres|mongodb)://[^:]+:[^@]+@',
        'JWT': r'eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+',
        'Slack Webhook': r'https://hooks\.slack\.com/services/T[a-zA-Z0-9]+/B[a-zA-Z0-9]+/',
        'SendGrid Key': r'SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}',
        'Google API': r'AIza[0-9A-Za-z_-]{35}',
        'OpenAI Key': r'sk-[a-zA-Z0-9]{48}',
        'Generic Secret': r'(?i)(password|secret|api_key|apikey|auth_token|access_token)\s*[=:]\s*[\'"]?[\w-]{8,}',
    }
    
    def scan_file(self, filepath: str) -> list[dict]:
        import re
        matches = []
        
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        for pattern_name, pattern in self.PATTERNS.items():
            for i, line in enumerate(lines, 1):
                matches_found = re.finditer(pattern, line)
                for match in matches_found:
                    matches.append({
                        'file': filepath,
                        'line': i,
                        'type': pattern_name,
                        'match': match.group(),
                        'context': line.strip()[:200]
                    })
        
        return matches
    
    def scan_directory(self, root_path: str, extensions=None) -> list:
        """扫描整个目录"""
        import os
        matches = []
        extensions = extensions or ['.js', '.ts', '.py', '.java', '.go', '.rb', '.php', '.cs', '.sh', '.env', '.json', '.yaml', '.yml', '.toml', '.xml']
        
        for dirpath, dirnames, filenames in os.walk(root_path):
            # 跳过node_modules等
            dirnames[:] = [d for d in dirnames if d not in ['node_modules', '.git', '__pycache__', 'venv', '.venv']]
            
            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    filepath = os.path.join(dirpath, filename)
                    matches.extend(self.scan_file(filepath))
        
        return matches
```

## 4. 安全加固建议

```python
class SecurityHardening:
    """安全加固清单"""
    
    @staticmethod
    def generate_report(target: str, scan_results: dict) -> str:
        """生成安全报告"""
        summary = scan_results['summary']
        vulns = scan_results['vulnerabilities']
        
        report = f"""
# 安全扫描报告

## 目标
{scan_results['target']}

## 概览
- 🔴 严重: {summary['critical']}
- 🟠 高危: {summary['high']}
- 🟡 中危: {summary['medium']}
- 🟢 低危: {summary['low']}

## 发现的问题

"""
        
        for v in vulns:
            icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(v.severity, '⚪')
            report += f"""
### {icon} {v.title}

- **严重程度**: {v.severity.upper()}
- **描述**: {v.description}
- **影响**: {v.affected}
- **修复建议**: {v.remediation}
{f'- **CWE**: {v.cwe}' if v.cwe else ''}

"""
        
        return report
    
    # === 加固清单 ===
    RECOMMENDATIONS = {
        'sql_injection': [
            '使用参数化查询或ORM',
            '启用WAF',
            '最小权限原则',
            '定期代码审计'
        ],
        'xss': [
            '输出编码',
            '内容安全策略 (CSP)',
            'HTTPOnly Cookie',
            '输入验证'
        ],
        'csrf': [
            'CSRF Token',
            'SameSite Cookie',
            '双重提交Cookie',
            '验证Referer'
        ],
        'authentication': [
            '强密码策略',
            '多因素认证 (MFA)',
            '账户锁定策略',
            '安全的会话管理'
        ],
        'data_protection': [
            '传输加密 (TLS 1.3)',
            '静态加密',
            '秘钥轮换',
            '数据脱敏'
        ]
    }
```

## 5. OWASP Top 10 检查清单

| 类别 | 检测项 | 工具 |
|------|--------|------|
| A01 Broken Access | 水平/垂直越权测试 | BurpSuite |
| A02 Cryptographic Failures | 弱加密/传输/存储 | custom |
| A03 Injection | SQLi/XSS/命令注入 | ZAP, sqlmap |
| A04 Insecure Design | 业务逻辑漏洞 | manual |
| A05 Security Misconfig | 默认口令/错误配置 | nmap, nikto |
| A06 Vulnerable Components | 过时依赖 | Snyk, Dependabot |
| A07 Auth Failures | 弱认证/会话劫持 | BurpSuite |
| A08 Data Integrity | CI/CD注入/篡改 | Semgrep |
| A09 Logging Failures | 审计日志缺失 | manual |
| A10 SSRF | 服务端请求伪造 | custom |
