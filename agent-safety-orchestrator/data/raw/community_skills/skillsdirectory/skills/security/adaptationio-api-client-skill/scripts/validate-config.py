#!/usr/bin/env python3
"""
Validate API client configuration

Usage:
    validate-config.py <config-file>

Example:
    python validate-config.py config.json
"""

import sys
import json
from pathlib import Path

def validate_config(config_file):
    """Validate configuration file"""
    if not Path(config_file).exists():
        print(f"Error: File not found: {config_file}", file=sys.stderr)
        return 1

    try:
        with open(config_file) as f:
            config = json.load(f)

        # Check required fields
        required = ['baseURL']
        for field in required:
            if field not in config:
                print(f"Error: Missing required field: {field}", file=sys.stderr)
                return 1

        print(f"✓ Configuration valid: {config_file}")
        return 0

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    if len(sys.argv) < 2 or '--help' in sys.argv:
        print(__doc__)
        sys.exit(1)

    sys.exit(validate_config(sys.argv[1]))
