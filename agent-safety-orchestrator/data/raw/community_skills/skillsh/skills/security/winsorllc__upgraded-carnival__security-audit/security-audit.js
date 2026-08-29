#!/usr/bin/env node

/**
 * Security Audit - Scan code for security vulnerabilities and secrets
 * 
 * Usage:
 *   security-audit.js --scan --path /path/to/code
 *   security-audit.js --vulns --path /path/to/code
 *   security-audit.js --full --path /path/to/code
 */

const fs = require('fs');
const path = require('path');

// Secret patterns to detect
const SECRET_PATTERNS = [
  { 
    name: 'AWS Access Key',
    pattern: /AKIA[0-9A-Z]{16}/g,
    severity: 'critical'
  },
  { 
    name: 'GitHub Token',
    pattern: /(?:ghp|gho|ghu|ghs)_[A-Za-z0-9_]{36,}/g,
    severity: 'critical'
  },
  { 
    name: 'Slack Token',
    pattern: /xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*/g,
    severity: 'critical'
  },
  { 
    name: 'Telegram Bot Token',
    pattern: /[0-9]{8,10}:[A-Za-z0-9_-]{35}/g,
    severity: 'critical'
  },
  { 
    name: 'Generic API Key',
    pattern: /api[_-]?key["'\s:=]+[a-zA-Z0-9_-]{20,}/gi,
    severity: 'high'
  },
  { 
    name: 'Private Key',
    pattern: /-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----/g,
    severity: 'critical'
  },
  { 
    name: 'Database Connection String',
    pattern: /(?:mongodb|postgres|mysql|redis):\/\/[^\s"']+/gi,
    severity: 'high'
  },
  { 
    name: 'JWT Token',
    pattern: /eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,
    severity: 'medium'
  },
  { 
    name: 'Password in URL',
    pattern: /:\/\/[^:]+:[^@]+@/g,
    severity: 'high'
  },
  {
    name: 'Hardcoded Password',
    pattern: /password\s*[=:]\s*["'][^"']{4,}["']/gi,
    severity: 'medium'
  },
  {
    name: 'Secret in Code',
    pattern: /secret\s*[=:]\s*["'][^"']{8,}["']/gi,
    severity: 'medium'
  }
];

// Vulnerability patterns
const VULN_PATTERNS = [
  {
    name: 'SQL Injection Risk',
    pattern: /(?:\$GET|_|\$|_POST|\$|_REQUEST)\s*\[.*?\]\s*\.\s*\(|(?:query|execute|select|insert|update|delete).*(?:\$|_GET|\$|_POST|\$|_REQUEST)/gi,
    severity: 'critical',
    message: 'Potential SQL injection - use parameterized queries'
  },
  {
    name: 'Command Injection Risk',
    pattern: /(?:exec|system|shell_exec|passthru|popen)\s*\(\s*\$_(?:GET|POST|REQUEST)/gi,
    severity: 'critical',
    message: 'Potential command injection - sanitize user input'
  },
  {
    name: 'Eval Usage',
    pattern: /\beval\s*\(\s*\$/gi,
    severity: 'high',
    message: 'eval() with user input is dangerous'
  },
  {
    name: 'Path Traversal',
    pattern: /\.\.[\/\\]|readfile\s*\(\s*\$_(?:GET|POST)/gi,
    severity: 'high',
    message: 'Potential path traversal vulnerability'
  },
  {
    name: 'Weak Cryptography',
    pattern: /(?:md5|sha1)\s*\(\s*\$/gi,
    severity: 'medium',
    message: 'Weak hashing algorithm - use bcrypt or scrypt'
  },
  {
    name: 'Insecure Random',
    pattern: /mt_rand\s*\(|rand\s*\(/gi,
    severity: 'low',
    message: 'Use cryptographically secure random'
  },
  {
    name: 'Disabled SSL Verify',
    pattern: /(?:verify_ssl|ssl_verify|verifypeer)\s*[=:]\s*(?:false|0)/gi,
    severity: 'high',
    message: 'SSL certificate verification is disabled'
  },
  {
    name: 'Hardcoded IP',
    pattern: /\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b/g,
    severity: 'low',
    message: 'Hardcoded IP address'
  }
];

// File extensions to scan
const SCAN_EXTENSIONS = [
  '.js', '.ts', '.jsx', '.tsx', '.py', '.rb', '.php', '.java', 
  '.go', '.rs', '.cs', '.c', '.cpp', '.h', '.sh', '.bash',
  '.env', '.yaml', '.yml', '.json', '.xml', '.sql'
];

// Files and directories to ignore
const IGNORE_PATTERNS = [
  /node_modules/, /\.git/, /dist/, /build/, /\.next/,
  /coverage/, /\.cache/, /vendor/, /__pycache__/, /\.pytest_cache/,
  /package-lock\.json/, /yarn\.lock/, /\.min\.js$/, /\.map$/
];

// Check if file should be scanned
function shouldScan(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (!SCAN_EXTENSIONS.includes(ext)) {
    return false;
  }
  
  for (const pattern of IGNORE_PATTERNS) {
    if (pattern.test(filePath)) {
      return false;
    }
  }
  
  return true;
}

// Scan a file for secrets
function scanFileForSecrets(filePath, content) {
  const findings = [];
  const lines = content.split('\n');
  
  for (const pattern of SECRET_PATTERNS) {
    const matches = content.match(pattern.pattern);
    if (matches) {
      matches.forEach(match => {
        // Find line number
        let lineNum = 0;
        let pos = 0;
        for (let i = 0; i < lines.length; i++) {
          const linePos = content.indexOf(lines[i], pos);
          if (linePos >= 0 && linePos <= content.indexOf(match, pos)) {
            lineNum = i + 1;
          }
          pos = linePos + lines[i].length;
        }
        
        findings.push({
          file: filePath,
          line: lineNum,
          type: pattern.name,
          severity: pattern.severity,
          match: match.substring(0, 20) + (match.length > 20 ? '...' : '')
        });
      });
    }
  }
  
  return findings;
}

// Scan a file for vulnerabilities
function scanFileForVulns(filePath, content) {
  const findings = [];
  const lines = content.split('\n');
  
  for (const pattern of VULN_PATTERNS) {
    let match;
    const regex = new RegExp(pattern.pattern.source, pattern.pattern.flags);
    
    while ((match = regex.exec(content)) !== null) {
      // Find line number
      let lineNum = 0;
      let pos = 0;
      for (let i = 0; i < lines.length; i++) {
        const linePos = content.indexOf(lines[i], pos);
        if (linePos >= 0 && linePos <= match.index) {
          lineNum = i + 1;
        }
        pos = linePos + lines[i].length;
      }
      
      findings.push({
        file: filePath,
        line: lineNum,
        type: pattern.name,
        severity: pattern.severity,
        message: pattern.message
      });
    }
  }
  
  return findings;
}

// Scan a directory recursively
function scanDirectory(dirPath, options) {
  const secrets = [];
  const vulns = [];
  
  function scanDir(currentPath) {
    try {
      const entries = fs.readdirSync(currentPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(currentPath, entry.name);
        
        if (entry.isDirectory()) {
          // Check if should ignore
          let shouldIgnore = false;
          for (const pattern of IGNORE_PATTERNS) {
            if (pattern.test(fullPath)) {
              shouldIgnore = true;
              break;
            }
          }
          
          if (!shouldIgnore) {
            scanDir(fullPath);
          }
        } else if (entry.isFile() && shouldScan(fullPath)) {
          try {
            const content = fs.readFileSync(fullPath, 'utf-8');
            
            if (options.scan || options.full) {
              const fileSecrets = scanFileForSecrets(fullPath, content);
              secrets.push(...fileSecrets);
            }
            
            if (options.vulns || options.full) {
              const fileVulns = scanFileForVulns(fullPath, content);
              vulns.push(...fileVulns);
            }
          } catch (e) {
            // Skip files that can't be read
          }
        }
      }
    } catch (e) {
      // Skip directories that can't be read
    }
  }
  
  scanDir(dirPath);
  
  return { secrets, vulnerabilities: vulns };
}

// Parse command line arguments
const args = process.argv.slice(2);
const options = {
  scan: false,
  vulns: false,
  full: false,
  path: null,
  output: 'json'
};

for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  const nextArg = args[i + 1];
  
  switch (arg) {
    case '--scan':
      options.scan = true;
      break;
    case '--vulns':
      options.vulns = true;
      break;
    case '--full':
      options.full = true;
      break;
    case '--path':
      options.path = nextArg;
      i++;
      break;
    case '--output':
      options.output = nextArg;
      i++;
      break;
    case '--help':
    case '-h':
      console.log(`
Security Audit - Scan code for security vulnerabilities and secrets

Usage:
  security-audit.js --scan --path /path/to/code
  security-audit.js --vulns --path /path/to/code
  security-audit.js --full --path /path/to/code

Options:
  --scan             Scan for secrets
  --vulns            Check for vulnerabilities
  --full             Full security audit (secrets + vulns)
  --path <path>      Path to scan (required)
  --output <format>  Output format: json, text (default: json)

Examples:
  security-audit.js --full --path ./src
  security-audit.js --scan --path . --output text
      `.trim());
      process.exit(0);
  }
}

// Validate required options
if (!options.path) {
  console.error('Error: --path is required');
  process.exit(1);
}

if (!options.scan && !options.vulns && !options.full) {
  options.full = true; // Default to full scan
}

// Main execution
function main() {
  try {
    if (!fs.existsSync(options.path)) {
      console.error('Error: Path does not exist:', options.path);
      process.exit(1);
    }
    
    const stats = fs.statSync(options.path);
    const isDir = stats.isDirectory();
    
    let results;
    if (isDir) {
      results = scanDirectory(options.path, options);
    } else {
      // Single file
      const content = fs.readFileSync(options.path, 'utf-8');
      results = {
        secrets: options.scan || options.full ? scanFileForSecrets(options.path, content) : [],
        vulnerabilities: options.vulns || options.full ? scanFileForVulns(options.path, content) : []
      };
    }
    
    // Add summary
    const summary = {
      totalSecrets: results.secrets.length,
      totalVulnerabilities: results.vulnerabilities.length,
      critical: results.secrets.filter(s => s.severity === 'critical').length +
                results.vulnerabilities.filter(v => v.severity === 'critical').length,
      high: results.secrets.filter(s => s.severity === 'high').length +
            results.vulnerabilities.filter(v => v.severity === 'high').length,
      medium: results.secrets.filter(s => s.severity === 'medium').length +
              results.vulnerabilities.filter(v => v.severity === 'medium').length,
      low: results.secrets.filter(s => s.severity === 'low').length +
            results.vulnerabilities.filter(v => v.severity === 'low').length
    };
    
    const output = {
      summary,
      secrets: results.secrets,
      vulnerabilities: results.vulnerabilities
    };
    
    if (options.output === 'text') {
      console.log('=== Security Audit Results ===\n');
      console.log(`Summary: ${summary.totalSecrets} secrets, ${summary.totalVulnerabilities} vulnerabilities found`);
      console.log(`Critical: ${summary.critical}, High: ${summary.high}, Medium: ${summary.medium}, Low: ${summary.low}\n`);
      
      if (results.secrets.length > 0) {
        console.log('=== Secrets Found ===');
        results.secrets.forEach(s => {
          console.log(`[${s.severity.toUpperCase()}] ${s.file}:${s.line} - ${s.type}`);
        });
        console.log('');
      }
      
      if (results.vulnerabilities.length > 0) {
        console.log('=== Vulnerabilities Found ===');
        results.vulnerabilities.forEach(v => {
          console.log(`[${v.severity.toUpperCase()}] ${v.file}:${v.line} - ${v.type}: ${v.message}`);
        });
      }
    } else {
      console.log(JSON.stringify(output, null, 2));
    }
    
    // Exit with error code if critical issues found
    if (summary.critical > 0) {
      process.exit(1);
    }
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

main();
