#!/usr/bin/env node
import process from 'node:process';

import {
  assertRequired,
  buildSignedMessage,
  loadAgentKeys,
  loadMocaContext,
  parseArgs,
  postJson,
  printJson,
} from './moca-common.mjs';

function printHelp() {
  console.log(`Usage:
  node moca-create-session.mjs --program-id <programId>

Required:
  --program-id         The verification program ID to scope the session to

Optional:
  --config             Path to .air-wallet-config.json
  --private-key        Path to agent P-256 private key PEM
  --public-key         Path to agent public key PEM
  --user-id            Override userId
  --partner-id         Override partnerId
  --air-api-url        Override AIR API base URL

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
  const keys = await loadAgentKeys(args);
  const programId = assertRequired(
    args['program-id'] ?? args._[0],
    'Provide a program ID via --program-id.',
  );

  const signedMessage = buildSignedMessage({
    userId: context.userId,
    publicKeyPem: keys.publicKeyPem,
    privateKeyPem: keys.privateKeyPem,
  });

  const scope = `${programId},${context.partnerId}`;
  const url = `${context.airApiUrl}/auth/agent/session`;

  const result = await postJson(url, { signedMessage, scope });

  printJson({
    accessToken: result.accessToken,
    user: result.user,
    scope,
    airApiUrl: context.airApiUrl,
  });
}

main().catch((error) => {
  console.error(error?.stack || error);
  process.exit(1);
});
