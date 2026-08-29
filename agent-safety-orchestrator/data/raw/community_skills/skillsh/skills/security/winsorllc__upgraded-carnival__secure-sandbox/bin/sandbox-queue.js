#!/usr/bin/env node
/**
 * sandbox-queue
 * 
 * CLI tool for managing the approval queue
 * 
 * Usage: sandbox-queue [command] [options]
 */

const path = require('path');
const queue = require('../lib/queue');

function showHelp() {
  console.log(`
Usage: sandbox-queue <command> [options]

Commands:
  list [status]         List queue entries (default: pending)
  approve <id>         Approve a queued command
  reject <id>         Reject a queued command
  clear --older-than N  Clear entries older than N days
  stats                 Show queue statistics

Status filters for list:
  all, pending, approved, rejected, executed, failed

Examples:
  sandbox-queue list
  sandbox-queue list pending
  sandbox-queue approve cmd_abc123
  sandbox-queue reject cmd_abc123 --reason "Too risky"
  sandbox-queue clear --older-than 7
  sandbox-queue stats
`);
}

function formatEntry(entry) {
  const created = new Date(entry.created_at).toLocaleString();
  return `
  ID: ${entry.id}
  Command: ${entry.command}
  Risk: ${entry.risk_level.toUpperCase()} (${entry.risk_score}/100)
  Status: ${entry.status}
  Created: ${created}
  ${entry.risk_reasons.length > 0 ? '\n  Risk Factors:\n' + entry.risk_reasons.map(r => '    • ' + r.replace('\\', '')).join('\\n') : ''}
`;
}

function listCommand(args) {
  const status = args[0] || 'pending';
  const validStatuses = ['all', 'pending', 'approved', 'rejected', 'executed', 'failed'];
  
  if (!validStatuses.includes(status)) {
    console.error(`Invalid status: ${status}. Valid: ${validStatuses.join(', ')}`);
    process.exit(1);
  }
  
  const entries = queue.listQueue({ 
    status: status === 'all' ? null : status,
    limit: 50
  });
  
  if (entries.length === 0) {
    console.log(`No ${status} entries in queue.`);
    return;
  }
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log(`                   Queue Entries (${status.toUpperCase()})`);
  console.log('═══════════════════════════════════════════════════════════════');
  console.log(`Total: ${entries.length} entries\\n`);
  
  entries.forEach(entry => {
    console.log(formatEntry(entry));
  });
  
  console.log('═══════════════════════════════════════════════════════════════');
}

function approveCommand(args) {
  const id = args[0];
  
  if (!id) {
    console.error('Error: No command ID provided');
    process.exit(1);
  }
  
  // Find approved_by flag
  let approvedBy = process.env.USER || 'cli';
  const approvedByIndex = args.indexOf('--approved-by');
  if (approvedByIndex !== -1 && args[approvedByIndex + 1]) {
    approvedBy = args[approvedByIndex + 1];
  }
  
  const result = queue.approveCommand(id, { 
    approved_by: approvedBy,
    notes: args.join(' ')
  });
  
  if (result.success) {
    console.log('═══════════════════════════════════════════════════════════════');
    console.log('                     COMMAND APPROVED');
    console.log('═══════════════════════════════════════════════════════════════');
    console.log();
    console.log(`ID: ${result.entry.id}`);
    console.log(`Command: ${result.entry.command}`);
    console.log(`Approved by: ${approvedBy}`);
    console.log(`Approved at: ${result.entry.approved_at}`);
    console.log();
    console.log('The command is now ready for execution.');
    console.log();
    console.log('═══════════════════════════════════════════════════════════════');
  } else {
    console.error(`Error: ${result.error}`);
    process.exit(1);
  }
}

function rejectCommand(args) {
  const id = args[0];
  
  if (!id) {
    console.error('Error: No command ID provided');
    process.exit(1);
  }
  
  // Find reason flag
  let reason = 'Rejected via CLI';
  const reasonIndex = args.indexOf('--reason');
  if (reasonIndex !== -1 && args[reasonIndex + 1]) {
    reason = args.slice(reasonIndex + 1).join(' ');
  }
  
  // Find rejected_by flag
  let rejectedBy = process.env.USER || 'cli';
  const rejectedByIndex = args.indexOf('--rejected-by');
  if (rejectedByIndex !== -1 && args[rejectedByIndex + 1]) {
    rejectedBy = args[rejectedByIndex + 1];
  }
  
  const result = queue.rejectCommand(id, { 
    rejected_by: rejectedBy,
    reason
  });
  
  if (result.success) {
    console.log('═══════════════════════════════════════════════════════════════');
    console.log('                     COMMAND REJECTED');
    console.log('═══════════════════════════════════════════════════════════════');
    console.log();
    console.log(`ID: ${result.entry.id}`);
    console.log(`Command: ${result.entry.command}`);
    console.log(`Rejected by: ${rejectedBy}`);
    console.log(`Reason: ${reason}`);
    console.log();
    console.log('═══════════════════════════════════════════════════════════════');
  } else {
    console.error(`Error: ${result.error}`);
    process.exit(1);
  }
}

function clearCommand(args) {
  const olderThanIndex = args.indexOf('--older-than');
  
  if (olderThanIndex === -1 || !args[olderThanIndex + 1]) {
    console.error('Error: --older-than flag required');
    console.error('Usage: sandbox-queue clear --older-than <days>');
    process.exit(1);
  }
  
  const days = parseInt(args[olderThanIndex + 1]);
  if (isNaN(days) || days < 1) {
    console.error('Error: Invalid number of days');
    process.exit(1);
  }
  
  const result = queue.clearOldEntries(days);
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                     QUEUE CLEANUP COMPLETE');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log();
  console.log(`Cleared: ${result.removed} entries`);
  console.log(`Remaining: ${result.remaining} entries`);
  console.log();
  console.log('═══════════════════════════════════════════════════════════════');
}

function statsCommand() {
  const stats = queue.getStats();
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                     QUEUE STATISTICS');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log();
  console.log('Overview:');
  console.log(`  Total Entries: ${stats.total}`);
  console.log(`  Pending: ${stats.pending}`);
  console.log(`  Approved: ${stats.approved}`);
  console.log(`  Rejected: ${stats.rejected}`);
  console.log(`  Executed: ${stats.executed}`);
  console.log(`  Failed: ${stats.failed}`);
  console.log();
  console.log('Pending Risk Breakdown:');
  console.log(`  Critical: ${stats.risk_breakdown.critical}`);
  console.log(`  Dangerous: ${stats.risk_breakdown.dangerous}`);
  console.log(`  Normal: ${stats.risk_breakdown.normal}`);
  console.log(`  Safe: ${stats.risk_breakdown.safe}`);
  console.log();
  console.log('═══════════════════════════════════════════════════════════════');
}

function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    showHelp();
    process.exit(0);
  }
  
  const command = args[0];
  const commandArgs = args.slice(1);
  
  switch (command) {
    case 'list':
      listCommand(commandArgs);
      break;
    case 'approve':
      approveCommand(commandArgs);
      break;
    case 'reject':
      rejectCommand(commandArgs);
      break;
    case 'clear':
      clearCommand(commandArgs);
      break;
    case 'stats':
      statsCommand();
      break;
    default:
      console.error(`Unknown command: ${command}`);
      showHelp();
      process.exit(1);
  }
}

main();
