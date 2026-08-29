/**
 * Language, framework, and package manager detection.
 * Inspects file extensions, config files, and directory patterns.
 * Zero dependencies — pure Node.js.
 */

import { access } from 'node:fs/promises';
import path from 'node:path';
import { readContent } from './line-reader.mjs';

/**
 * Extension-to-language mapping.
 */
const EXT_LANGUAGE = {
  '.js': 'JavaScript',
  '.mjs': 'JavaScript',
  '.cjs': 'JavaScript',
  '.jsx': 'JavaScript',
  '.ts': 'TypeScript',
  '.tsx': 'TypeScript',
  '.py': 'Python',
  '.rb': 'Ruby',
  '.go': 'Go',
  '.rs': 'Rust',
  '.java': 'Java',
  '.kt': 'Kotlin',
  '.scala': 'Scala',
  '.ex': 'Elixir',
  '.exs': 'Elixir',
  '.erl': 'Erlang',
  '.php': 'PHP',
  '.cs': 'C#',
  '.fs': 'F#',
  '.swift': 'Swift',
  '.m': 'Objective-C',
  '.c': 'C',
  '.cpp': 'C++',
  '.cc': 'C++',
  '.h': 'C/C++ Header',
  '.hpp': 'C++ Header',
  '.lua': 'Lua',
  '.r': 'R',
  '.dart': 'Dart',
  '.vue': 'Vue',
  '.svelte': 'Svelte',
  '.astro': 'Astro',
  '.css': 'CSS',
  '.scss': 'SCSS',
  '.less': 'LESS',
  '.html': 'HTML',
  '.md': 'Markdown',
  '.mdx': 'MDX',
  '.sql': 'SQL',
  '.sh': 'Shell',
  '.bash': 'Shell',
  '.zsh': 'Shell',
  '.yml': 'YAML',
  '.yaml': 'YAML',
  '.toml': 'TOML',
  '.json': 'JSON',
  '.xml': 'XML',
  '.graphql': 'GraphQL',
  '.gql': 'GraphQL',
  '.proto': 'Protocol Buffers',
  '.tf': 'Terraform',
  '.hcl': 'HCL',
  '.dockerfile': 'Docker',
};

/**
 * Config-file-to-framework mapping.
 * Checked in order; first match wins for each category.
 */
const FRAMEWORK_SIGNALS = [
  // Meta-frameworks & SSR
  { file: 'astro.config.mjs', framework: 'Astro' },
  { file: 'astro.config.ts', framework: 'Astro' },
  { file: 'next.config.js', framework: 'Next.js' },
  { file: 'next.config.mjs', framework: 'Next.js' },
  { file: 'next.config.ts', framework: 'Next.js' },
  { file: 'nuxt.config.ts', framework: 'Nuxt' },
  { file: 'nuxt.config.js', framework: 'Nuxt' },
  { file: 'remix.config.js', framework: 'Remix' },
  { file: 'svelte.config.js', framework: 'SvelteKit' },
  { file: 'angular.json', framework: 'Angular' },
  { file: 'gatsby-config.js', framework: 'Gatsby' },
  { file: 'gatsby-config.ts', framework: 'Gatsby' },

  // Backend
  { file: 'mix.exs', framework: 'Elixir/Phoenix' },
  { file: 'manage.py', framework: 'Django' },
  { file: 'requirements.txt', framework: 'Python' },
  { file: 'pyproject.toml', framework: 'Python' },
  { file: 'Gemfile', framework: 'Ruby/Rails' },
  { file: 'Cargo.toml', framework: 'Rust' },
  { file: 'go.mod', framework: 'Go' },
  { file: 'pom.xml', framework: 'Java/Maven' },
  { file: 'build.gradle', framework: 'Java/Gradle' },
  { file: 'build.gradle.kts', framework: 'Kotlin/Gradle' },
  { file: 'composer.json', framework: 'PHP/Composer' },

  // Mobile
  { file: 'app.json', framework: 'React Native' },
  { file: 'pubspec.yaml', framework: 'Flutter' },
  { file: 'Podfile', framework: 'iOS/CocoaPods' },

  // Frontend libraries (checked via package.json later)
  { file: 'tailwind.config.js', framework: 'Tailwind CSS' },
  { file: 'tailwind.config.ts', framework: 'Tailwind CSS' },
  { file: 'postcss.config.js', framework: 'PostCSS' },
  { file: 'vite.config.js', framework: 'Vite' },
  { file: 'vite.config.ts', framework: 'Vite' },
  { file: 'webpack.config.js', framework: 'Webpack' },
  { file: 'rollup.config.js', framework: 'Rollup' },
  { file: 'tsconfig.json', framework: 'TypeScript' },

  // Infrastructure
  { file: 'docker-compose.yml', framework: 'Docker Compose' },
  { file: 'docker-compose.yaml', framework: 'Docker Compose' },
  { file: 'Dockerfile', framework: 'Docker' },
  { file: 'terraform.tf', framework: 'Terraform' },
  { file: '.github/workflows', framework: 'GitHub Actions' },
];

/**
 * Package manager detection.
 */
const PACKAGE_MANAGERS = [
  { lockfile: 'pnpm-lock.yaml', manager: 'pnpm' },
  { lockfile: 'yarn.lock', manager: 'yarn' },
  { lockfile: 'package-lock.json', manager: 'npm' },
  { lockfile: 'bun.lockb', manager: 'bun' },
  { lockfile: 'mix.lock', manager: 'mix' },
  { lockfile: 'Pipfile.lock', manager: 'pipenv' },
  { lockfile: 'poetry.lock', manager: 'poetry' },
  { lockfile: 'Cargo.lock', manager: 'cargo' },
  { lockfile: 'go.sum', manager: 'go' },
  { lockfile: 'Gemfile.lock', manager: 'bundler' },
  { lockfile: 'composer.lock', manager: 'composer' },
  { lockfile: 'pubspec.lock', manager: 'pub' },
];

async function fileExists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Detect the ecosystem of a project.
 *
 * @param {string} rootDir - Absolute path to project root
 * @param {object[]} files - Array of file objects from fs-walk
 * @returns {Promise<object>} Ecosystem info
 */
export async function detectEcosystem(rootDir, files) {
  // Count languages by extension
  const languageCounts = {};
  let totalLOC = 0;
  const codeExtensions = new Set([
    '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
    '.py', '.rb', '.go', '.rs', '.java', '.kt', '.scala',
    '.ex', '.exs', '.php', '.cs', '.swift', '.c', '.cpp', '.cc',
    '.h', '.hpp', '.lua', '.r', '.dart', '.vue', '.svelte', '.astro',
    '.css', '.scss', '.less', '.html', '.sql', '.sh', '.bash',
    '.graphql', '.gql', '.proto', '.tf',
  ]);

  for (const file of files) {
    const lang = EXT_LANGUAGE[file.ext];
    if (lang) {
      languageCounts[lang] = (languageCounts[lang] || 0) + 1;
    }
  }

  // Determine primary language
  const sorted = Object.entries(languageCounts).sort((a, b) => b[1] - a[1]);
  const primaryLanguage = sorted.length > 0 ? sorted[0][0] : 'Unknown';
  const languages = sorted.map(([lang, count]) => ({ language: lang, fileCount: count }));

  // Detect frameworks
  const frameworks = [];
  const seen = new Set();
  for (const signal of FRAMEWORK_SIGNALS) {
    if (seen.has(signal.framework)) continue;
    const exists = await fileExists(path.join(rootDir, signal.file));
    if (exists) {
      frameworks.push(signal.framework);
      seen.add(signal.framework);
    }
  }

  // Check package.json for additional framework signals
  const pkgPath = path.join(rootDir, 'package.json');
  let packageJson = null;
  const pkgContent = await readContent(pkgPath);
  if (pkgContent) {
    try {
      packageJson = JSON.parse(pkgContent);
    } catch {
      // Malformed package.json
    }
  }

  if (packageJson) {
    const allDeps = {
      ...packageJson.dependencies,
      ...packageJson.devDependencies,
    };
    const depNames = Object.keys(allDeps);

    const frameworkDeps = [
      { dep: 'react', framework: 'React' },
      { dep: 'vue', framework: 'Vue' },
      { dep: 'svelte', framework: 'Svelte' },
      { dep: '@angular/core', framework: 'Angular' },
      { dep: 'express', framework: 'Express' },
      { dep: 'fastify', framework: 'Fastify' },
      { dep: 'hono', framework: 'Hono' },
      { dep: 'koa', framework: 'Koa' },
      { dep: 'nest', framework: 'NestJS' },
      { dep: '@nestjs/core', framework: 'NestJS' },
      { dep: 'prisma', framework: 'Prisma' },
      { dep: '@prisma/client', framework: 'Prisma' },
      { dep: 'drizzle-orm', framework: 'Drizzle' },
      { dep: 'mongoose', framework: 'Mongoose' },
      { dep: 'sequelize', framework: 'Sequelize' },
      { dep: 'tailwindcss', framework: 'Tailwind CSS' },
      { dep: '@tailwindcss/typography', framework: 'Tailwind Typography' },
    ];

    for (const { dep, framework } of frameworkDeps) {
      if (depNames.includes(dep) && !seen.has(framework)) {
        frameworks.push(framework);
        seen.add(framework);
      }
    }
  }

  // Detect package manager
  let packageManager = null;
  let hasLockfile = false;
  for (const { lockfile, manager } of PACKAGE_MANAGERS) {
    if (await fileExists(path.join(rootDir, lockfile))) {
      packageManager = manager;
      hasLockfile = true;
      break;
    }
  }

  // Fallback: if package.json exists but no lockfile detected
  if (!packageManager && packageJson) {
    packageManager = 'npm'; // Default assumption
    hasLockfile = false;
  }

  // Detect test frameworks
  const testFrameworks = detectTestFrameworks(packageJson, files);

  return {
    primaryLanguage,
    languages,
    frameworks,
    packageManager,
    hasLockfile,
    packageJson,
    testFrameworks,
    totalFiles: files.length,
  };
}

/**
 * Detect test frameworks from package.json and file patterns.
 */
function detectTestFrameworks(packageJson, files) {
  const frameworks = [];

  if (packageJson) {
    const allDeps = {
      ...packageJson.dependencies,
      ...packageJson.devDependencies,
    };
    const depNames = Object.keys(allDeps);

    const testDeps = [
      { dep: 'jest', framework: 'Jest' },
      { dep: 'vitest', framework: 'Vitest' },
      { dep: 'mocha', framework: 'Mocha' },
      { dep: '@testing-library/react', framework: 'React Testing Library' },
      { dep: '@testing-library/vue', framework: 'Vue Testing Library' },
      { dep: 'cypress', framework: 'Cypress' },
      { dep: 'playwright', framework: 'Playwright' },
      { dep: '@playwright/test', framework: 'Playwright' },
      { dep: 'ava', framework: 'AVA' },
      { dep: 'tap', framework: 'tap' },
      { dep: 'supertest', framework: 'Supertest' },
      { dep: 'chai', framework: 'Chai' },
    ];

    for (const { dep, framework } of testDeps) {
      if (depNames.includes(dep)) {
        frameworks.push(framework);
      }
    }
  }

  // Check for test config files
  const testConfigs = files.map(f => f.relativePath);
  const configSignals = [
    { pattern: /jest\.config/, framework: 'Jest' },
    { pattern: /vitest\.config/, framework: 'Vitest' },
    { pattern: /\.mocharc/, framework: 'Mocha' },
    { pattern: /cypress\.config/, framework: 'Cypress' },
    { pattern: /playwright\.config/, framework: 'Playwright' },
    { pattern: /pytest\.ini|setup\.cfg|conftest\.py/, framework: 'pytest' },
    { pattern: /phpunit\.xml/, framework: 'PHPUnit' },
    { pattern: /\.rspec/, framework: 'RSpec' },
  ];

  for (const { pattern, framework } of configSignals) {
    if (testConfigs.some(p => pattern.test(p)) && !frameworks.includes(framework)) {
      frameworks.push(framework);
    }
  }

  return frameworks;
}
