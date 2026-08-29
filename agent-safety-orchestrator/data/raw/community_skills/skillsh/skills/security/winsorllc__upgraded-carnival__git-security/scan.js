#!/usr/bin/env node
/**
 * Git Security Scanner - Secret detection
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Secret patterns to detect
const secretPatterns = [
  {
    name: 'OpenAI API Key',
    pattern: /sk-[a-zA-Z0-9]{20,}/g,
    severity: 'critical'
  },
  {
    name: 'AWS Access Key',
    pattern: /AKIA[0-9A-Z]{16}/g,
    severity: 'critical'
  },
  {
    name: 'AWS Secret Key',
    pattern: /[0-9a-zA-Z/+]{40}/g,
    severity: 'critical'
  },
  {
    name: 'GitHub Token',
    pattern: /ghp_[a-zA-Z0-9]{36}/g,
    severity: 'critical'
  },
  {
    name: 'Private Key',
    pattern: /-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----/g,
    severity: 'critical'
  },
  {
    name: 'Database URL',
    pattern: /(postgres|mysql|mongodb):\/\/[^:]+:[^@\x5d]+@/gi,
    severity: 'high'
  },
  {
    name: 'Password in URL',
    pattern: /https?:\/\/[^:\s]+:[^@\s]+@/g,
    severity: 'high'
  },
  {
    name: 'API Key Pattern',
    pattern: /["\']?[a-zA-Z_]*[kK][eE][yY]["\']?\s*[:=]\s*["\'][a-zA-Z0-9_\-\.]{20,}["\']/g,
    severity: 'medium'
  },
  {
    name: 'Secret Pattern',
    pattern: /["\']?[a-zA-Z_]*[sS][eE][cC][rR][eE][tT]["\']?\s*[:=]\s*["\'][a-zA-Z0-9_\-\.]{10,}["\']/g,
    severity: 'medium'
  },
  {
    name: 'Token Pattern',
    pattern: /["\']?[a-zA-Z_]*[tT][oO][kK][eE][nN]["\']?\s*[:=]\s*["\'][a-zA-Z0-9_\-\.]{15,}["\']/g,
    severity: 'medium'
  },
  {
    name: 'Bearer Token',
    pattern: /[bB]earer\s+[a-zA-Z0-9_\-\.]+/g,
    severity: 'medium'
  },
  {
    name: 'Slack Token',
    pattern: /xox[baprs]-[0-9a-zA-Z\-]+/g,
    severity: 'critical'
  },
  {
    name: 'Generic Secret',
    pattern: /[\w-]*[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd][\w-]*\s*[=:]\s*["\'][^"\']{8,}["\']/g,
    severity: 'high'
  }
];

const IGNORE_PATTERNS = [
  /\.git\//,
  /node_modules\//,
  /\.env\.example/,
  /\.env\.sample/,
  /test\/.*\.(js|ts)$/,
  /____\.js$/,
  /example.*\.js$/,
  /sample.*\.js$/,
  /SKILL\.md$/,
  /test\.js$/
];

function shouldScanFile(filepath) {
  return !IGNORE_PATTERNS.some(pattern => pattern.test(filepath));
}

function scanFile(filepath, content) {
  const findings = [];
  
  for (const { name, pattern, severity } of secretPatterns) {
    const matches = content.match(pattern);
    if (matches) {
      for (const match of matches) {
        // Check for redacted patterns
        if (match.includes('****') || match.includes('...') || match.includes('your-') || match.includes('placeholder')) {
          continue;
        }
        
        // Get context (line number and surrounding text)
        const lines = content.split('\n');
        let lineNum = 0;
        let charCount = 0;
        
        for (let i = 0; i < lines.length; i++) {
          if (charCount + lines[i].length >= content.indexOf(match)) {
            lineNum = i + 1;
            break;
          }
          charCount += lines[i].length + 1;
        }
        
        findings.push({
          file: filepath,
          line: lineNum,
          pattern: name,
          match: match.substring(0, 20) + (match.length > 20 ? '...' : ''),
          severity
        });
      }
    }
  }
  
  return findings;
}

function scanDirectory(dirPath) {
  const findings = [];
  
  function scanRecursive(currentPath) {
    const entries = fs.readdirSync(currentPath, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = path.join(currentPath, entry.name);
      
      if (entry.isSymbolicLink()) continue;
      
      if (entry.isDirectory()) {
        // Skip common ignore directories
        if (['.git', 'node_modules', 'dist', 'build', '.next', 'coverage', '__pycache__', '.venv', 'venv'].includes(entry.name)) {
          continue;
        }
        scanRecursive(fullPath);
      } else if (entry.isFile()) {
        if (!shouldScanFile(fullPath)) continue;
        
        // Check file extensions
        const ext = path.extname(entry.name).toLowerCase();
        if (!['.js', '.ts', '.json', '.yaml', '.yml', '.env', '.toml', '.ini', '.conf', '.config', '.sh', '.py', '.rb', '.php', '.go', '.rs', '.java', '.c', '.cpp', '.h', '.swift', '.kt'].includes(ext) && !entry.name.startsWith('.env')) {
          continue;
        }
        
        try {
          const content = fs.readFileSync(fullPath, 'utf8');
          const fileFindings = scanFile(fullPath, content);
          findings.push(...fileFindings);
        } catch (err) {
          // Binary file or unreadable, skip
        }
      }
    }
  }
  
  scanRecursive(dirPath);
  return findings;
}

function scanGitStaged(repoPath) {
  const findings = [];
  
  try {
    const output = execSync('git diff --cached --name-only', { 
      cwd: repoPath, 
      encoding: 'utf8' 
    });
    
    const files = output.trim().split('\n').filter(f => f);
    
    for (const file of files) {
      const fullPath = path.join(repoPath, file);
      if (!fs.existsSync(fullPath)) continue;
      
      try {
        const content = fs.readFileSync(fullPath, 'utf8');
        const fileFindings = scanFile(file, content);
        findings.push(...fileFindings);
      } catch (err) {
        // Skip binary files
      }
    }
  } catch (err) {
    // Not a git repo or no staged files
  }
  
  return findings;
}

function formatFindings(findings, format = 'text') {
  if (format === 'json') {
    return JSON.stringify(findings, null, 2);
  }
  
  if (findings.length === 0) {
    return '✓ No secrets detected';
  }
  
  const bySeverity = {};
  for (let severity of ['critical', 'high', 'medium', 'low']) {
    bySeverity[severity] = findings.filter(f => f.severity === severity);
  }
  
  let output = '';
  let total = 0;
  
  for (let severity of ['critical', 'high', 'medium', 'low']) {
    const items = bySeverity[severity];
    if (items.length > 0) {
      const color = severity === 'critical' ? '\x1b[31m' : 
                   severity === 'high' ? '\x1b[31m' :
                   severity === 'medium' ? '\x1b[33m' : '\x1b[36m';
      output += `${color}[${severity.toUpperCase()}] ${items.length} finding(s)\x1b[0m\n`;
      for (const item of items) {
        output += `  ${item.file}:${item.line} - ${item.pattern}\n`;
      }
      total += items.length;
    }
  }
  
  output += `\n${total} total potential secret(s) detected`;
  return output;
}

function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args.includes('--help')) {
    console.log(`
Git Security Scanner

Usage:
  scan.js [options]

Options:
  --path <path>     Scan specific path (default: current directory)
  --staged          Scan only staged git files
  --json            Output as JSON
  --install-hook    Install pre-commit hook

Examples:
  scan.js
  scan.js --path /repo --json
  scan.js --staged
    `);
    return;
  }
  
  const scanPath = args.find(a => a.startsWith('--path='))?.split('=')[1] || 
                   args[args.indexOf('--path') + 1] || 
                   process.cwd();
  const stagedOnly = args.includes('--staged');
  const outputJson = args.includes('--json');
  
  const resolvedPath = path.resolve(scanPath);
  
  if (!fs.existsSync(resolvedPath)) {
    console.error(`Path not found: ${resolvedPath}`);
    process.exit(1);
  }
  
  console.log(`Scanning ${stagedOnly ? 'staged files in' : ''} ${resolvedPath}...\n`);
  
  let findings;
  if (stagedOnly) {
    findings = scanGitStaged(resolvedPath);
  } else {
    findings = scanDirectory(resolvedPath);
  }
  
  console.log(formatFindings(findings, outputJson ? 'json' : 'text'));
  
  // Exit with error if critical findings
  const criticalCount = findings.filter(f => f.severity === 'critical').length;
  if (criticalCount > 0) {
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { 
  scanFile, 
  scanDirectory, 
  scanGitStaged, 
  secretPatterns, 
  shouldScanFile 
};
