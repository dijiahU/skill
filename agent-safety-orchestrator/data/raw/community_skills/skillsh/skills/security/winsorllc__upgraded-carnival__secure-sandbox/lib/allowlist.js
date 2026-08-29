/**
 * Allowlist Manager
 * 
 * Manages allowed command patterns that can auto-execute.
 * 
 */

const fs = require('fs');
const path = require('path');

const ALLOWLIST_FILE = path.join(__dirname, '..', '.sandbox', 'allowlist.json');

// Default safe commands
const DEFAULT_ALLOWLIST = [
  { pattern: '^ls\\s+', description: 'List directory contents', auto_approve: true },
  { pattern: '^pwd$', description: 'Print working directory', auto_approve: true },
  { pattern: '^cat\\s+', description: 'Display file contents', auto_approve: true },
  { pattern: '^echo\\s+', description: 'Print text', auto_approve: true },
  { pattern: '^grep\\s+', description: 'Search text', auto_approve: true },
  { pattern: '^rg\\s+', description: 'Ripgrep search', auto_approve: true },
  { pattern: '^head\\s+', description: 'Show file start', auto_approve: true },
  { pattern: '^tail\\s+', description: 'Show file end', auto_approve: true },
  { pattern: '^find\\s+', description: 'Find files', auto_approve: true },
  { pattern: '^node\\s+--version$', description: 'Check Node version', auto_approve: true },
  { pattern: '^npm\\s+list', description: 'List npm packages', auto_approve: true },
  { pattern: '^git\\s+status', description: 'Git status', auto_approve: true },
  { pattern: '^git\\s+log', description: 'Git log', auto_approve: true },
  { pattern: '^git\\s+describe', description: 'Git describe', auto_approve: true },
  { pattern: '^mkdir\\s+', description: 'Create directory', auto_approve: true },
  { pattern: '^touch\\s+', description: 'Create empty file', auto_approve: true },
  { pattern: '^cd\\s+', description: 'Change directory', auto_approve: true }
];

/**
 * Load allowlist from file or return defaults
 * @returns {Object[]} Array of allowlist entries
 */
function loadAllowlist() {
  try {
    if (fs.existsSync(ALLOWLIST_FILE)) {
      const data = fs.readFileSync(ALLOWLIST_FILE, 'utf8');
      const parsed = JSON.parse(data);
      // Merge with defaults
      return [...DEFAULT_ALLOWLIST, ...(parsed.entries || [])];
    }
  } catch (err) {
    console.error('Error loading allowlist:', err.message);
  }
  return [...DEFAULT_ALLOWLIST];
}

/**
 * Save allowlist to file
 * @param {Object[]} entries - Array of allowlist entries
 */
function saveAllowlist(entries) {
  const dir = path.dirname(ALLOWLIST_FILE);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(ALLOWLIST_FILE, JSON.stringify({ entries }, null, 2));
}

/**
 * Test if a command matches the allowlist
 * @param {string} command - Command to test
 * @returns {Object} Match result
 */
function testAllowlist(command) {
  const entries = loadAllowlist();
  
  for (const entry of entries) {
    try {
      const regex = new RegExp(entry.pattern, 'i');
      if (regex.test(command)) {
        return {
          matched: true,
          pattern: entry.pattern,
          description: entry.description,
          auto_approve: entry.auto_approve !== false
        };
      }
    } catch (err) {
      console.error(`Invalid pattern in allowlist: ${entry.pattern}`);
    }
  }
  
  return {
    matched: false,
    pattern: null,
    description: null,
    auto_approve: false
  };
}

/**
 * Add a pattern to the allowlist
 * @param {Object} entry - Allowlist entry
 * @returns {Object} Result
 */
function addToAllowlist(entry) {
  const entries = loadAllowlist().filter(e => 
    !DEFAULT_ALLOWLIST.some(d => d.pattern === e.pattern)
  );
  
  // Check if already exists
  const exists = entries.some(e => e.pattern === entry.pattern);
  if (exists) {
    return { success: false, error: 'Pattern already exists in allowlist' };
  }
  
  // Validate pattern
  try {
    new RegExp(entry.pattern);
  } catch (err) {
    return { success: false, error: `Invalid regex pattern: ${err.message}` };
  }
  
  entries.push({
    pattern: entry.pattern,
    description: entry.description || 'User-defined pattern',
    auto_approve: entry.auto_approve !== false,
    added_at: new Date().toISOString()
  });
  
  saveAllowlist(entries);
  
  return { 
    success: true, 
    pattern: entry.pattern,
    message: 'Pattern added to allowlist'
  };
}

/**
 * Remove a pattern from the allowlist
 * @param {string} pattern - Pattern to remove
 * @returns {Object} Result
 */
function removeFromAllowlist(pattern) {
  const entries = loadAllowlist().filter(e => 
    !DEFAULT_ALLOWLIST.some(d => d.pattern === e.pattern)
  );
  
  const filtered = entries.filter(e => e.pattern !== pattern);
  
  if (filtered.length === entries.length) {
    return { success: false, error: 'Pattern not found in allowlist' };
  }
  
  saveAllowlist(filtered);
  
  return { 
    success: true, 
    pattern,
    message: 'Pattern removed from allowlist'
  };
}

/**
 * List all allowlist entries
 * @returns {Object[]} All entries
 */
function listAllowlist() {
  const entries = loadAllowlist();
  return {
    defaults: DEFAULT_ALLOWLIST,
    custom: entries.filter(e => 
      !DEFAULT_ALLOWLIST.some(d => d.pattern === e.pattern)
    )
  };
}

/**
 * Reset allowlist to defaults
 * @returns {Object} Result
 */
function resetAllowlist() {
  saveAllowlist([]);
  return {
    success: true,
    message: 'Allowlist reset to defaults',
    defaults_count: DEFAULT_ALLOWLIST.length
  };
}

module.exports = {
  loadAllowlist,
  saveAllowlist,
  testAllowlist,
  addToAllowlist,
  removeFromAllowlist,
  listAllowlist,
  resetAllowlist,
  DEFAULT_ALLOWLIST
};
