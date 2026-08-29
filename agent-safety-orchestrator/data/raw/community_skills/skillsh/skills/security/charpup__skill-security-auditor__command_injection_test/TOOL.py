#!/usr/bin/env python3
"""
Test skill with command injection vulnerability
Allows arbitrary OS command execution
"""

import subprocess
import os

def execute_tool(command):
    """
    Execute a system tool - vulnerable to command injection
    """
    # VULNERABLE: Direct shell execution of user input
    full_command = f"echo {command}"
    
    result = subprocess.run(
        full_command,
        shell=True,
        capture_output=True,
        text=True
    )
    
    return result.stdout

def process_file(filename):
    """
    Process a file - vulnerable to injection
    """
    # Command injection via filename
    cmd = f"cat {filename}"
    
    return os.system(cmd)

def run_user_script(script_path):
    """
    Execute user-provided script
    """
    # Dangerous: No validation of script path
    exec(open(script_path).read())
