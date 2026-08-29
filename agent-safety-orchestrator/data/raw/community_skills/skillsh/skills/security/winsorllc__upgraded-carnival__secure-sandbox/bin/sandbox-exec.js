#!/usr/bin/env node
/**
 * sandbox-exec
 * 
 * CLI tool to execute commands with safety checks
 * 
 * Usage: sandbox-exec "command to execute" [options]
 */

const path = require('path');
const sandbox = require('../lib/sandbox');

function parseArgs(args) {
  const options = {
    command: '',
    dry_run: false,
    require_approval: false,
    timeout: 60000,
    cwd: process.cwd(),
    json: false,
    approved_by: null
  };
  
  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    
    if (arg === '--dry-run' || arg === '-n') {
      options.dry_run = true;
    } else if (arg === '--require-approval' || arg === '-a') {
      options.require_approval = true;
    } else if (arg === '--timeout' || arg === '-t') {
      i++;
      options.timeout = parseInt(args[i]) || 60000;
    } else if (arg === '--cwd') {
      i++;
      options.cwd = args[i] || process.cwd();
    } else if (arg === '--json' || arg === '-j') {
      options.json = true;
    } else if (arg === '--approved-by') {
      i++;
      options.approved_by = args[i];
    } else if (arg === '--help' || arg === '-h') {
      showHelp();
      process.exit(0);
    } else if (!options.command) {
      options.command = args.slice(i).join(' ');
      break;
    }
    
    i++;
  }
  
  return options;
}

function showHelp() {
  console.log(`
Usage: sandbox-exec [options] "command to execute"

Options:
  -n, --dry-run          Show what would happen without executing
  -a, --require-approval Force approval even for safe commands
  -t, --timeout MS       Set execution timeout (default: 60000)
      --cwd PATH         Set working directory
      --approved-by USER Mark as pre-approved by user
  -j, --json             Output results as JSON
  -h, --help             Show this help

Examples:
  sandbox-exec "ls -la"
  sandbox-exec --dry-run "rm -rf node_modules"
  sandbox-exec --json "npm install express"
  sandbox-exec --approved-by admin "rm -rf /tmp/old"
`);
}

function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    showHelp();
    process.exit(1);
  }
  
  const options = parseArgs(args);
  
  if (!options.command) {
    console.error('Error: No command provided');
    process.exit(1);
  }
  
  const result = sandbox.executeSync({
    command: options.command,
    dry_run: options.dry_run,
    require_approval: options.require_approval,
    timeout: options.timeout,
    cwd: options.cwd,
    approved_by: options.approved_by
  });
  
  if (options.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    if (result.dry_run) {
      console.log('═══════════════════════════════════════════════════════════════');
      console.log('                         DRY RUN');
      console.log('═══════════════════════════════════════════════════════════════');
      console.log();
      console.log(`Command: ${result.command}`);
      console.log();
      console.log(`Risk Level: ${result.safety.risk_level.toUpperCase()}`);
      console.log(`Would Execute: ${result.would_execute ? 'YES' : 'NO'}`);
      console.log(`Would Queue: ${result.would_queue ? 'YES' : 'NO'}`);
      console.log();
      if (result.safety.risk_reasons.length > 0) {
        console.log('Risk Factors:');
        result.safety.risk_reasons.forEach(r => console.log(`  • ${r}`));
      }
      console.log();
      console.log('═══════════════════════════════════════════════════════════════');
    } else if (result.queued) {
      console.log('═══════════════════════════════════════════════════════════════');
      console.log('                   COMMAND QUEUED FOR APPROVAL');
      console.log('═══════════════════════════════════════════════════════════════');
      console.log();
      console.log(`Command: ${result.command}`);
      console.log(`Queue ID: ${result.queue_id}`);
      console.log();
      console.log(`Risk Level: ${result.safety.risk_level.toUpperCase()}`);
      if (result.safety.risk_reasons.length > 0) {
        console.log('Risk Factors:');
        result.safety.risk_reasons.forEach(r => console.log(`  • ${r}`));
      }
      console.log();
      console.log('To approve, run:');
      console.log(`  sandbox-queue approve ${result.queue_id}`);
      console.log();
      console.log('═══════════════════════════════════════════════════════════════');
    } else if (result.blocked) {
      console.log('═══════════════════════════════════════════════════════════════');
      console.log('                    COMMAND BLOCKED');
      console.log('═══════════════════════════════════════════════════════════════');
      console.log();
      console.log(`Command: ${result.command}`);
      console.log();
      console.log(`Risk Level: ${result.safety.risk_level.toUpperCase()}`);
      console.log('Error: This command poses a critical security risk and is blocked.');
      console.log();
      if (result.safety.safe_alternatives.length > 0) {
        console.log('Consider these alternatives:');
        result.safety.safe_alternatives.forEach(a => console.log(`  ${a}`));
      }
      console.log();
      console.log('═══════════════════════════════════════════════════════════════');
      process.exit(2);
    } else if (result.success) {
      console.log('═══════════════════════════════════════════════════════════════');
      console.log('                      EXECUTION SUCCESSFUL');
      console.log('═══════════════════════════════════════════════════════════════');
      console.log();
      console.log(`Command: ${result.command}`);
      console.log(`Duration: ${result.duration_ms}ms`);
      console.log(`Risk Level: ${result.safety.risk_level}`);
      console.log();
      if (result.stdout) {
        console.log('Output:');
        console.log(result.stdout);
      }
      console.log('═══════════════════════════════════════════════════════════════');
    } else {
      console.log('═══════════════════════════════════════════════════════════════');
      console.log('                      EXECUTION FAILED');
      console.log('═══════════════════════════════════════════════════════════════');
      console.log();
      console.log(`Command: ${result.command}`);
      console.log(`Error: ${result.error}`);
      console.log(`Exit Code: ${result.exit_code}`);
      console.log();
      if (result.stderr) {
        console.log('Stderr:', result.stderr);
      }
      console.log('═══════════════════════════════════════════════════════════════');
      process.exit(1);
    }
  }
  
  process.exit(result.success ? 0 : 1);
}

main();
