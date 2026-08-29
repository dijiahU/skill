/**
 * Output parsers for external security/quality tools.
 * Each parser converts raw tool output into finding[] compatible with severity.mjs.
 * Zero dependencies — pure Node.js.
 */

import { finding, SEVERITY } from '../utils/severity.mjs';

/**
 * Map a SARIF level to our severity.
 */
function sarifLevelToSeverity(level) {
  switch (level) {
    case 'error': return SEVERITY.HIGH;
    case 'warning': return SEVERITY.MEDIUM;
    case 'note': return SEVERITY.LOW;
    case 'none': return SEVERITY.INFO;
    default: return SEVERITY.MEDIUM;
  }
}

/**
 * Parse SARIF output (shared by Semgrep --sarif, ESLint --format=json-sarif, etc.)
 */
export function parseSarif(raw, analyzer, toolId) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    for (const run of data.runs || []) {
      const ruleMap = new Map();
      for (const rule of run.tool?.driver?.rules || []) {
        ruleMap.set(rule.id, rule);
      }

      for (const result of run.results || []) {
        const rule = ruleMap.get(result.ruleId) || {};
        const location = result.locations?.[0]?.physicalLocation;
        const filePath = location?.artifactLocation?.uri?.replace(/^file:\/\//, '') || null;
        const line = location?.region?.startLine || null;
        const snippet = location?.region?.snippet?.text?.trim() || null;

        const severity = sarifLevelToSeverity(result.level);

        findings.push(finding({
          analyzer,
          severity,
          title: `${result.ruleId || 'Unknown rule'}: ${result.message?.text || 'No description'}`.slice(0, 200),
          description: rule.shortDescription?.text || rule.fullDescription?.text || result.message?.text || '',
          file: filePath,
          line,
          snippet,
          remediation: rule.help?.text || rule.helpUri || null,
          source: 'tool',
          toolId,
        }));
      }
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse Semgrep JSON output (--json format).
 */
export function parseSemgrepJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    for (const result of data.results || []) {
      const severityMap = {
        'ERROR': SEVERITY.HIGH,
        'WARNING': SEVERITY.MEDIUM,
        'INFO': SEVERITY.LOW,
      };

      const metaSeverity = result.extra?.metadata?.severity;
      let severity;
      if (metaSeverity === 'CRITICAL' || metaSeverity === 'critical') {
        severity = SEVERITY.CRITICAL;
      } else if (metaSeverity === 'ERROR' || metaSeverity === 'HIGH' || metaSeverity === 'high') {
        severity = SEVERITY.HIGH;
      } else {
        severity = severityMap[result.extra?.severity] || SEVERITY.MEDIUM;
      }

      findings.push(finding({
        analyzer,
        severity,
        title: `${result.check_id}: ${result.extra?.message || 'Finding'}`.slice(0, 200),
        description: result.extra?.message || result.check_id || '',
        file: result.path || null,
        line: result.start?.line || null,
        snippet: result.extra?.lines?.trim() || null,
        remediation: result.extra?.metadata?.references?.join(', ') || result.extra?.fix || null,
        source: 'tool',
        toolId: 'semgrep',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse ESLint JSON output (--format=json).
 */
export function parseEslintJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    for (const fileResult of data) {
      for (const msg of fileResult.messages || []) {
        const severity = msg.severity === 2 ? SEVERITY.MEDIUM : SEVERITY.LOW;

        findings.push(finding({
          analyzer,
          severity,
          title: `${msg.ruleId || 'eslint'}: ${msg.message}`.slice(0, 200),
          description: msg.message || '',
          file: fileResult.filePath || null,
          line: msg.line || null,
          snippet: msg.source || null,
          remediation: msg.ruleId ? `Fix or disable rule: ${msg.ruleId}` : null,
          source: 'tool',
          toolId: 'eslint',
        }));
      }
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse Trivy JSON output (--format=json).
 */
export function parseTrivyJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    const results = data.Results || data.results || [];
    for (const result of results) {
      for (const vuln of result.Vulnerabilities || result.vulnerabilities || []) {
        const severityMap = {
          'CRITICAL': SEVERITY.CRITICAL,
          'HIGH': SEVERITY.HIGH,
          'MEDIUM': SEVERITY.MEDIUM,
          'LOW': SEVERITY.LOW,
          'UNKNOWN': SEVERITY.INFO,
        };

        const severity = severityMap[(vuln.Severity || vuln.severity || '').toUpperCase()] || SEVERITY.MEDIUM;
        const pkg = vuln.PkgName || vuln.pkgName || 'unknown';
        const installed = vuln.InstalledVersion || vuln.installedVersion || '';
        const fixed = vuln.FixedVersion || vuln.fixedVersion || '';
        const vulnId = vuln.VulnerabilityID || vuln.vulnerabilityID || '';

        findings.push(finding({
          analyzer,
          severity,
          title: `${vulnId}: ${pkg}@${installed}`.slice(0, 200),
          description: vuln.Description || vuln.description || vuln.Title || vuln.title || '',
          file: result.Target || result.target || null,
          remediation: fixed ? `Update ${pkg} to ${fixed}` : `No fix available. See ${vuln.PrimaryURL || vuln.primaryURL || vulnId}`,
          source: 'tool',
          toolId: 'trivy',
        }));
      }
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse Bandit JSON output (--format=json).
 */
export function parseBanditJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    const severityMap = {
      'HIGH': SEVERITY.HIGH,
      'MEDIUM': SEVERITY.MEDIUM,
      'LOW': SEVERITY.LOW,
    };

    const confidenceWeight = {
      'HIGH': 0,
      'MEDIUM': 1,
      'LOW': 2,
    };

    for (const result of data.results || []) {
      let severity = severityMap[(result.issue_severity || '').toUpperCase()] || SEVERITY.MEDIUM;
      // Downgrade low-confidence findings
      if ((confidenceWeight[result.issue_confidence] || 0) >= 2 && severity !== SEVERITY.LOW) {
        severity = SEVERITY.LOW;
      }

      findings.push(finding({
        analyzer,
        severity,
        title: `${result.test_id}: ${result.issue_text}`.slice(0, 200),
        description: result.issue_text || '',
        file: result.filename || null,
        line: result.line_number || null,
        snippet: result.code?.trim() || null,
        remediation: result.more_info || null,
        source: 'tool',
        toolId: 'bandit',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse TruffleHog JSON output (line-delimited JSON).
 */
export function parseTrufflehogJson(raw, analyzer) {
  try {
    const findings = [];
    const lines = raw.trim().split('\n').filter(Boolean);

    for (const line of lines) {
      let result;
      try { result = JSON.parse(line); } catch { continue; }

      const detectorName = result.DetectorName || result.detectorName || result.SourceMetadata?.Data?.Filesystem?.file || 'Unknown';
      const filePath = result.SourceMetadata?.Data?.Filesystem?.file || null;
      const lineNum = result.SourceMetadata?.Data?.Filesystem?.line || null;

      findings.push(finding({
        analyzer,
        severity: result.Verified ? SEVERITY.CRITICAL : SEVERITY.HIGH,
        title: `${detectorName} secret ${result.Verified ? '(verified)' : '(unverified)'}${filePath ? ` in ${filePath}` : ''}`.slice(0, 200),
        description: `${detectorName} detector found a ${result.Verified ? 'verified active' : 'potential'} secret.${result.DecoderName ? ` Encoding: ${result.DecoderName}.` : ''}`,
        file: filePath,
        line: lineNum,
        snippet: result.Raw ? '[REDACTED]' : null,
        remediation: result.Verified ? 'This secret is confirmed active. Rotate it immediately.' : 'Verify whether this secret is active and rotate if needed.',
        source: 'tool',
        toolId: 'trufflehog',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse Gitleaks JSON output.
 */
export function parseGitleaksJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    if (!Array.isArray(data)) return [];

    const findings = [];
    for (const leak of data) {
      findings.push(finding({
        analyzer,
        severity: SEVERITY.HIGH,
        title: `${leak.RuleID || leak.ruleID || 'secret'}: ${leak.Description || 'Secret detected'}`.slice(0, 200),
        description: leak.Description || `Secret detected by rule ${leak.RuleID || leak.ruleID}`,
        file: leak.File || leak.file || null,
        line: leak.StartLine || leak.startLine || null,
        snippet: '[REDACTED]',
        remediation: 'Remove the secret from source code and rotate the credential.',
        source: 'tool',
        toolId: 'gitleaks',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse Madge JSON output (circular dependency detection).
 */
export function parseMadgeJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    if (!Array.isArray(data)) return [];

    const findings = [];
    for (const cycle of data) {
      if (!Array.isArray(cycle) || cycle.length === 0) continue;

      const cycleStr = cycle.join(' → ');
      findings.push(finding({
        analyzer,
        severity: SEVERITY.MEDIUM,
        title: `Circular import detected (${cycle.length} files)`,
        description: `Circular dependency chain: ${cycleStr}. Circular imports can cause initialization issues, make testing difficult, and indicate tight coupling.`,
        file: cycle[0],
        remediation: 'Break the cycle by extracting shared code into a separate module, or use dependency injection.',
        source: 'tool',
        toolId: 'madge',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse npm audit JSON output.
 */
export function parseNpmAuditJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    const severityMap = {
      'critical': SEVERITY.CRITICAL,
      'high': SEVERITY.HIGH,
      'moderate': SEVERITY.MEDIUM,
      'low': SEVERITY.LOW,
      'info': SEVERITY.INFO,
    };

    const vulns = data.vulnerabilities || {};
    for (const [name, info] of Object.entries(vulns)) {
      const severity = severityMap[info.severity] || SEVERITY.MEDIUM;
      findings.push(finding({
        analyzer,
        severity,
        title: `Vulnerable dependency: ${name} (${info.severity})`,
        description: `${info.title || 'Known vulnerability'} in ${name}. ${info.url || ''}`.trim(),
        remediation: info.fixAvailable
          ? `Run \`npm audit fix\` or update ${name} to a patched version.`
          : `No automatic fix available. Check ${info.url || 'npm advisory'} for details.`,
        source: 'tool',
        toolId: 'npm-audit',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse pnpm audit JSON output.
 */
export function parsePnpmAuditJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    const severityMap = {
      'critical': SEVERITY.CRITICAL,
      'high': SEVERITY.HIGH,
      'moderate': SEVERITY.MEDIUM,
      'low': SEVERITY.LOW,
      'info': SEVERITY.INFO,
    };

    const advisories = data.advisories || {};
    for (const [, advisory] of Object.entries(advisories)) {
      const severity = severityMap[advisory.severity] || SEVERITY.MEDIUM;
      findings.push(finding({
        analyzer,
        severity,
        title: `Vulnerable dependency: ${advisory.module_name || 'unknown'} (${advisory.severity})`,
        description: advisory.title || advisory.overview || '',
        remediation: advisory.recommendation || advisory.url || 'Check advisory for details.',
        source: 'tool',
        toolId: 'pnpm-audit',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse yarn audit JSON output (line-delimited JSON).
 */
export function parseYarnAuditJson(raw, analyzer) {
  try {
    const findings = [];
    const lines = raw.trim().split('\n').filter(Boolean);

    const severityMap = {
      'critical': SEVERITY.CRITICAL,
      'high': SEVERITY.HIGH,
      'moderate': SEVERITY.MEDIUM,
      'low': SEVERITY.LOW,
      'info': SEVERITY.INFO,
    };

    for (const line of lines) {
      let entry;
      try { entry = JSON.parse(line); } catch { continue; }
      if (entry.type !== 'auditAdvisory') continue;

      const advisory = entry.data?.advisory;
      if (!advisory) continue;

      const severity = severityMap[advisory.severity] || SEVERITY.MEDIUM;
      findings.push(finding({
        analyzer,
        severity,
        title: `Vulnerable dependency: ${advisory.module_name || 'unknown'} (${advisory.severity})`,
        description: advisory.title || advisory.overview || '',
        remediation: advisory.recommendation || advisory.url || 'Check advisory for details.',
        source: 'tool',
        toolId: 'yarn-audit',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse OSV-Scanner JSON output.
 */
export function parseOsvScannerJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    const severityMap = {
      'CRITICAL': SEVERITY.CRITICAL,
      'HIGH': SEVERITY.HIGH,
      'MODERATE': SEVERITY.MEDIUM,
      'MEDIUM': SEVERITY.MEDIUM,
      'LOW': SEVERITY.LOW,
    };

    for (const result of data.results || []) {
      const source = result.source?.path || null;
      for (const pkg of result.packages || []) {
        const pkgInfo = pkg.package || {};
        for (const vuln of pkg.vulnerabilities || []) {
          const dbSeverity = vuln.database_specific?.severity || vuln.severity?.[0]?.type || '';
          const severity = severityMap[dbSeverity.toUpperCase()] || SEVERITY.MEDIUM;

          findings.push(finding({
            analyzer,
            severity,
            title: `${vuln.id}: ${pkgInfo.name || 'unknown'}@${pkgInfo.version || '?'}`.slice(0, 200),
            description: vuln.summary || vuln.details || '',
            file: source,
            remediation: vuln.id ? `See https://osv.dev/vulnerability/${vuln.id}` : null,
            source: 'tool',
            toolId: 'osv-scanner',
          }));
        }
      }
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse `mix audit` text output.
 */
export function parseMixAuditText(raw, analyzer) {
  const findings = [];
  const blocks = raw.split(/\n-{3,}\n/).filter(Boolean);

  const severityMap = {
    'critical': SEVERITY.CRITICAL,
    'high': SEVERITY.HIGH,
    'moderate': SEVERITY.MEDIUM,
    'medium': SEVERITY.MEDIUM,
    'low': SEVERITY.LOW,
  };

  for (const block of blocks) {
    const pkgMatch = block.match(/Package:\s*(\S+)/i);
    const titleMatch = block.match(/Title:\s*(.+)/i);
    const severityMatch = block.match(/Severity:\s*(\S+)/i);
    const urlMatch = block.match(/URL:\s*(\S+)/i);

    if (pkgMatch && titleMatch) {
      const severity = severityMap[(severityMatch?.[1] || '').toLowerCase()] || SEVERITY.MEDIUM;
      findings.push(finding({
        analyzer,
        severity,
        title: `${pkgMatch[1]}: ${titleMatch[1]}`.slice(0, 200),
        description: titleMatch[1],
        file: 'mix.exs',
        remediation: urlMatch?.[1] || `Update ${pkgMatch[1]} to a patched version.`,
        source: 'tool',
        toolId: 'mix-audit',
      }));
    }
  }

  return findings;
}

/**
 * Parse `cargo audit --json` output.
 */
export function parseCargoAuditJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    const severityMap = {
      'critical': SEVERITY.CRITICAL,
      'high': SEVERITY.HIGH,
      'medium': SEVERITY.MEDIUM,
      'low': SEVERITY.LOW,
      'informational': SEVERITY.INFO,
    };

    for (const vuln of data.vulnerabilities?.list || []) {
      const advisory = vuln.advisory || {};
      const pkg = vuln.package || {};
      const severity = severityMap[(advisory.cvss?.severity || '').toLowerCase()] || SEVERITY.MEDIUM;

      findings.push(finding({
        analyzer,
        severity,
        title: `${advisory.id || 'RUSTSEC'}: ${pkg.name || 'unknown'}@${pkg.version || '?'}`.slice(0, 200),
        description: advisory.title || advisory.description || '',
        file: 'Cargo.toml',
        remediation: advisory.url || (advisory.id ? `See https://rustsec.org/advisories/${advisory.id}` : null),
        source: 'tool',
        toolId: 'cargo-audit',
      }));
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse `pip-audit --format=json` output.
 */
export function parsePipAuditJson(raw, analyzer) {
  try {
    const data = JSON.parse(raw);
    const findings = [];

    for (const dep of data.dependencies || data) {
      for (const vuln of dep.vulns || []) {
        findings.push(finding({
          analyzer,
          severity: SEVERITY.HIGH,
          title: `${vuln.id}: ${dep.name}@${dep.version}`.slice(0, 200),
          description: vuln.description || `Known vulnerability in ${dep.name}`,
          file: 'requirements.txt',
          remediation: vuln.fix_versions?.length
            ? `Update ${dep.name} to ${vuln.fix_versions.join(' or ')}`
            : `See https://osv.dev/vulnerability/${vuln.id}`,
          source: 'tool',
          toolId: 'pip-audit',
        }));
      }
    }

    return findings;
  } catch {
    return [];
  }
}

/**
 * Parse `bundler-audit` text output.
 */
export function parseBundlerAuditText(raw, analyzer) {
  const findings = [];
  const blocks = raw.split(/\n\n+/).filter(Boolean);

  for (const block of blocks) {
    const nameMatch = block.match(/Name:\s*(\S+)/);
    const titleMatch = block.match(/Title:\s*(.+)/);
    const versionMatch = block.match(/Version:\s*(\S+)/);
    const advisoryMatch = block.match(/Advisory:\s*(\S+)/);
    const critMatch = block.match(/Criticality:\s*(\S+)/i);
    const urlMatch = block.match(/URL:\s*(\S+)/);

    if (nameMatch && titleMatch) {
      const severityMap = {
        'critical': SEVERITY.CRITICAL,
        'high': SEVERITY.HIGH,
        'medium': SEVERITY.MEDIUM,
        'low': SEVERITY.LOW,
      };

      const severity = severityMap[(critMatch?.[1] || '').toLowerCase()] || SEVERITY.MEDIUM;
      findings.push(finding({
        analyzer,
        severity,
        title: `${advisoryMatch?.[1] || 'CVE'}: ${nameMatch[1]}@${versionMatch?.[1] || '?'}`.slice(0, 200),
        description: titleMatch[1],
        file: 'Gemfile',
        remediation: urlMatch?.[1] || `Update ${nameMatch[1]} to a patched version.`,
        source: 'tool',
        toolId: 'bundler-audit',
      }));
    }
  }

  return findings;
}

/**
 * Registry of parser IDs to functions.
 */
export const PARSERS = {
  'sarif': parseSarif,
  'semgrep-json': parseSemgrepJson,
  'eslint-json': parseEslintJson,
  'trivy-json': parseTrivyJson,
  'bandit-json': parseBanditJson,
  'trufflehog-json': parseTrufflehogJson,
  'gitleaks-json': parseGitleaksJson,
  'madge-json': parseMadgeJson,
  'npm-audit-json': parseNpmAuditJson,
  'pnpm-audit-json': parsePnpmAuditJson,
  'yarn-audit-json': parseYarnAuditJson,
  'osv-scanner-json': parseOsvScannerJson,
  'mix-audit-text': parseMixAuditText,
  'cargo-audit-json': parseCargoAuditJson,
  'pip-audit-json': parsePipAuditJson,
  'bundler-audit-text': parseBundlerAuditText,
};
