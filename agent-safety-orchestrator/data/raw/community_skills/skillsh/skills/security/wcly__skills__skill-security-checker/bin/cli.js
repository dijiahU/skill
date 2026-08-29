#!/usr/bin/env node

const { checkSecurity, generateReport } = require('../dist/index.js');

const args = process.argv.slice(2);

function showHelp() {
  console.log(`
Usage: skill-security-checker <command> [options]

Commands:
  github <repo> [format]       Check a GitHub repository (owner/repo or full URL)
  local <path> [format]        Check a local folder
  npm <package-name> [format]  Check an npm package

Formats:
  json      JSON format output
  friendly  User-friendly output with emojis
  concise   Concise summary (default)

Options:
  --runtime    Enable runtime behavior monitoring
  -h, --help   Show this help message

Examples:
  skill-security-checker github octocat/Hello-World friendly
  skill-security-checker github https://github.com/octocat/Hello-World json
  skill-security-checker local /path/to/skill
  skill-security-checker npm lodash
`);
  process.exit(0);
}

if (args.includes('-h') || args.includes('--help')) {
  showHelp();
}

const command = args[0];
let target = args[1];
const format = args[2] || 'concise';
const enableRuntime = args.includes('--runtime');

if (!command || !target) {
  console.error('Error: Missing required arguments');
  console.error('Use --help for usage information');
  process.exit(1);
}

function normalizeGithubInput(input) {
  let repoUrl = input;
  if (input.startsWith('http://') || input.startsWith('https://')) {
    repoUrl = input.replace(/\/$/, '');
    if (repoUrl.endsWith('.git')) {
      repoUrl = repoUrl.replace(/\.git$/, '');
    }
  } else if (input.includes('/') && !input.includes('://')) {
    repoUrl = `https://github.com/${input.replace(/^\/+/, '')}`;
  }
  return repoUrl;
}

let inputType;
switch (command) {
  case 'github':
    inputType = 'github';
    target = normalizeGithubInput(target);
    break;
  case 'local':
    inputType = 'local';
    break;
  case 'npm':
    inputType = 'npm';
    break;
  default:
    console.error('Unknown command: ' + command);
    process.exit(1);
}

const options = {
  input: { type: inputType, path: target },
  outputFormat: format,
  enableRuntimeCheck: enableRuntime
};

(async () => {
  try {
    console.log('🔍 正在检查安全风险...\n');
    const result = await checkSecurity(options);
    const report = generateReport(result, options.outputFormat);
    console.log(report);
  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
})();
