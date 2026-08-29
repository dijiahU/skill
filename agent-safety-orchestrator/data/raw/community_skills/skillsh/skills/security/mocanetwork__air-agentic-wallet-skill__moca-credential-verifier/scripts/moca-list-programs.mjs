#!/usr/bin/env node
import process from 'node:process';

import {
  bearerHeaders,
  getJson,
  loadMocaContext,
  parseArgs,
  printJson,
} from './moca-common.mjs';

function printHelp() {
  console.log(`Usage:
  node moca-list-programs.mjs
  node moca-list-programs.mjs --access-token <token>

Optional:
  --access-token       Bearer token from moca-create-session (enables personalized view)
  --page               Page number (default 1)
  --limit              Items per page (default 20)
  --category           Filter by category
  --issuer             Filter by issuer name
  --verified           true/false filter (requires token for meaningful results)
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

  // userId is not required for public listing.
  const context = await loadMocaContext(args, { requireUserId: false });
  const accessToken = args['access-token'] ?? process.env.MOCA_ACCESS_TOKEN;

  const page = args.page ?? '1';
  const limit = args.limit ?? '20';
  const params = new URLSearchParams({ page, limit });
  if (args.category) params.set('category', args.category);
  if (args.issuer) params.set('issuer', args.issuer);
  if (args.verified !== undefined) params.set('verified', String(args.verified));

  const url = `${context.vpApiUrl}/vp/mocaproof/search?${params}`;
  const headers = accessToken ? bearerHeaders(accessToken) : {};
  const result = await getJson(url, headers);

  const { data, pagination, meta } = result;
  const mode = accessToken
    ? 'personalized (with access token)'
    : 'public (without access token)';

  console.log(`Mode: ${mode}`);

  data.sort((a, b) => {
    const catCmp = (a.category ?? '').localeCompare(b.category ?? '');
    if (catCmp !== 0) return catCmp;
    return (a.issuer?.name ?? '').localeCompare(b.issuer?.name ?? '');
  });

  console.log(`\n--- Verification Programs (page ${pagination.page}/${Math.ceil(pagination.total / pagination.limit) || 1}, ${pagination.total} total) ---\n`);

  const numberedOptions = [];
  let optionIndex = 1;
  for (const item of data) {
    const verifiedTag = item.verified ? '[VERIFIED]' : '';
    console.log(`  [${optionIndex}] ${item.name} ${verifiedTag}`);
    console.log(`    Issuer:       ${item.issuer?.name ?? 'N/A'}`);
    console.log(`    Category:     ${item.category ?? 'N/A'}`);
    console.log(`    Description:  ${item.description ?? 'N/A'}`);
    console.log(`    Programs (top tier first):`);
    const numberedPrograms = [];
    let tierIndex = 1;
    for (const prog of item.programs ?? []) {
      const pVerified = prog.verified ? ' [VERIFIED]' : '';
      console.log(`      (${optionIndex}.${tierIndex}) ${prog.programId}${pVerified}`);
      console.log(`        Issue URL: ${prog.issueUrl}`);
      numberedPrograms.push({
        tierIndex,
        programId: prog.programId,
        verified: prog.verified === true,
        issueUrl: prog.issueUrl,
      });
      tierIndex += 1;
    }
    console.log(`    Verifications: ${item.verifications}`);
    console.log('');
    numberedOptions.push({
      optionIndex,
      name: item.name,
      issuer: item.issuer?.name ?? null,
      category: item.category ?? null,
      programs: numberedPrograms,
    });
    optionIndex += 1;
  }

  if (meta) {
    console.log(`  User verified count: ${meta.verified}`);
  }

  if (pagination.page * pagination.limit < pagination.total) {
    console.log(`  (more results available — use --page ${Number(pagination.page) + 1})`);
  }

  printJson({ pagination, meta, options: numberedOptions });
}

main().catch((error) => {
  console.error(error?.stack || error);
  process.exit(1);
});
