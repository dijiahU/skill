/**
 * Command Risk Classifier
 * 
 * Analyzes commands and classifies them by risk level.
 * Inspired by OpenClaw's security model.
 */

const path = require('path');
const fs = require('fs');

// Risk patterns for classification
const RISK_PATTERNS = {
  critical: [
    // Code injection / evaluation
    /\beval\s*\(/i,
    /\bexec\s*\(/i,
    /`[^`]*\$\([^)]*\)/,  // Command substitution in backticks
    /\$\([^)]*\|/i,        // Command substitution with pipe
    // Network execution
    /curl\s+.*\|\s*(ba)?sh/i,
    /wget\s+.*\|\s*(ba)?sh/i,
    /fetch\s+.*\|\s*(ba)?sh/i,
    // Shell escapes
    /;\s*rm\s+/i,
    /&&\s*rm\s+/i,
    /\|\s*sh\s+-c/i,
    // Path exploits
    /\.\.\/.*\.\.\//,        // Directory traversal
    // Privilege escalation
    /sudo\s+su\s*$/i,
    /sudo\s+-i\s*$/i,
  ],
  
  dangerous: [
    // File deletion
    /\brm\s+-[rf]+/i,
    /\brm\s+.*\*+/,
    /\brmdir\s+/,
    /\bunlink\s*\(/,
    // Permission changes
    /\bchmod\s+777/i,
    /\bchmod\s+-R/i,
    /\bchown\s+-R/i,
    /\bchgrp\s+-R/i,
    // Disk/FS operations
    /\bdd\s+if=/i,
    /\bmkfs\./i,
    /\bfsck\./i,
    /\bmount\s+/i,
    /\bumount\s+/i,
    // Privileged operations
    /\bsudo\s+/i,
    /\bsu\s+-/i,
    // Network servers
    /\bnc\s+.*-l/i,
    /\bnetcat\s+.*-l/i,
    /\bpython\s+.*-m\s+http\.server/i,
    // Package managers with system scope
    /\bapt\s+(install|remove|purge)/i,
    /\byum\s+(install|remove)/i,
    /\bdnf\s+(install|remove)/i,
    /\bpacman\s+-S/i,
    // Git destructive
    /\bgit\s+reset\s+--hard/i,
    /\bgit\s+clean\s+-f/i,
    /\bgit\s+push\s+.*--force/i,
  ],
  
  normal: [
    // Package managers (user space)
    /\bnpm\s+(install|uninstall|update)/i,
    /\byarn\s+(add|remove|install)/i,
    /\bpnpm\s+(add|remove|install)/i,
    /\bcargo\s+(build|run|test)/i,
    /\bgo\s+(build|run|test)/i,
    // Development tools
    /\bnode\s+/i,
    /\bpython\s+/i,
    /\bruby\s+/i,
    // Build tools
    /\bmake\s/i,
    /\bmvn\s/i,
    /\bgradle\s/i,
    // Git operations
    /\bgit\s+(clone|pull|fetch|merge)/i,
    /\bgit\s+(add|commit|status|log)/i,
    // File operations
    /\btouch\s+/i,
    /\bmv\s+/i,
    /\bcp\s+/i,
    /\bmkdir\s+/i,
  ],
  
  safe: [
    // Read-only commands
    /\bls\s/i,
    /\bcat\s/i,
    /\bhead\s/i,
    /\btail\s/i,
    /\bgrep\s/i,
    /\brg\s/i,
    /\bfind\s/i,
    /\bpwd\b/i,
    /\becho\s/i,
    /\bprint/,
    /\bconsole\.log/,
    /\btypeof\s/,
    // Version checks
    /\b(node|npm|python|pip|ruby|gem|go|rustc|cargo)\s+--version/i,
    // Read-only git
    /\bgit\s+(describe|rev-parse|config\s+--get)/i,
  ]
};

// Destructive path patterns
const DESTRUCTIVE_PATHS = [
  /^\/\s*$/,              // Root directory
  /^\/home\/[^\/]+\/?$/, // Home root
  /^\/etc\//,            // System config
  /^\/usr\//,            // System binaries
  /^\/bin\//,            // Core binaries
  /^\/sbin\//,           // System binaries
  /^\/var\//,            // System data
  /^\/opt\//,            // Optional packages
  /\.git\/?$/,           // Git repositories
  /node_modules\/?$/,    // Node modules
];

/**
 * Classify a command by risk level
 * @param {string} command - The command to classify
 * @param {Object} context - Execution context (cwd, user, etc.)
 * @returns {Object} Classification result
 */
function classifyCommand(command, context = {}) {
  const result = {
    command: command.trim(),
    risk_level: 'safe',
    risk_score: 0,
    risk_reasons: [],
    requires_approval: false,
    suggested_action: 'execute',
    context: context
  };

  // Check for critical patterns (automatic block)
  for (const pattern of RISK_PATTERNS.critical) {
    if (pattern.test(command)) {
      result.risk_level = 'critical';
      result.risk_score = 100;
      result.risk_reasons.push(`Critical pattern: ${pattern.source}`);
      result.requires_approval = true;
      result.suggested_action = 'block';
      return result;
    }
  }

  // Check for dangerous patterns
  for (const pattern of RISK_PATTERNS.dangerous) {
    if (pattern.test(command)) {
      result.risk_level = 'dangerous';
      result.risk_score = Math.max(result.risk_score, 75);
      result.risk_reasons.push(`Dangerous pattern: ${pattern.source.substring(0, 50)}...`);
      result.requires_approval = true;
      result.suggested_action = 'queue_for_approval';
    }
  }

  // Check for destructive paths
  const pathMatches = command.match(/\s(\/[^\s;|&]+)/g);
  if (pathMatches) {
    for (const p of pathMatches) {
      const cleanPath = p.trim();
      for (const dangerous of DESTRUCTIVE_PATHS) {
        if (dangerous.test(cleanPath)) {
          result.risk_level = result.risk_level === 'safe' ? 'dangerous' : result.risk_level;
          result.risk_score = Math.max(result.risk_score, 80);
          result.risk_reasons.push(`Destructive path: ${cleanPath}`);
          result.requires_approval = true;
          result.suggested_action = 'queue_for_approval';
        }
      }
    }
  }

  // Check for sudo escalation
  if (/\bsudo\b/.test(command)) {
    result.risk_score += 20;
    if (!result.risk_reasons.includes('Uses sudo privileges')) {
      result.risk_reasons.push('Uses sudo privileges');
    }
  }

  // Check for network operations
  if (/\b(curl|wget|fetch)\b/.test(command)) {
    result.risk_score += 10;
    // Higher risk if piping to shell
    if (/\|\s*(ba)?sh/i.test(command)) {
      result.risk_level = 'critical';
      result.risk_score = 100;
      result.risk_reasons.push('Network code execution via pipe to shell');
      result.requires_approval = true;
      result.suggested_action = 'block';
      return result;
    }
  }

  // Check for normal patterns (only if not already classified)
  if (result.risk_level === 'safe') {
    for (const pattern of RISK_PATTERNS.normal) {
      if (pattern.test(command)) {
        result.risk_level = 'normal';
        result.risk_score = Math.max(result.risk_score, 25);
        break;
      }
    }
  }

  // Check for safe patterns
  if (result.risk_level === 'safe' && result.risk_score === 0) {
    for (const pattern of RISK_PATTERNS.safe) {
      if (pattern.test(command)) {
        result.risk_reasons.push('Read-only operation');
        break;
      }
    }
  }

  // Final decision
  if (result.risk_level === 'critical') {
    result.requires_approval = true;
    result.suggested_action = 'block';
  } else if (result.risk_level === 'dangerous') {
    result.requires_approval = true;
    result.suggested_action = 'queue_for_approval';
  } else if (result.risk_level === 'normal') {
    result.requires_approval = false;
    result.suggested_action = 'execute';
  }

  return result;
}

/**
 * Get detailed risk analysis
 * @param {string} command - The command to analyze
 * @returns {Object} Detailed analysis
 */
function analyzeRisk(command) {
  const classification = classifyCommand(command);
  
  return {
    ...classification,
    recommendations: generateRecommendations(classification),
    safe_alternatives: suggestAlternatives(command, classification)
  };
}

/**
 * Generate recommendations based on classification
 * @param {Object} classification - The classification result
 * @returns {string[]} Array of recommendations
 */
function generateRecommendations(classification) {
  const recommendations = [];
  
  switch (classification.risk_level) {
    case 'critical':
      recommendations.push('This command poses a critical security risk');
      recommendations.push('Consider using safer alternatives');
      recommendations.push('If required, break into smaller, verifiable steps');
      break;
    case 'dangerous':
      recommendations.push('Review the command carefully before execution');
      recommendations.push('Consider running in a dry-run mode first');
      if (classification.command.match(/rm\s+-r/)) {
        recommendations.push('Consider using `rm -i` for interactive mode');
        recommendations.push('Verify the target path is correct: `ls <path>` first');
      }
      break;
    case 'normal':
      recommendations.push('Standard operation - proceed with normal precautions');
      break;
    case 'safe':
      recommendations.push('Read-only operation - safe to execute');
      break;
  }
  
  return recommendations;
}

/**
 * Suggest safer alternatives
 * @param {string} command - The original command
 * @param {Object} classification - The classification result
 * @returns {string[]} Safer alternatives
 */
function suggestAlternatives(command, classification) {
  const alternatives = [];
  
  // Suggest safer rm alternatives
  if (/\brm\s+-rf?/.test(command)) {
    const target = command.match(/rm\s+-[rf]+\s+(.+)/i)?.[1] || 'target';
    alternatives.push(`# Preview what would be deleted:\nls -la ${target}`);
    alternatives.push(`# Interactive deletion:\nrm -i ${target}`);
    alternatives.push(`# Move to trash instead:\nmv ${target} ~/.Trash/`);
  }
  
  // Suggest safer chmod alternatives
  if (/\bchmod\s+777/.test(command)) {
    const target = command.match(/chmod\s+777\s+(.+)/i)?.[1] || 'target';
    alternatives.push(`# Use more restrictive permissions:\nchmod 755 ${target}`);
    alternatives.push(`# Or even more restrictive:\nchmod 644 ${target}`);
  }
  
  // Suggest safer curl alternatives
  if (/curl\s+.*\|/.test(command)) {
    const url = command.match(/curl\s+([\'"]?https?:\/\/[^\s|]+)/i)?.[1];
    if (url) {
      alternatives.push(`# Download and inspect first:\ncurl -o /tmp/download ${url}`);
      alternatives.push(`# Then review before running:\ncat /tmp/download`);
      alternatives.push(`# Only execute if safe:\nbash /tmp/download`);
    }
  }
  
  return alternatives;
}

module.exports = {
  classifyCommand,
  analyzeRisk,
  RISK_PATTERNS,
  DESTRUCTIVE_PATHS
};
