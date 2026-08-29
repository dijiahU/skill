#!/usr/bin/env node
/**
 * sandbox-allowlist
 * 
 * CLI tool for managing command allowlist
 * 
 * Usage: sandbox-allowlist <command> [options]
 */

const path = require('path');
const allowlist = require('../lib/allowlist');

function showHelp() {
  console.log(`
Usage: sandbox-allowlist <command> [options]

Commands:
  list                    List all allowlisted patterns
  add "pattern"           Add a pattern to allowlist
  remove "pattern"        Remove a pattern from allowlist
  test "command"          Test if a command matches allowlist
  reset                   Reset to default allowlist

Add options:
  --description "text"    Description of the pattern
  --auto-approve BOOL     Auto-approve matching commands (default: true)

Examples:
  sandbox-allowlist list
  sandbox-allowlist add "npm install" --description "Safe install"
  sandbox-allowlist add "git fetch" --auto-approve false
  sandbox-allowlist remove "npm install"
  sandbox-allowlist test "npm install express"
  sandbox-allowlist reset
`);
}

function listCommand() {
  const { defaults, custom } = allowlist.listAllowlist();
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                      COMMAND ALLOWLIST');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log();
  
  console.log('Default Patterns (read-only):');
  console.log('-'.repeat(60));
  defaults.forEach(entry => {
    console.log(`  Pattern: ${entry.pattern}`);
    console.log(`  Description: ${entry.description}`);
    console.log(`  Auto-approve: ${entry.auto_approve ? 'Yes' : 'No'}`);
    console.log();
  });
  
  if (custom.length > 0) {
    console.log('Custom Patterns:');
    console.log('-'.repeat(60));
    custom.forEach(entry => {
      console.log(`  Pattern: ${entry.pattern}`);
      console.log(`  Description: ${entry.description}`);
      console.log(`  Auto-approve: ${entry.auto_approve ? 'Yes' : 'No'}`);
      if (entry.added_at) {
        console.log(`  Added: ${new Date(entry.added_at).toLocaleString()}`);
      }
      console.log();
    });
  } else {
    console.log('No custom patterns defined.');
    console.log();
  }
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log(`Total: ${defaults.length} defaults + ${custom.length} custom = ${defaults.length + custom.length} patterns`);
  console.log('═══════════════════════════════════════════════════════════════');
}

function addCommand(args) {
  let pattern = args[0];
  let description = 'User-defined pattern';
  let autoApprove = true;
  
  // Handle quoted pattern
  if (!pattern || pattern.startsWith('--')) {
    // Find quoted pattern
    const fullArgs = process.argv.slice(3).join(' ');
    const match = fullArgs.match(/^"([^"]+)"/);
    if (match) {
      pattern = match[1];
    } else {
      console.error('Error: No pattern provided');
      process.exit(1);
    }
  }
  
  // Parse options
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--description' || args[i] === '-d') {
      description = args[++i] || description;
    } else if (args[i] === '--auto-approve') {
      const val = args[++i];
      if (val) {
        autoApprove = val.toLowerCase() === 'true';
      } else {
        autoApprove = true;
      }
    }
  }
  
  const result = allowlist.addToAllowlist({
    pattern,
    description,
    auto_approve: autoApprove
  });
  
  if (result.success) {
    console.log('═══════════════════════════════════════════════════════════════');
    console.log('                     PATTERN ADDED');
    console.log('═══════════════════════════════════════════════════════════════');
    console.log();
    console.log(`Pattern: ${pattern}`);
    console.log(`Description: ${description}`);
    console.log(`Auto-approve: ${autoApprove ? 'Yes' : 'No'}`);
    console.log();
    console.log(result.message);
    console.log();
    console.log('═══════════════════════════════════════════════════════════════');
  } else {
    console.error(`Error: ${result.error}`);
    process.exit(1);
  }
}

function removeCommand(args) {
  let pattern = args[0];
  
  // Handle quoted pattern
  if (!pattern || pattern.startsWith('--')) {
    const fullArgs = process.argv.slice(3).join(' ');
    const match = fullArgs.match(/^"([^"]+)"/);
    if (match) {
      pattern = match[1];
    } else {
      console.error('Error: No pattern provided');
      process.exit(1);
    }
  }
  
  const result = allowlist.removeFromAllowlist(pattern);
  
  if (result.success) {
    console.log('═══════════════════════════════════════════════════════════════');
    console.log('                    PATTERN REMOVED');
    console.log('═══════════════════════════════════════════════════════════════');
    console.log();
    console.log(`Pattern: ${pattern}`);
    console.log();
    console.log(result.message);
    console.log();
    console.log('═══════════════════════════════════════════════════════════════');
  } else {
    console.error(`Error: ${result.error}`);
    process.exit(1);
  }
}

function testCommand(args) {
  let command = args[0];
  
  // Handle quoted command
  if (!command) {
    const fullArgs = process.argv.slice(3).join(' ');
    const match = fullArgs.match(/^"([^"]+)"/);
    if (match) {
      command = match[1];
    } else {
      console.error('Error: No command provided');
      process.exit(1);
    }
  }
  
  const result = allowlist.testAllowlist(command);
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                    ALLOWLIST TEST');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log();
  console.log(`Command: ${command}`);
  console.log();
  
  if (result.matched) {
    console.log('Result: MATCHED ✓');
    console.log(`Pattern: ${result.pattern}`);
    console.log(`Description: ${result.description}`);
    console.log(`Auto-approve: ${result.auto_approve ? 'Yes' : 'No'}`);
  } else {
    console.log('Result: NOT MATCHED ✗');
    console.log('This command will require classification.');
  }
  
  console.log();
  console.log('═══════════════════════════════════════════════════════════════');
}

function resetCommand() {
  const result = allowlist.resetAllowlist();
  
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                    ALLOWLIST RESET');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log();
  console.log(result.message);
  console.log();
  console.log(`Default patterns restored: ${result.defaults_count}`);
  console.log('Custom patterns have been cleared.');
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
    case 'ls':
      listCommand();
      break;
    case 'add':
      addCommand(commandArgs);
      break;
    case 'remove':
    case 'rm':
      removeCommand(commandArgs);
      break;
    case 'test':
      testCommand(commandArgs);
      break;
    case 'reset':
      resetCommand();
      break;
    default:
      console.error(`Unknown command: ${command}`);
      showHelp();
      process.exit(1);
  }
}

main();
