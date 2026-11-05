#!/usr/bin/env bash
# Install a standalone DSH plugin and an opt-in config patch.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 "$ROOT/adapters/dsh/install.py"
