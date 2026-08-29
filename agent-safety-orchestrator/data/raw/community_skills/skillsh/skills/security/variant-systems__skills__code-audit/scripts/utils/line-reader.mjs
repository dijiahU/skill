/**
 * CRLF-safe line reader.
 * Reads a file and returns lines with metadata, handling both LF and CRLF.
 * Zero dependencies — pure Node.js.
 */

import { readFile } from 'node:fs/promises';

/**
 * Read a file and return its lines.
 * Handles UTF-8, CRLF, and LF line endings.
 *
 * @param {string} filePath - Absolute path to file
 * @param {object} [opts]
 * @param {number} [opts.maxBytes=2_097_152] - Skip files larger than this (default 2MB)
 * @returns {Promise<{ lines: string[], lineEnding: 'crlf'|'lf'|'mixed', totalLines: number } | null>}
 *   Returns null if file is too large or unreadable.
 */
export async function readLines(filePath, { maxBytes = 2_097_152 } = {}) {
  let buffer;
  try {
    buffer = await readFile(filePath);
  } catch {
    return null;
  }

  if (buffer.length > maxBytes) return null;

  const content = buffer.toString('utf-8');

  const hasCRLF = content.includes('\r\n');
  const hasLF = content.includes('\n') && !hasCRLF;
  const lineEnding = hasCRLF && hasLF ? 'mixed' : hasCRLF ? 'crlf' : 'lf';

  // Normalize to LF before splitting
  const normalized = content.replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');

  // Remove trailing empty line from final newline
  if (lines.length > 0 && lines[lines.length - 1] === '') {
    lines.pop();
  }

  return {
    lines,
    lineEnding,
    totalLines: lines.length,
  };
}

/**
 * Read a file and return raw content as string.
 * @param {string} filePath
 * @param {object} [opts]
 * @param {number} [opts.maxBytes=2_097_152]
 * @returns {Promise<string|null>}
 */
export async function readContent(filePath, { maxBytes = 2_097_152 } = {}) {
  let buffer;
  try {
    buffer = await readFile(filePath);
  } catch {
    return null;
  }

  if (buffer.length > maxBytes) return null;
  return buffer.toString('utf-8');
}
