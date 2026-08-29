/**
 * Finding deduplication — merges tool and regex findings.
 * When both find the same file+line, keeps the tool finding (richer context).
 * All tool findings are preserved. Regex findings only where tools didn't cover.
 * Zero dependencies — pure Node.js.
 */

/**
 * Deduplicate tool findings and regex findings.
 *
 * @param {object[]} toolFindings - Findings from external tools (source='tool')
 * @param {object[]} regexFindings - Findings from regex analysis (source='regex')
 * @returns {object[]} Merged deduplicated findings
 */
export function deduplicateFindings(toolFindings, regexFindings) {
  // Build a set of file+line combos covered by tools
  const toolCoverage = new Set();

  for (const f of toolFindings) {
    if (f.file && f.line) {
      toolCoverage.add(`${f.file}:${f.line}`);
    }
    // Also mark a wider range (tools often report nearby lines for the same issue)
    if (f.file && f.line) {
      for (let offset = -2; offset <= 2; offset++) {
        const nearbyLine = f.line + offset;
        if (nearbyLine > 0) {
          toolCoverage.add(`${f.file}:${nearbyLine}`);
        }
      }
    }
  }

  // Keep regex findings only where tools didn't find anything at the same location
  const keptRegex = [];
  for (const f of regexFindings) {
    if (f.file && f.line) {
      const key = `${f.file}:${f.line}`;
      if (toolCoverage.has(key)) continue; // Tool already covers this
    }
    keptRegex.push(f);
  }

  return [...toolFindings, ...keptRegex];
}
