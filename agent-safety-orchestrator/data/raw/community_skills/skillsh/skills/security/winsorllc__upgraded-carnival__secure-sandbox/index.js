/**
 * Secure Sandbox - Main Entry Point
 * 
 * Provides the programmatic API for the secure sandbox skill.
 */

const sandbox = require('./lib/sandbox');
const queue = require('./lib/queue');
const allowlist = require('./lib/allowlist');
const auditor = require('./lib/auditor');
const classifier = require('./lib/classifier');

module.exports = {
  // Core sandbox operations
  check: sandbox.check,
  execute: sandbox.execute,
  executeSync: sandbox.executeSync,
  
  // Queue management
  addToQueue: queue.addToQueue,
  approveCommand: queue.approveCommand,
  rejectCommand: queue.rejectCommand,
  listQueue: queue.listQueue,
  getQueueStats: queue.getStats,
  clearOldEntries: queue.clearOldEntries,
  
  // Allowlist management
  testAllowlist: allowlist.testAllowlist,
  addToAllowlist: allowlist.addToAllowlist,
  removeFromAllowlist: allowlist.removeFromAllowlist,
  listAllowlist: allowlist.listAllowlist,
  resetAllowlist: allowlist.resetAllowlist,
  
  // Audit logging
  logAudit: auditor.logAudit,
  logExecution: auditor.logExecution,
  logClassification: auditor.logClassification,
  readAuditLog: auditor.readAuditLog,
  getAuditStats: auditor.getAuditStats,
  exportAudit: auditor.exportAudit,
  listAuditFiles: auditor.listAuditFiles,
  clearOldLogs: auditor.clearOldLogs,
  
  // Classification
  classifyCommand: classifier.classifyCommand,
  analyzeRisk: classifier.analyzeRisk,
  
  // Config
  config: sandbox.CONFIG
};
