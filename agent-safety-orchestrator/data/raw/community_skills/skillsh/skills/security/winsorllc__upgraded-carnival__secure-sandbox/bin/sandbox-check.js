#!/usr/bin/env node
/**
 * sandbox-check
 * 
 * CLI tool to check command safety before execution
 * 
 * Usage: sandbox-check "command to check"
 */

const path = require('path');
const sandbox = require('../lib/sandbox');

function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log('Usage: sandbox-check "command to check"');
    console.log('       sandbox-check --json "command"');
    process.exit(1);
  }
  
  const useJson = args[0] === '--json' || args[0] === '-j';
  const commandIndex = useJson ? 1 : 0;
  const command = args.slice(commandIndex).join(' ');
  
  if (!command) {
    console.error('Error: No command provided');
    process.exit(1);
  }
  
  const result = sandbox.check(command, {
    cwd: process.cwd(),
    user: process.env.USER
  });
  
  if (useJson) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log('═══════════════════════════════════════════════════════════════');
    console.log('                   Command Safety Analysis');
    console.log('═══════════════════════════════════════════════════════════════');
    console.log();
    console.log(`Command: ${result.command}`);
    console.log();
    console.log(`Risk Level: ${result.risk_level.toUpperCase()}`);
    console.log(`Risk Score: ${result.risk_score}/100`);
    console.log(`Requires Approval: ${result.requires_approval ? 'YES ⚠️' : 'NO ✓'}`);
    console.log(`Suggested Action: ${result.suggested_action}`);
    console.log(`Allowlisted: ${result.allowlisted ? 'YES' : 'NO'}`);
    console.log();
    
    if (result.risk_reasons.length > 0) {
      console.log('Risk Factors:');
      result.risk_reasons.forEach(reason => {
        console.log(`  • ${reason}`);
      });
      console.log();
    }
    
    if (result.recommendations.length > 0) {
      console.log('Recommendations:');
      result.recommendations.forEach(rec => {
        console.log(`  • ${rec}`);
      });
      console.log();
    }
    
    if (result.safe_alternatives.length > 0) {
      console.log('Safer Alternatives:');
      result.safe_alternatives.forEach(alt => {
        console.log(`  ${alt}`);
      });
      console.log();
    }
    
    console.log('Context:');
    console.log(`  Working Directory: ${result.context.cwd}`);
    console.log(`  User: ${result.context.user}`);
    console.log(`  Timestamp: ${result.context.timestamp}`);
    console.log();
    console.log('═══════════════════════════════════════════════════════════════');
  }
  
  // Exit with different codes based on risk
  if (result.risk_level === 'critical') process.exit(2);
  if (result.risk_level === 'dangerous') process.exit(3);
  process.exit(0);
}

main();
