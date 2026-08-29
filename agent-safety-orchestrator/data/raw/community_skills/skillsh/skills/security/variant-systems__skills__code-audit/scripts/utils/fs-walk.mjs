/**
 * Cross-platform recursive file walker.
 * Zero dependencies — pure Node.js.
 */

import { readdir, stat } from 'node:fs/promises';
import path from 'node:path';

/** Directories to always skip. */
const DEFAULT_IGNORE = new Set([
  'node_modules',
  '.git',
  '.svn',
  '.hg',
  'dist',
  'build',
  'out',
  '.next',
  '.nuxt',
  '.astro',
  '__pycache__',
  '.pytest_cache',
  '.mypy_cache',
  'venv',
  '.venv',
  'env',
  '.env',
  'vendor',
  '_build',
  'deps',
  '.elixir_ls',
  'target',
  'coverage',
  '.cache',
  '.turbo',
  '.vercel',
  '.netlify',
  '.output',
  'tmp',
  '.tmp',
]);

/** Binary / non-text extensions to skip. */
const BINARY_EXTENSIONS = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.avif',
  '.svg', '.ttf', '.otf', '.woff', '.woff2', '.eot',
  '.mp3', '.mp4', '.wav', '.ogg', '.webm', '.avi', '.mov',
  '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
  '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.exe', '.dll', '.so', '.dylib', '.bin', '.dat',
  '.pyc', '.pyo', '.class', '.o', '.obj',
  '.db', '.sqlite', '.sqlite3',
  '.lock',
  '.map',
]);

/**
 * Recursively walk a directory and yield file info objects.
 *
 * @param {string} rootDir - Absolute path to walk
 * @param {object} [opts]
 * @param {Set<string>} [opts.ignoreDirs] - Additional directory names to skip
 * @param {Set<string>} [opts.ignoreExtensions] - Additional extensions to skip
 * @param {number} [opts.maxDepth=20] - Max recursion depth
 * @param {number} [opts.maxFiles=10_000] - Stop after this many files
 * @returns {AsyncGenerator<{ absolutePath: string, relativePath: string, ext: string, size: number }>}
 */
export async function* walk(rootDir, {
  ignoreDirs = new Set(),
  ignoreExtensions = new Set(),
  maxDepth = 20,
  maxFiles = 10_000,
} = {}) {
  const allIgnoreDirs = new Set([...DEFAULT_IGNORE, ...ignoreDirs]);
  const allIgnoreExts = new Set([...BINARY_EXTENSIONS, ...ignoreExtensions]);
  let fileCount = 0;

  async function* _walk(dir, depth) {
    if (depth > maxDepth || fileCount >= maxFiles) return;

    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return; // Permission denied or similar
    }

    for (const entry of entries) {
      if (fileCount >= maxFiles) return;

      const entryPath = path.join(dir, entry.name);

      if (entry.isDirectory()) {
        if (allIgnoreDirs.has(entry.name)) continue;
        if (entry.name.startsWith('.') && entry.name !== '.github') continue;
        yield* _walk(entryPath, depth + 1);
      } else if (entry.isFile()) {
        const ext = path.extname(entry.name).toLowerCase();
        if (allIgnoreExts.has(ext)) continue;

        let fileStat;
        try {
          fileStat = await stat(entryPath);
        } catch {
          continue;
        }

        fileCount++;
        yield {
          absolutePath: entryPath,
          relativePath: path.relative(rootDir, entryPath),
          ext,
          size: fileStat.size,
        };
      }
    }
  }

  yield* _walk(rootDir, 0);
}

/**
 * Collect all files from walk() into an array.
 */
export async function collectFiles(rootDir, opts) {
  const files = [];
  for await (const file of walk(rootDir, opts)) {
    files.push(file);
  }
  return files;
}
