/**
 * Audit Logger
 * 
 * Logs all command executions with timestamps and context.
 * Organizes logs by date in JSONL format.
 */

const fs = require('fs');
const path = require('path');

const AUDIT_DIR = path.join(__dirname, '..', '.sandbox', 'audit');

/**
 * Ensure audit directory exists
 */
function ensureAuditDir() {
  if (!fs.existsSync(AUDIT_DIR)) {
    fs.mkdirSync(AUDIT_DIR, { recursive: true });
  }
}

/**
 * Get today's audit file path
 * @returns {string} File path
 */
function getTodayAuditFile() {
  ensureAuditDir();
  const date = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
  return path.join(AUDIT_DIR, `${date}.jsonl`);
}

/**
 * Get audit file for a specific date
 * @param {string} date - Date string (YYYY-MM-DD)
 * @returns {string} File path
 */
function getAuditFileForDate(date) {
  ensureAuditDir();
  return path.join(AUDIT_DIR, `${date}.jsonl`);
}

/**
 * Log an audit entry
 * @param {Object} entry - Audit entry
 */
function logAudit(entry) {
  ensureAuditDir();
  
  const auditEntry = {
    timestamp: new Date().toISOString(),
    ...entry
  };
  
  const file = getTodayAuditFile();
  const line = JSON.stringify(auditEntry) + '\\n';
  
  fs.appendFileSync(file, line);
  
  return auditEntry;
}

/**
 * Log command execution
 * @param {Object} execution - Execution details
 */
function logExecution(execution) {
  return logAudit({
    type: 'execution',
    command: execution.command,
    risk_level: execution.risk_level,
    risk_score: execution.risk_score,
    risk_reasons: execution.risk_reasons,
    context: execution.context,
    status: execution.status,
    exit_code: execution.exit_code,
    stdout_preview: execution.stdout?.substring(0, 500),
    stderr_preview: execution.stderr?.substring(0, 500),
    duration_ms: execution.duration_ms,
    approved_by: execution.approved_by,
    queue_id: execution.queue_id
  });
}

/**
 * Log classification
 * @param {Object} classification - Classification result
 */
function logClassification(classification) {
  return logAudit({
    type: 'classification',
    command: classification.command,
    risk_level: classification.risk_level,
    risk_score: classification.risk_score,
    risk_reasons: classification.risk_reasons,
    requires_approval: classification.requires_approval,
    suggested_action: classification.suggested_action
  });
}

/**
 * Log a queued command
 * @param {Object} entry - Queue entry
 */
function logQueueEntry(entry) {
  return logAudit({
    type: 'queued',
    queue_id: entry.id,
    command: entry.command,
    risk_level: entry.risk_level,
    status: entry.status
  });
}

/**
 * Read audit log for a date range
 * @param {Object} options - Query options
 * @returns {Object[]} Audit entries
 */
function readAuditLog(options = {}) {
  ensureAuditDir();
  
  const entries = [];
  const files = fs.readdirSync(AUDIT_DIR)
    .filter(f => f.endsWith('.jsonl'))
    .sort()
    .reverse(); // Newest first
  
  for (const file of files) {
    const filePath = path.join(AUDIT_DIR, file);
    const fileDate = file.replace('.jsonl', '');
    
    // Skip files outside date range
    if (options.since && fileDate < options.since) continue;
    if (options.until && fileDate > options.until) continue;
    
    try {
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.trim().split('\\n').filter(l => l);
      
      for (const line of lines) {
        try {
          const entry = JSON.parse(line);
          
          // Apply filters
          if (options.type && entry.type !== options.type) continue;
          if (options.risk_level && entry.risk_level !== options.risk_level) continue;
          if (options.status && entry.status !== options.status) continue;
          if (options.command_pattern) {
            const regex = new RegExp(options.command_pattern, 'i');
            if (!regex.test(entry.command)) continue;
          }
          
          entries.push(entry);
        } catch (err) {
          // Skip malformed lines
        }
      }
    } catch (err) {
      console.error(`Error reading audit file ${file}:`, err.message);
    }
  }
  
  // Sort by timestamp (newest first)
  entries.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  
  if (options.limit) {
    return entries.slice(0, options.limit);
  }
  
  return entries;
}

/**
 * Get audit statistics
 * @param {Object} options - Options
 * @returns {Object} Statistics
 */
function getAuditStats(options = {}) {
  const entries = readAuditLog(options);
  
  const stats = {
    total_commands: entries.filter(e => e.type === 'execution').length,
    total_classifications: entries.filter(e => e.type === 'classification').length,
    total_queued: entries.filter(e => e.type === 'queued').length,
    
    by_risk_level: {
      safe: 0,
      normal: 0,
      dangerous: 0,
      critical: 0
    },
    
    by_status: {
      success: 0,
      failed: 0,
      blocked: 0,
      approved: 0,
      rejected: 0
    },
    
    by_type: {
      execution: 0,
      classification: 0,
      queued: 0
    },
    
    time_range: {
      start: null,
      end: null
    }
  };
  
  for (const entry of entries) {
    // Count by type
    if (entry.type) {
      stats.by_type[entry.type] = (stats.by_type[entry.type] || 0) + 1;
    }
    
    // Count by risk level
    if (entry.risk_level) {
      stats.by_risk_level[entry.risk_level] = 
        (stats.by_risk_level[entry.risk_level] || 0) + 1;
    }
    
    // Count by status
    if (entry.status) {
      stats.by_status[entry.status] = 
        (stats.by_status[entry.status] || 0) + 1;
    }
    
    // Track time range
    if (entry.timestamp) {
      if (!stats.time_range.start || entry.timestamp < stats.time_range.start) {
        stats.time_range.start = entry.timestamp;
      }
      if (!stats.time_range.end || entry.timestamp > stats.time_range.end) {
        stats.time_range.end = entry.timestamp;
      }
    }
  }
  
  return stats;
}

/**
 * Export audit log
 * @param {Object} options - Export options
 * @returns {Object} Export result
 */
function exportAudit(options = {}) {
  const entries = readAuditLog(options);
  
  const format = options.format || 'json';
  let output;
  
  if (format === 'jsonl') {
    output = entries.map(e => JSON.stringify(e)).join('\\n');
  } else if (format === 'csv') {
    // Simple CSV export
    const headers = ['timestamp', 'type', 'command', 'risk_level', 'status'];
    const rows = entries.map(e => [
      e.timestamp,
      e.type,
      `"${(e.command || '').replace(/"/g, '""')}"`,
      e.risk_level,
      e.status
    ].join(','));
    output = [headers.join(','), ...rows].join('\\n');
  } else {
    output = JSON.stringify(entries, null, 2);
  }
  
  if (options.output) {
    fs.writeFileSync(options.output, output);
    return {
      success: true,
      entries_count: entries.length,
      output_file: options.output,
      format
    };
  }
  
  return {
    success: true,
    entries_count: entries.length,
    data: output,
    format
  };
}

/**
 * Get audit files list
 * @returns {Object[]} List of audit files with metadata
 */
function listAuditFiles() {
  ensureAuditDir();
  
  const files = fs.readdirSync(AUDIT_DIR)
    .filter(f => f.endsWith('.jsonl'))
    .map(f => {
      const filePath = path.join(AUDIT_DIR, f);
      const stats = fs.statSync(filePath);
      return {
        date: f.replace('.jsonl', ''),
        filename: f,
        size_bytes: stats.size,
        modified: stats.mtime.toISOString()
      };
    })
    .sort((a, b) => b.date.localeCompare(a.date));
  
  return files;
}

/**
 * Clear old audit logs
 * @param {number} days - Keep logs for this many days
 * @returns {Object} Result
 */
function clearOldLogs(days) {
  ensureAuditDir();
  
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  
  const files = fs.readdirSync(AUDIT_DIR).filter(f => f.endsWith('.jsonl'));
  let removed = 0;
  
  for (const file of files) {
    const fileDate = file.replace('.jsonl', '');
    if (fileDate < cutoff.toISOString().split('T')[0]) {
      fs.unlinkSync(path.join(AUDIT_DIR, file));
      removed++;
    }
  }
  
  return {
    success: true,
    removed,
    message: `Cleared ${removed} old audit files`
  };
}

module.exports = {
  logAudit,
  logExecution,
  logClassification,
  logQueueEntry,
  readAuditLog,
  getAuditStats,
  exportAudit,
  listAuditFiles,
  clearOldLogs
};
