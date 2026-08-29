#!/usr/bin/env node
import process from 'node:process';

import {
  assertRequired,
  bearerHeaders,
  getJson,
  loadMocaContext,
  parseArgs,
  printJson,
} from './moca-common.mjs';

function printHelp() {
  console.log(`Usage:
  node moca-poll-status.mjs --access-token <token>

Required:
  --access-token       Bearer token from moca-create-session

Optional:
  --interval           Polling interval in seconds (default 5)
  --timeout            Max polling duration in seconds (default 120)
  --status-url         Override the full status endpoint URL
  --vp-api-url         Override VP API base URL
  --config             Path to .air-wallet-config.json

Config fallback order:
  CLI flags -> environment variables -> .air-wallet-config.json -> sandbox defaults
`);
}

async function main() {
  const args = parseArgs();
  if (args.help) {
    printHelp();
    return;
  }

  const context = await loadMocaContext(args);
  const accessToken = assertRequired(
    args['access-token'] ?? process.env.MOCA_ACCESS_TOKEN,
    'Provide an access token via --access-token.',
  );

  const intervalMs = (Number(args.interval) || 5) * 1000;
  const timeoutMs = (Number(args.timeout) || 120) * 1000;
  const statusUrl =
    args['status-url'] ?? `${context.vpApiUrl}/vp/mocaproof/status`;

  const startTime = Date.now();
  let lastResult = null;

  console.log(`Polling ${statusUrl} every ${intervalMs / 1000}s (timeout ${timeoutMs / 1000}s)...\n`);

  while (Date.now() - startTime < timeoutMs) {
    try {
      lastResult = await getJson(statusUrl, bearerHeaders(accessToken));
    } catch (err) {
      console.error(`Poll error: ${err.message}`);
      lastResult = err.data ?? null;
    }

    if (lastResult) {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`[${elapsed}s] Status response:`);
      printJson(lastResult);
      console.log('');

      // Current default: any response with `apps` is treated as a usable result.
      if (lastResult.apps !== undefined) {
        console.log('Status endpoint returned a result.');
        break;
      }
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  if (Date.now() - startTime >= timeoutMs) {
    console.log('Polling timed out. Last result:');
    printJson(lastResult);
  }
}

main().catch((error) => {
  console.error(error?.stack || error);
  process.exit(1);
});
