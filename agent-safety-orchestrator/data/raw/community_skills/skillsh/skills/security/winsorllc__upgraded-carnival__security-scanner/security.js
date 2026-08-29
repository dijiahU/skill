#!/usr/bin/env node
/**
 * Security Scanner - Vulnerability and secret detection
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Security patterns
const PATTERNS = {
  secrets: [
    { name: 'API Key', regex: /['"`]?[aA][pP][iI][_-]?[kK][eE][yY]['"`]?\s*(=|:)\s*['"`][a-zA-Z0-9_\-]{16,}['"`]/g },
    { name: 'Secret Token', regex: /['"`]?[sS][eE][cC][rR][eE][tT]['"`]?\s*(=|:)\s*['"`][a-zA-Z0-9_\-]{16,}['"`]/g },
    { name: 'Private Key', regex: /-----BEGIN [A-Z]+ PRIVATE KEY-----/ },
    { name: 'AWS Key', regex: /AKIA[0-9A-Z]{16}/ },
    { name: 'GitHub Token', regex: /gh[pousr]_[A-Za-z0-9_]{36,}/ },
    { name: 'Password', regex: /password\s*(=|:)\s*['"`].{8,}['"`]/i },
    { name: 'Bearer Token', regex: /Bearer\s+[a-zA-Z0-9_\-\.]{20,}/ },
    { name: 'JWT Token', regex: /eyJ[A-Za-z0-9_\-]*\.eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*/ },
  ],
  config: [
    { name: 'Debug Enabled', regex: /debug:\s*true/ },
    { name: 'CORS Wildcard', regex: /['"`]?\*['"`]?\s*in\s*cors|Access-Control-Allow-Origin:\s*\*/ },
    { name: 'Weak SSL', regex: /ssl:\s*false|verify:\s*false/ },
    { name: 'SQL Injection Risk', regex: /SELECT\s+.*FROM\s+.*\+.*\/\/\s*.*\+|['"`]?\$\{.*\}['"`]?.+query/i },
  ],
  permissions: [
    { type: 'file', check: (stat) => stat.mode & 0o044 }, // World readable
  ],
};

class SecurityScanner {
  constructor() {
    this.findings = [];
    this.scanned = 0;
  }

  addFinding(severity, category, file, line, message, details = '') {
    this.findings.push({
      severity,
      category,
      file,
      line: line || 0,
      message,
      details,
      timestamp: new Date().toISOString(),
    });
  }

  scanFile(filePath) {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    this.scanned++;

    // Scan for secrets
    PATTERNS.secrets.forEach(pattern => {
      lines.forEach((line, idx) => {
        if (pattern.regex.test(line)) {
          const masked = line.replace(/['"`][a-zA-Z0-9_\-\.]{10,}['"`]/g, match => 
            match.charAt(0) + '*'.repeat(Math.min(match.length - 2, 20)) + match.charAt(match.length - 1));
          this.addFinding('HIGH', 'Secret', filePath, idx + 1, 
            `Potential ${pattern.name} found`, masked.trim().substring(0, 100));
        }
      });
    });

    // Scan for config issues
    PATTERNS.config.forEach(pattern => {
      lines.forEach((line, idx) => {
        if (pattern.regex.test(line)) {
          this.addFinding('MEDIUM', 'Config', filePath, idx + 1, 
            pattern.name, line.trim().substring(0, 100));
        }
      });
    });

    // Check file permissions
    try {
      const stat = fs.statSync(filePath);
      if (stat.mode & 0o022) {
        this.addFinding('LOW', 'Permission', filePath, null, 
          'File is world-writable', `Mode: ${(stat.mode & 0o777).toString(8)}`);
      }
    } catch (e) {
      // Ignore
    }
  }

  scanDirectory(dirPath, extensions = ['.js', '.ts', '.json', '.yml', '.yaml', '.md']) {
    const files = this.getFiles(dirPath, extensions);
    files.forEach(f => {
      try {
        this.scanFile(f);
      } catch (e) {
        this.addFinding('INFO', 'Error', f, null, `Could not scan: ${e.message}`);
      }
    });
  }

  getFiles(dir, extensions, files = []) {
    if (!fs.existsSync(dir)) return files;
    
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    entries.forEach(entry => {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith('.') && 
          entry.name !== 'node_modules' && entry.name !== 'tmp') {
        this.getFiles(fullPath, extensions, files);
      } else if (entry.isFile() && extensions.some(ext => entry.name.endsWith(ext))) {
        files.push(fullPath);
      }
    });
    return files;
  }

  generateReport() {
    const high = this.findings.filter(f => f.severity === 'HIGH').length;
    const medium = this.findings.filter(f => f.severity === 'MEDIUM').length;
    const low = this.findings.filter(f => f.severity === 'LOW').length;
    
    return {
      timestamp: new Date().toISOString(),
      summary: { filesScanned: this.scanned, high, medium, low, total: this.findings.length },
      findings: this.findings,
    };
  }

  printReport(report) {
    const colors = {
      reset: '\x1b[0m',
      red: '\x1b[31m',
      yellow: '\x1b[33m',
      green: '\x1b[32m',
      cyan: '\x1b[36m',
      gray: '\x1b[90m',
    };

    console.log(`\n${colors.cyan}╔════════════════════════════════════════════════════════╗`);
    console.log(`║           Security Scanner 🛡️ v1.0.0                   ║`);
    console.log(`╚════════════════════════════════════════════════════════╝${colors.reset}\n`);

    console.log(`${colors.cyan}Summary${colors.reset}`);
    console.log(`${'─'.repeat(50)}`);
    console.log(`Files Scanned: ${report.summary.filesScanned}`);
    console.log(`${colors.red}High: ${report.summary.high}${colors.reset}`);
    console.log(`${colors.yellow}Medium: ${report.summary.medium}${colors.reset}`);
    console.log(`${colors.green}Low: ${report.summary.low}${colors.reset}`);
    console.log(`Total Issues: ${report.summary.total}\n`);

    if (report.findings.length === 0) {
      console.log(`${colors.green}✓ No security issues found${colors.reset}`);
      return;
    }

    const grouped = {};
    report.findings.forEach(f => {
      if (!grouped[f.severity]) grouped[f.severity] = [];
      grouped[f.severity].push(f);
    });

    ['HIGH', 'MEDIUM', 'LOW', 'INFO'].forEach(severity => {
      if (grouped[severity]) {
        const color = { HIGH: colors.red, MEDIUM: colors.yellow, LOW: colors.green, INFO: colors.gray }[severity];
        console.log(`\n${color}[${severity}]${colors.reset}`);
        
        grouped[severity].forEach(f => {
          console.log(`  ${colors.cyan}${f.category}${colors.reset} ${f.file}${f.line ? `:${f.line}` : ''}`);
          console.log(`    ${f.message}`);
          if (f.details) {
            console.log(`    ${colors.gray}${f.details}${colors.reset}`);
          }
        });
      }
    });
  }

  run() {
    const args = process.argv.slice(2);
    const command = args[0];

    if (!command || command === '--help') {
      console.log('Security Scanner - Vulnerability and secret detection');
      console.log('');
      console.log('Commands:');
      console.log('  scan [files...]         Scan specific files or directories');
      console.log('  check --secrets         Check for hardcoded secrets only');
      console.log('  report                  Generate security report');
      console.log('');
      console.log('Options:');
      console.log('  --full                  Full recursive scan of current directory');
      console.log('  --output FILE           Save report to file');
      process.exit(0);
    }

    if (command === 'scan') {
      const files = args.slice(1).filter(a => !a.startsWith('--'));
      
      if (args.includes('--full') || files.length === 0) {
        console.log('Scanning current directory recursively...');
        this.scanDirectory('.');
      } else {
        files.forEach(f => {
          if (fs.existsSync(f)) {
            console.log(`Scanning ${f}...`);
            this.scanFile(f);
          }
        });
      }

      const report = this.generateReport();
      this.printReport(report);

      if (args.includes('--output')) {
        const outputIdx = args.indexOf('--output');
        const outputFile = args[outputIdx + 1];
        fs.writeFileSync(outputFile, JSON.stringify(report, null, 2));
        console.log(`\nReport saved to: ${outputFile}`);
      }

      process.exit(report.summary.high > 0 ? 1 : 0);
    }

    if (command === 'check' && args.includes('--secrets')) {
      console.log('Checking for secrets in current directory...');
      this.scanDirectory('.');
      
      const secrets = this.findings.filter(f => f.category === 'Secret');
      if (secrets.length > 0) {
        console.log(`\nFound ${secrets.length} potential secrets`);
        secrets.forEach(s => console.log(`  ${s.file}:${s.line} - ${s.message}`));
        process.exit(1);
      } else {
        console.log('✓ No secrets found');
      }
    }

    console.error(`Unknown command: ${command}`);
    process.exit(1);
  }
}

if (require.main === module) {
  const scanner = new SecurityScanner();
  scanner.run();
}

module.exports = { SecurityScanner };
