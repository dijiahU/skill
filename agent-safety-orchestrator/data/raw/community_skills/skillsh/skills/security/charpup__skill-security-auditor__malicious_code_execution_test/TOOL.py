#!/usr/bin/env python3
"""
Test skill with arbitrary code execution vulnerability
Allows execution of malicious code
"""

def execute_user_code(code_string):
    """
    Execute user-provided code - extremely dangerous
    """
    # VULNERABLE: Direct code execution
    result = eval(code_string)
    return result

def dynamic_execution(code):
    """
    Dynamically execute code
    """
    # Another dangerous pattern
    exec(code)
    return "Executed"

def compile_and_run(source):
    """
    Compile and run arbitrary source code
    """
    compiled = compile(source, '<string>', 'exec')
    exec(compiled)
