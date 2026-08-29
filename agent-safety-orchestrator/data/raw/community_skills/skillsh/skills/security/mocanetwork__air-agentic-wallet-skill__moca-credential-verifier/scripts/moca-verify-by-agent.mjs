#!/usr/bin/env node
import process from 'node:process';

import {
  assertRequired,
  bearerHeaders,
  loadMocaContext,
  normalizeVerifyResponse,
  parseArgs,
  postJson,
  printJson,
} from './moca-common.mjs';

function printHelp() {
  console.log(`Usage:
  node moca-verify-by-agent.mjs --access-token <token> --program-id <programId>

Required:
  --access-token       Bearer token from moca-create-session
  --program-id         Verification program ID to verify against

Optional:
  --issue-url          Issuance URL to display when no credential is found
  --response-mode      Response mode: zkp | selective_disclosure | query_match (default: query_match)
  --disclose-fields    Comma-separated fields for selective_disclosure mode
  --include-zkp        Include ZKP proofs in selective_disclosure mode (true/false)
  --chain-api-url      Override Moca Chain API base URL
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
  const programId = assertRequired(
    args['program-id'] ?? args._[0],
    'Provide a program ID via --program-id.',
  );

  const responseMode = args['response-mode'] ?? 'query_match';
  const body = { programId, responseMode };
  if (
    responseMode === 'selective_disclosure' &&
    args['disclose-fields']
  ) {
    body.discloseFields = args['disclose-fields'].split(',');
  }
  if (responseMode === 'selective_disclosure' && args['include-zkp'] === 'true') {
    body.includeZkp = true;
  }

  const url = `${context.mocaChainApiUrl}/credentials/verify-by-agent`;

  console.log('Verifying....');

  let rawResponse;
  try {
    rawResponse = await postJson(url, body, bearerHeaders(accessToken));
  } catch (err) {
    if (err.data) {
      rawResponse = err.data;
    } else {
      throw err;
    }
  }

  const result = normalizeVerifyResponse(rawResponse);

  switch (result.normalized) {
    case 'compliant':
      console.log('Verification result: COMPLIANT');
      break;
    case 'non_compliant':
      console.log('Sorry, not compliant');
      break;
    case 'processing':
      console.log('Verification accepted, processing on-chain...');
      break;
    case 'no_vc': {
      console.log('No credential found for this program.');
      const issueUrl = args['issue-url'];
      if (issueUrl) {
        console.log(`Issue your credential here: ${issueUrl}`);
      }
      break;
    }
    default:
      if (result.normalized.startsWith('status_bucket:')) {
        console.log(`Verification returned status: ${result.status}`);
      } else if (result.normalized.startsWith('unknown_failure_code:')) {
        console.log(`Verification failed with code: ${result.code}`);
      } else {
        console.log('Unexpected response from verify-by-agent:');
      }
      break;
  }

  printJson(result);
}

main().catch((error) => {
  console.error(error?.stack || error);
  process.exit(1);
});
