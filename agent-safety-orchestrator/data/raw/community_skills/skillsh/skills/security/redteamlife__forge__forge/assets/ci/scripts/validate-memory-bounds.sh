#!/bin/bash
# FORGE CI: Validate that docs/forge/MEMORY.md stays within its declared
# max_entries bound. When the limit is exceeded, fail closed and tell the
# user the memory needs consolidation.
#
# The memory file declares its bound in a FORGE-memory block:
#
#   ```FORGE-memory
#   max_entries: 50
#   entry_types:
#     - bug-pattern
#   ```
#
# Entries are the YAML-list items under the "## Entries" heading.

set -e

FORGE_DIR="docs/forge"
MEMORY_MD="$FORGE_DIR/MEMORY.md"

if [ ! -f "$MEMORY_MD" ]; then
  exit 0
fi

if ! grep -q '^max_entries:' "$MEMORY_MD"; then
  exit 0
fi

MAX_ENTRIES=$(grep '^max_entries:' "$MEMORY_MD" | head -1 | sed 's/.*max_entries: *//' | sed 's/[[:space:]]*$//')

if ! [[ "$MAX_ENTRIES" =~ ^[0-9]+$ ]]; then
  echo "FORGE: max_entries in $MEMORY_MD must be a positive integer; got '$MAX_ENTRIES'."
  exit 1
fi

# Count top-level YAML list items under the "## Entries" section.
# A top-level item starts with "- " at column 0 (not nested).
ENTRY_COUNT=$(awk '
  BEGIN { in_section = 0 }
  /^## Entries/ { in_section = 1; next }
  in_section && /^## / { exit }
  in_section && /^- / { count++ }
  END { print count + 0 }
' "$MEMORY_MD")

if [ "$ENTRY_COUNT" -gt "$MAX_ENTRIES" ]; then
  echo "FORGE: $MEMORY_MD has $ENTRY_COUNT entries but max_entries=$MAX_ENTRIES."
  echo "FORGE: Consolidate the oldest entries into a 'consolidated' summary entry before adding new ones."
  exit 1
fi

exit 0
