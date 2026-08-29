/**
 * Approval Queue Manager
 * 
 * Manages commands awaiting user approval.
 * Stores queue in JSON file for persistence.
 */

const fs = require('fs');
const path = require('path');

const QUEUE_FILE = path.join(__dirname, '..', '.sandbox', 'queue.json');
const QUEUE_DIR = path.join(__dirname, '..', '.sandbox');

/**
 * Ensure queue file exists
 */
function ensureQueueFile() {
  if (!fs.existsSync(QUEUE_DIR)) {
    fs.mkdirSync(QUEUE_DIR, { recursive: true });
  }
  if (!fs.existsSync(QUEUE_FILE)) {
    fs.writeFileSync(QUEUE_FILE, JSON.stringify({ queue: [], last_id: 0 }, null, 2));
  }
}

/**
 * Load queue from file
 * @returns {Object} Queue data
 */
function loadQueue() {
  ensureQueueFile();
  try {
    const data = fs.readFileSync(QUEUE_FILE, 'utf8');
    return JSON.parse(data);
  } catch (err) {
    return { queue: [], last_id: 0 };
  }
}

/**
 * Save queue to file
 * @param {Object} data - Queue data
 */
function saveQueue(data) {
  ensureQueueFile();
  fs.writeFileSync(QUEUE_FILE, JSON.stringify(data, null, 2));
}

/**
 * Generate unique command ID
 * @returns {string} Command ID
 */
function generateId() {
  const data = loadQueue();
  data.last_id++;
  saveQueue(data);
  return `cmd_${Date.now().toString(36)}_${data.last_id}`;
}

/**
 * Add command to approval queue
 * @param {Object} commandInfo - Command information
 * @returns {Object} Queue entry
 */
function addToQueue(commandInfo) {
  const data = loadQueue();
  
  const entry = {
    id: generateId(),
    command: commandInfo.command,
    risk_level: commandInfo.risk_level,
    risk_score: commandInfo.risk_score,
    risk_reasons: commandInfo.risk_reasons,
    context: commandInfo.context || {},
    status: 'pending',
    created_at: new Date().toISOString(),
    approved_at: null,
    approved_by: null,
    rejection_reason: null,
    execution_result: null
  };
  
  data.queue.push(entry);
  saveQueue(data);
  
  return entry;
}

/**
 * Get queue entry by ID
 * @param {string} id - Entry ID
 * @returns {Object|null} Entry or null
 */
function getEntry(id) {
  const data = loadQueue();
  return data.queue.find(e => e.id === id) || null;
}

/**
 * Update queue entry
 * @param {Object} entry - Updated entry
 */
function updateEntry(entry) {
  const data = loadQueue();
  const index = data.queue.findIndex(e => e.id === entry.id);
  if (index !== -1) {
    data.queue[index] = entry;
    saveQueue(data);
  }
}

/**
 * Approve a queued command
 * @param {string} id - Entry ID
 * @param {Object} approvalInfo - Approval metadata
 * @returns {Object} Result
 */
function approveCommand(id, approvalInfo = {}) {
  const entry = getEntry(id);
  
  if (!entry) {
    return { success: false, error: 'Command not found in queue' };
  }
  
  if (entry.status !== 'pending') {
    return { success: false, error: `Command is already ${entry.status}` };
  }
  
  entry.status = 'approved';
  entry.approved_at = new Date().toISOString();
  entry.approved_by = approvalInfo.approved_by || 'system';
  entry.approval_notes = approvalInfo.notes || '';
  
  updateEntry(entry);
  
  return {
    success: true,
    entry,
    message: 'Command approved and ready for execution'
  };
}

/**
 * Reject a queued command
 * @param {string} id - Entry ID
 * @param {Object} rejectionInfo - Rejection metadata
 * @returns {Object} Result
 */
function rejectCommand(id, rejectionInfo = {}) {
  const entry = getEntry(id);
  
  if (!entry) {
    return { success: false, error: 'Command not found in queue' };
  }
  
  if (entry.status !== 'pending') {
    return { success: false, error: `Command is already ${entry.status}` };
  }
  
  entry.status = 'rejected';
  entry.rejected_at = new Date().toISOString();
  entry.rejected_by = rejectionInfo.rejected_by || 'system';
  entry.rejection_reason = rejectionInfo.reason || 'No reason provided';
  
  updateEntry(entry);
  
  return {
    success: true,
    entry,
    message: 'Command rejected'
  };
}

/**
 * Mark command as executed
 * @param {string} id - Entry ID
 * @param {Object} result - Execution result
 */
function markExecuted(id, result) {
  const entry = getEntry(id);
  if (entry) {
    entry.status = 'executed';
    entry.executed_at = new Date().toISOString();
    entry.execution_result = result;
    updateEntry(entry);
  }
}

/**
 * Mark command as failed
 * @param {string} id - Entry ID
 * @param {string} error - Error message
 */
function markFailed(id, error) {
  const entry = getEntry(id);
  if (entry) {
    entry.status = 'failed';
    entry.failed_at = new Date().toISOString();
    entry.execution_error = error;
    updateEntry(entry);
  }
}

/**
 * List queue entries
 * @param {Object} filters - Filter options
 * @returns {Object[]} Filtered entries
 */
function listQueue(filters = {}) {
  const data = loadQueue();
  let entries = data.queue;
  
  if (filters.status) {
    entries = entries.filter(e => e.status === filters.status);
  }
  
  if (filters.risk_level) {
    entries = entries.filter(e => e.risk_level === filters.risk_level);
  }
  
  if (filters.since) {
    entries = entries.filter(e => new Date(e.created_at) >= new Date(filters.since));
  }
  
  // Sort by newest first
  entries.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  
  if (filters.limit) {
    entries = entries.slice(0, filters.limit);
  }
  
  return entries;
}

/**
 * Get queue statistics
 * @returns {Object} Statistics
 */
function getStats() {
  const data = loadQueue();
  const stats = {
    total: data.queue.length,
    pending: data.queue.filter(e => e.status === 'pending').length,
    approved: data.queue.filter(e => e.status === 'approved').length,
    rejected: data.queue.filter(e => e.status === 'rejected').length,
    executed: data.queue.filter(e => e.status === 'executed').length,
    failed: data.queue.filter(e => e.status === 'failed').length
  };
  
  // Risk breakdown
  const pending = data.queue.filter(e => e.status === 'pending');
  stats.risk_breakdown = {
    critical: pending.filter(e => e.risk_level === 'critical').length,
    dangerous: pending.filter(e => e.risk_level === 'dangerous').length,
    normal: pending.filter(e => e.risk_level === 'normal').length,
    safe: pending.filter(e => e.risk_level === 'safe').length
  };
  
  return stats;
}

/**
 * Clear old entries from queue
 * @param {number} days - Clear entries older than this many days
 * @returns {Object} Result
 */
function clearOldEntries(days) {
  const data = loadQueue();
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  
  const beforeCount = data.queue.length;
  data.queue = data.queue.filter(e => {
    const entryDate = new Date(e.created_at);
    // Keep pending entries regardless of age
    if (e.status === 'pending') return true;
    return entryDate >= cutoff;
  });
  
  saveQueue(data);
  
  const removed = beforeCount - data.queue.length;
  return {
    success: true,
    removed,
    remaining: data.queue.length,
    message: `Cleared ${removed} old entries`
  };
}

/**
 * Get entries awaiting execution (approved but not executed)
 * @returns {Object[]} Awaiting entries
 */
function getAwaitingExecution() {
  const data = loadQueue();
  return data.queue.filter(e => e.status === 'approved');
}

module.exports = {
  addToQueue,
  getEntry,
  approveCommand,
  rejectCommand,
  markExecuted,
  markFailed,
  listQueue,
  getStats,
  clearOldEntries,
  getAwaitingExecution
};
