/**
 * Sandbox Execution Engine
 * 
 * Main orchestration module that coordinates:
 * - Classification
 * - Allowlist checking
 * - Queue management
 * - Audit logging
 * - Command execution
 */

const { execSync, spawn } = require('child_process');
const path = require('path');

const classifier = require('./classifier');
const allowlist = require('./allowlist');
const queue = require('./queue');
const auditor = require('./auditor');

/**
 * Configuration
 */
const CONFIG = {
  // Security level: 'permissive', 'normal', 'strict', 'deny'
  security_level: process.env.SANDBOX_LEVEL || 'normal',
  
  // Auto-approve safe commands
  auto_approve_safe: process.env.SANDBOX_AUTO_APPROVE_SAFE !== 'false',
  
  // Block critical commands
  block_critical: process.env.SANDBOX_BLOCK_CRITICAL !== 'false',
  
  // Default timeout (ms)
  default_timeout: parseInt(process.env.SANDBOX_TIMEOUT) || 60000,
  
  // Working directory
  cwd: process.env.SANDBOX_CWD || process.cwd()
};

/**
 * Check command safety
 * @param {string} command - Command to check
 * @param {Object} context - Execution context
 * @returns {Object} Safety check result
 */
function check(command, context = {}) {
  const classification = classifier.classifyCommand(command, context);
  const allowlistCheck = allowlist.testAllowlist(command);
  
  // Allowlisted commands get lowered risk if auto_approve is enabled
  let adjustedRisk = classification.risk_level;
  let requiresApproval = classification.requires_approval;
  let action = classification.suggested_action;
  
  if (allowlistCheck.matched && allowlistCheck.auto_approve) {
    if (classification.risk_level === 'safe' || classification.risk_level === 'normal') {
      adjustedRisk = 'safe';
      requiresApproval = false;
      action = 'execute';
    }
  }
  
  // Critical commands always require special handling
  if (classification.risk_level === 'critical' && CONFIG.block_critical) {
    adjustedRisk = 'critical';
    requiresApproval = true;
    action = 'block';
  }
  
  const result = {
    command,
    original_risk: classification.risk_level,
    risk_level: adjustedRisk,
    risk_score: classification.risk_score,
    risk_reasons: classification.risk_reasons,
    allowlisted: allowlistCheck.matched,
    allowlist_pattern: allowlistCheck.pattern,
    requires_approval: requiresApproval,
    suggested_action: action,
    recommendations: classifier.analyzeRisk(command).recommendations,
    safe_alternatives: classifier.analyzeRisk(command).safe_alternatives,
    context: {
      cwd: context.cwd || CONFIG.cwd,
      user: context.user || process.env.USER || 'unknown',
      timestamp: new Date().toISOString()
    }
  };
  
  // Log classification
  auditor.logClassification(result);
  
  return result;
}

/**
 * Execute a command
 * @param {Object} options - Execution options
 * @returns {Promise<Object>} Execution result
 */
async function execute(options) {
  const {
    command,
    timeout = CONFIG.default_timeout,
    cwd = CONFIG.cwd,
    env = {},
    dry_run = false,
    require_approval = false,
    approved_by = null,
    queue_id = null,
    capture_output = true
  } = options;
  
  const context = {
    cwd,
    user: process.env.USER || 'unknown',
    ...options.context
  };
  
  // Check safety
  const safety = check(command, context);
  
  // Handle dry run mode
  if (dry_run) {
    return {
      success: true,
      dry_run: true,
      command,
      safety,
      message: 'Dry run - command would be analyzed and potentially queued',
      would_execute: !safety.requires_approval || (approved_by !== null),
      would_queue: safety.requires_approval && !approved_by
    };
  }
  
  // Block critical commands
  if (safety.risk_level === 'critical' && CONFIG.block_critical) {
    const result = {
      success: false,
      error: 'Command blocked: critical security risk',
      command,
      risk_level: 'critical',
      safety,
      blocked: true
    };
    
    auditor.logExecution({
      command,
      risk_level: 'critical',
      risk_score: safety.risk_score,
      risk_reasons: safety.risk_reasons,
      context,
      status: 'blocked',
      exit_code: -1,
      queue_id
    });
    
    return result;
  }
  
  // Queue dangerous commands requiring approval
  if (safety.requires_approval && !approved_by && !require_approval) {
    const entry = queue.addToQueue({
      command,
      risk_level: safety.risk_level,
      risk_score: safety.risk_score,
      risk_reasons: safety.risk_reasons,
      context
    });
    
    auditor.logQueueEntry(entry);
    
    return {
      success: false,
      queued: true,
      queue_id: entry.id,
      command,
      safety,
      message: 'Command queued for approval',
      approval_instructions: `Run: sandbox-queue approve ${entry.id}`
    };
  }
  
  // Execute the command
  const startTime = Date.now();
  
  try {
    let result;
    
    if (capture_output) {
      // Use execSync for simple command capture
      const output = execSync(command, {
        cwd,
        timeout,
        encoding: 'utf8',
        env: { ...process.env, ...env },
        maxBuffer: 1024 * 1024 // 1MB
      });
      
      result = {
        success: true,
        command,
        stdout: output,
        stderr: '',
        exit_code: 0,
        duration_ms: Date.now() - startTime
      };
    } else {
      // For long-running commands without capture
      const child = spawn(command, {
        cwd,
        env: { ...process.env, ...env },
        shell: true,
        detached: false
      });
      
      await new Promise((resolve, reject) => {
        const t = setTimeout(() => {
          child.kill('SIGTERM');
          reject(new Error(`Command timed out after ${timeout}ms`));
        }, timeout);
        
        child.on('close', (code) => {
          clearTimeout(t);
          result = {
            success: code === 0,
            command,
            exit_code: code,
            duration_ms: Date.now() - startTime
          };
          resolve();
        });
        
        child.on('error', (err) => {
          clearTimeout(t);
          reject(err);
        });
      });
    }
    
    // Mark queue entry as executed if applicable
    if (queue_id) {
      queue.markExecuted(queue_id, result);
    }
    
    // Log execution
    auditor.logExecution({
      command,
      risk_level: safety.risk_level,
      risk_score: safety.risk_score,
      risk_reasons: safety.risk_reasons,
      context,
      status: 'success',
      exit_code: result.exit_code || 0,
      stdout: result.stdout,
      stderr: result.stderr,
      duration_ms: result.duration_ms,
      approved_by,
      queue_id
    });
    
    return {
      ...result,
      safety,
      executed: true
    };
    
  } catch (err) {
    const result = {
      success: false,
      command,
      error: err.message,
      stderr: err.stderr?.toString(),
      exit_code: err.status || -1,
      duration_ms: Date.now() - startTime
    };
    
    // Mark queue entry as failed if applicable
    if (queue_id) {
      queue.markFailed(queue_id, err.message);
    }
    
    // Log execution
    auditor.logExecution({
      command,
      risk_level: safety.risk_level,
      risk_score: safety.risk_score,
      risk_reasons: safety.risk_reasons,
      context,
      status: 'failed',
      exit_code: err.status || -1,
      stderr: err.message,
      duration_ms: result.duration_ms,
      approved_by,
      queue_id
    });
    
    return {
      ...result,
      safety,
      executed: false
    };
  }
}

/**
 * Execute a command synchronously (convenience wrapper)
 * @param {Object} options - Execution options
 * @returns {Object} Execution result
 */
function executeSync(options) {
  // For simplicity in testing, we use a synchronous approach
  const { command, timeout = CONFIG.default_timeout, cwd = CONFIG.cwd, env = {}, dry_run = false } = options;
  const context = { cwd, user: process.env.USER || 'unknown' };
  
  // Check safety
  const safety = check(command, context);
  
  // Handle dry run mode
  if (dry_run) {
    return {
      success: true,
      dry_run: true,
      command,
      safety,
      message: 'Dry run - command would be analyzed and potentially queued',
      would_execute: !safety.requires_approval || (options.approved_by !== null),
      would_queue: safety.requires_approval && !options.approved_by
    };
  }
  
  // Handle critical/block
  if (safety.risk_level === 'critical' && CONFIG.block_critical && !options.approved_by) {
    return {
      success: false,
      error: 'Command blocked: critical security risk',
      command,
      blocked: true,
      safety
    };
  }
  
  // Handle requiring approval
  if (safety.requires_approval && !options.approved_by && !options.require_approval) {
    const entry = queue.addToQueue({
      command,
      risk_level: safety.risk_level,
      risk_score: safety.risk_score,
      risk_reasons: safety.risk_reasons,
      context
    });
    
    auditor.logQueueEntry(entry);
    
    return {
      success: false,
      queued: true,
      queue_id: entry.id,
      command,
      safety,
      message: 'Command queued for approval'
    };
  }
  
  // Execute
  const startTime = Date.now();
  
  try {
    const output = execSync(command, {
      cwd,
      timeout,
      encoding: 'utf8',
      env: { ...process.env, ...env },
      maxBuffer: 1024 * 1024
    });
    
    const result = {
      success: true,
      command,
      stdout: output,
      stderr: '',
      exit_code: 0,
      duration_ms: Date.now() - startTime,
      safety,
      executed: true
    };
    
    auditor.logExecution({
      command,
      risk_level: safety.risk_level,
      risk_score: safety.risk_score,
      risk_reasons: safety.risk_reasons,
      context,
      status: 'success',
      exit_code: 0,
      stdout: output,
      duration_ms: result.duration_ms,
      approved_by: options.approved_by
    });
    
    return result;
    
  } catch (err) {
    const result = {
      success: false,
      command,
      error: err.message,
      stderr: err.stderr?.toString(),
      stdout: err.stdout?.toString(),
      exit_code: err.status || -1,
      duration_ms: Date.now() - startTime,
      safety,
      executed: false
    };
    
    auditor.logExecution({
      command,
      risk_level: safety.risk_level,
      risk_score: safety.risk_score,
      risk_reasons: safety.risk_reasons,
      context,
      status: 'failed',
      exit_code: err.status || -1,
      stderr: err.stderr?.toString(),
      duration_ms: result.duration_ms,
      approved_by: options.approved_by
    });
    
    return result;
  }
}

module.exports = {
  check,
  execute,
  executeSync,
  classifier,
  allowlist,
  queue,
  auditor,
  CONFIG
};
