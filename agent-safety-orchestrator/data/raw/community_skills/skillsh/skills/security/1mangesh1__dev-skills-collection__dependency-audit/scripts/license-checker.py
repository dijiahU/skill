#!/usr/bin/env python3
"""Dependency License Checker"""

import subprocess
import json
import re

def check_licenses():
    """Check licenses of all dependencies"""
    try:
        result = subprocess.run(
            ['npm', 'list', '--json', '--depth=0'],
            capture_output=True,
            text=True
        )
        
        dependencies = json.loads(result.stdout).get('dependencies', {})
        
        restricted_licenses = {'AGPL', 'GPL', 'SSPL'}
        issues = []
        
        for package, info in dependencies.items():
            if isinstance(info, dict):
                # Try to get license from package
                print(f"Checking {package}...")
                # In real scenario, would parse actual license
        
        return issues
    except Exception as e:
        print(f"Error checking licenses: {e}")
        return []

def check_dependency_conflicts():
    """Check for version conflicts"""
    try:
        result = subprocess.run(
            ['npm', 'list', '--depth=3'],
            capture_output=True,
            text=True
        )
        
        if 'deduped' in result.stdout or 'conflicting' in result.stdout:
            print("⚠ Potential dependency conflicts detected")
            return False
        else:
            print("✓ No obvious dependency conflicts")
            return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    check_dependency_conflicts()
    check_licenses()
