#!/usr/bin/env node

/**
 * Detection script for GPC CLI.
 * Returns JSON with installation status, version, auth state, and config.
 * Used by Claude Code skill system for deterministic environment detection.
 *
 * Exit codes:
 *   0 — GPC detected (may or may not be authenticated)
 *   1 — GPC not found
 */

import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

function run(cmd) {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 10000 }).trim();
  } catch {
    return null;
  }
}

const result = {
  installed: false,
  version: null,
  installMethod: null,
  authStatus: null,
  authMethod: null,
  profile: null,
  envAuth: false,
  defaultApp: null,
  configFile: null,
  nodeVersion: process.version,
};

// Check if gpc is installed globally
const versionOutput = run("gpc --version");
if (!versionOutput) {
  // Try npx
  const npxVersion = run("npx gpc --version 2>/dev/null");
  if (!npxVersion) {
    console.log(JSON.stringify(result, null, 2));
    process.exit(1);
  }
  result.version = npxVersion;
  result.installed = true;
  result.installMethod = "npx";
} else {
  result.version = versionOutput;
  result.installed = true;
  result.installMethod = "global";
}

// Check auth status
const authOutput = run("gpc auth status --json 2>/dev/null");
if (authOutput) {
  try {
    const auth = JSON.parse(authOutput);
    result.authStatus = auth.status || "unknown";
    result.authMethod = auth.method || null;
    result.profile = auth.profile || null;
  } catch {
    result.authStatus = "parse_error";
  }
}

// Check for env-based auth
if (process.env.GPC_SERVICE_ACCOUNT) {
  result.envAuth = true;
}

// Check default app
const configOutput = run("gpc config get app --json 2>/dev/null");
if (configOutput) {
  try {
    const config = JSON.parse(configOutput);
    result.defaultApp = config.value || config.app || null;
  } catch {
    result.defaultApp = configOutput || null;
  }
}

// Check for .gpcrc.json in current directory
const rcPath = join(process.cwd(), ".gpcrc.json");
if (existsSync(rcPath)) {
  result.configFile = rcPath;
}

console.log(JSON.stringify(result, null, 2));
process.exit(0);
