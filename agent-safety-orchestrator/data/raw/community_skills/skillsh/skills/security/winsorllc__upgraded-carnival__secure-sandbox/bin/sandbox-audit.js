#!/usr/bin/env node
/**
 * sandbox-audit
 * 
 * CLI tool for viewing audit logs
 * 
 * Usage: sandbox-audit <command> [options]
 */

const path = require('path');
const auditor = require('../lib/auditor');

function showHelp() {
  console.log(`
Usage: sandbox-audit <command> [options]

Commands:
  log [options]           View audit log
  stats [options]         Show statistics
  export [options]        Export audit data
  files                   List audit files

Log options:
  --last N                Show last N entries
  --risk-level LEVEL      Filter by risk (safe, normal, dangerous, critical)
  --since DATE            Filter by date (YYYY-MM-DD)
  --command-pattern REGEX Filter by command pattern
  --status STATUS         Filter by status (success, failed, blocked)

Stats options:
  --period DAYS           Statistics period (default: 7)

Export options:
  --format FORMAT         Export format (json, jsonl, csv)
  --output FILE           Output file (default: stdout)

Examples:
  sandbox-audit log --last 20
  sandbox-audit log --risk-level dangerous
  sandbox-audit stats --period 30
  sandbox-audit export --format json --output /tmp/audit.json
`);
}

function logCommand(args) {
  const options = {};
  
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    
    if (arg === '--last' || arg === '-l') {
      options.limit = parseInt(args[++i]) || 20;
    } else if (arg === '--risk-level' || arg === '-r') {
      options.risk_level = args[++i];
    } else if (arg === '--since' || arg === '-s') {
      options.since = args[++i];
    } else if (arg === '--until' || arg === '-u') {
      options.until = args[++i];
    } else if (arg === '--command-pattern' || arg === '-p') {
      options.command_pattern = args[++i];
    } else if (arg === '--status') {
      options.status = args[++i];
    } else if (arg === '--json' || arg === '-j') {
      options.json = true;
    }
  }
  
  const entries = auditor.readAuditLog(options);
  
  if (options.json) {
    console.log(JSON.stringify(entries, null, 2));
    return;
  }
  
  if (entries.length === 0) {
    console.log('No audit entries found.');
    return;
  }
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                         AUDIT LOG');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log(`Showing ${entries.length} entries\\n`);
  
  entries.forEach((entry, idx) => {
    const date = new Date(entry.timestamp).toLocaleString();
    const type = entry.type?.toUpperCase() || 'UNKNOWN';
    
    console.log(`[${idx + 1}] ${date} | ${type}`);
    
    if (entry.command) {
      console.log(`    Command: ${entry.command.substring(0, 80)}${entry.command.length > 80 ? '...' : ''}`);
    }
    
    if (entry.risk_level) {
      console.log(`    Risk: ${entry.risk_level.toUpperCase()}`);
    }
    
    if (entry.status) {
      console.log(`    Status: ${entry.status}`);
    }
    
    if (entry.exit_code !== undefined) {
      console.log(`    Exit Code: ${entry.exit_code}`);
    }
    
    if (entry.duration_ms) {
      console.log(`    Duration: ${entry.duration_ms}ms`);
    }
    
    if (entry.approved_by) {
      console.log(`    Approved By: ${entry.approved_by}`);
    }
    
    console.log();
  });
  
  console.log('═══════════════════════════════════════════════════════════════');
}

function statsCommand(args) {
  let period = '7d';
  
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--period' || args[i] === '-p') {
      period = args[++i] || '7d';
    }
  }
  
  const days = parseInt(period) || 7;
  const since = new Date();
  since.setDate(since.getDate() - days);
  
  const stats = auditor.getAuditStats({ since: since.toISOString().split('T')[0] });
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                      AUDIT STATISTICS');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log();
  console.log(`Period: Last ${days} days`);
  console.log();
  console.log('Summary:');
  console.log(`  Total Commands: ${stats.total_commands}`);
  console.log(`  Classifications: ${stats.total_classifications}`);
  console.log(`  Queued: ${stats.total_queued}`);
  console.log();
  console.log('By Risk Level:');
  Object.entries(stats.by_risk_level).forEach(([level, count]) => {
    if (count > 0) {
      console.log(`  ${level}: ${count}`);
    }
  });
  console.log();
  console.log('By Status:');
  Object.entries(stats.by_status).forEach(([status, count]) => {
    if (count > 0) {
      console.log(`  ${status}: ${count}`);
    }
  });
  console.log();
  
  if (stats.time_range.start) {
    console.log('Time Range:');
    console.log(`  From: ${stats.time_range.start}`);
    console.log(`  To: ${stats.time_range.end}`);
  }
  console.log();
  console.log('═══════════════════════════════════════════════════════════════');
}

function exportCommand(args) {
  const options = {
    format: 'json',
    since: null,
    until: null
  };
  
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    
    if (arg === '--format' || arg === '-f') {
      options.format = args[++i] || 'json';
    } else if (arg === '--output' || arg === '-o') {
      options.output = args[++i];
    } else if (arg === '--since' || arg === '-s') {
      options.since = args[++i];
    } else if (arg === '--until' || arg === '-u') {
      options.until = args[++i];
    }
  }
  
  const validFormats = ['json', 'jsonl', 'csv'];
  if (!validFormats.includes(options.format)) {
    console.error(`Invalid format: ${options.format}. Valid: ${validFormats.join(', ')}`);
    process.exit(1);
  }
  
  const result = auditor.exportAudit(options);
  
  if (result.output_file) {
    console.log('═══════════════════════════════════════════════════════════════');
    console.log('                      EXPORT COMPLETE');
    console.log('═══════════════════════════════════════════════════════════════');
    console.log();
    console.log(`Format: ${options.format}`);
    console.log(`Entries: ${result.entries_count}`);
    console.log(`Output: ${result.output_file}`);
    console.log();
    console.log('═══════════════════════════════════════════════════════════════');
  } else {
    console.log(result.data);
  }
}

function filesCommand() {
  const files = auditor.listAuditFiles();
  
  if (files.length === 0) {
    console.log('No audit files found.');
    return;
  }
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                      AUDIT FILES');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log();
  console.log('Date         | Size (KB) | Modified');
  console.log('-------------|-----------|------------------------');
  
  files.forEach(file => {
    const size = (file.size_bytes / 1024).toFixed(2);
    const modified = new Date(file.modified).toLocaleString();
    console.log(`${file.date} | ${size.padStart(9)} | ${modified}`);
  });
  
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
    case 'log':
      logCommand(commandArgs);
      break;
    case 'stats':
      statsCommand(commandArgs);
      break;
    case 'export':
      exportCommand(commandArgs);
      break;
    case 'files':
      filesCommand();
      break;
    default:
      console.error(`Unknown command: ${command}`);
      showHelp();
      process.exit(1);
  }
}

main();
