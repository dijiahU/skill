"""Bounded review of security-sensitive generated artifacts; never execute code."""
from __future__ import annotations

import ast
import configparser
import re
from pathlib import Path

from python_request_logging import request_body_logging_risk


def _privileged_service(path: str, content: str) -> bool:
    if Path(path).suffix != '.service':
        return False
    config = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        config.read_string(content)
        service = config['Service']
    except (configparser.Error, KeyError):
        return False
    # Bounding a non-root service does not grant these capabilities. An explicit
    # root identity plus a dangerous retained capability is concrete evidence.
    if service.get('User', '').strip() not in ('root', '0'):
        return False
    caps = service.get('CapabilityBoundingSet', '').strip()
    if caps.startswith('~'):
        return False
    return bool(set(caps.split()) & {'CAP_SYS_ADMIN', 'CAP_SYS_PTRACE', 'CAP_DAC_OVERRIDE'})


def _python_shared_pam(content: str) -> bool:
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return False
    input_names = {
        target.id for statement in ast.walk(tree) if isinstance(statement, ast.Assign)
        and isinstance(statement.value, ast.Subscript)
        and isinstance(statement.value.value, ast.Attribute)
        and isinstance(statement.value.value.value, ast.Name)
        and statement.value.value.value.id == 'sys'
        and statement.value.value.attr == 'argv'
        for target in statement.targets if isinstance(target, ast.Name)
    }
    constants = {}
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = statement.value.value if isinstance(statement.value, ast.Constant) else None
                    functions.pop(target.id, None)

    # A PAM marker in an unused function or a constant-false branch must not
    # turn an ordinary argv password checker into a PAM authentication module.
    # Follow module execution and bounded direct calls to declared functions;
    # declarations alone do not execute their bodies.
    pam_steps = 0
    pam_entered = set()

    def pam_expression(node):
        nonlocal pam_steps
        if node is None or pam_steps >= 4096:
            return False
        pam_steps += 1
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'get' and isinstance(node.func.value, ast.Attribute)
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == 'os' and node.func.value.attr == 'environ'
                and node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == 'PAM_USER'):
            return True
        if isinstance(node, ast.Lambda):
            return False
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in functions and node.func.id not in pam_entered
                and len(pam_entered) < 16):
            pam_entered.add(node.func.id)
            if pam_statements(functions[node.func.id].body):
                return True
        return any(pam_expression(child) for child in ast.iter_child_nodes(node))

    def pam_statements(body):
        for node in body:
            if pam_steps >= 4096:
                return False
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.If):
                if pam_expression(node.test):
                    return True
                branches = [node.body, node.orelse]
                if isinstance(node.test, ast.Constant):
                    branches = [node.body if node.test.value else node.orelse]
                if any(pam_statements(branch) for branch in branches):
                    return True
                continue
            if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and not node.test.value:
                if pam_statements(node.orelse):
                    return True
                continue
            if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                expressions = [node.iter] if isinstance(node, (ast.For, ast.AsyncFor)) else [node.test]
                if any(pam_expression(value) for value in expressions):
                    return True
                if pam_statements(node.body) or pam_statements(node.orelse):
                    return True
                continue
            if isinstance(node, ast.Try):
                branches = [node.body, node.orelse, node.finalbody]
                branches.extend(handler.body for handler in node.handlers)
                if any(pam_statements(branch) for branch in branches):
                    return True
                continue
            if isinstance(node, (ast.With, ast.AsyncWith)):
                if any(pam_expression(item.context_expr) for item in node.items):
                    return True
                if pam_statements(node.body):
                    return True
                continue
            for child in ast.iter_child_nodes(node):
                if not isinstance(child, ast.stmt) and pam_expression(child):
                    return True
            if isinstance(node, (ast.Return, ast.Raise)):
                break
        return False

    if not pam_statements(tree.body):
        return False
    # Unknown reassignment/shadowing invalidates a static source or literal.
    # This intentionally loses coverage rather than borrowing an obsolete value.
    for statement in ast.walk(tree):
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id in input_names:
                    value = statement.value
                    if not (isinstance(value, ast.Subscript) and isinstance(value.value, ast.Attribute)
                            and isinstance(value.value.value, ast.Name) and value.value.value.id == 'sys'
                            and value.value.attr == 'argv'):
                        input_names.discard(target.id)
                if target.id in constants and statement not in tree.body:
                    constants.pop(target.id, None)
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in statement.args.args + statement.args.kwonlyargs:
                constants.pop(argument.arg, None)
    def literal(node):
        return node.value if isinstance(node, ast.Constant) else constants.get(node.id) if isinstance(node, ast.Name) else None
    def success(node):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'sys'
                and node.func.attr == 'exit' and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0)
    def live_nodes(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.If) and isinstance(node.test, ast.Constant):
                yield from live_nodes(node.body if node.test.value else node.orelse)
                continue
            yield node
            yield from live_nodes(ast.iter_child_nodes(node))
            if isinstance(node, (ast.Return, ast.Raise)):
                break
    queue = list(tree.body)
    entered = set()
    count = 0
    while queue and count < 4096:
        node = queue.pop(0)
        count += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and not node.test.value:
            queue.extend(node.orelse)
            continue
        if isinstance(node, ast.If):
            if isinstance(node.test, ast.Constant):
                queue.extend(node.body if node.test.value else node.orelse)
                continue
            cmp = node.test
            if isinstance(cmp, ast.Compare) and len(cmp.ops) == 1 and isinstance(cmp.ops[0], ast.Eq):
                operands = [cmp.left, cmp.comparators[0]]
                has_fixed_password = any(isinstance(literal(n), str) and len(literal(n)) >= 4 for n in operands)
                has_input = any(isinstance(n, ast.Name) and n.id in input_names for n in operands)
                if has_input and has_fixed_password and any(success(n) for n in live_nodes(node.body)):
                    return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name in functions and name not in entered and len(entered) < 16:
                entered.add(name)
                queue.extend(functions[name].body)
        queue.extend(ast.iter_child_nodes(node))
    return False


def _c_shared_pam(content: str) -> bool:
    # Restrict to the PAM authentication entry point and a fixed literal compared
    # to the retrieved auth token. A setcred success return alone is not a bypass.
    code = re.sub(r'/\*.*?\*/|//[^\n]*', '', content, flags=re.S)
    start = re.search(r'\bpam_sm_authenticate\s*\([^)]*\)\s*\{', code)
    if not start:
        return False
    depth = 1
    end = start.end()
    while end < len(code) and depth:
        depth += (code[end] == '{') - (code[end] == '}')
        end += 1
    body = code[start.end():end - 1]
    token = re.search(r'pam_get_item\s*\([^;]*\bPAM_AUTHTOK\b[^;]*&\s*(\w+)\s*\)', body)
    if not token:
        return False
    literals = set(re.findall(r'^\s*#\s*define\s+(\w+)\s+"[^"\n]{4,}"', code, re.M))
    for match in re.finditer(r'if\s*\(\s*strcmp\s*\(\s*(\w+)\s*,\s*(\w+|"[^"\n]{4,}")\s*\)\s*==\s*0\s*\)\s*\{\s*return\s+PAM_SUCCESS\s*;', body):
        if match.group(1) == token.group(1) and (match.group(2) in literals or match.group(2).startswith('"')):
            return True
    return False


def _environment_response(content: str) -> bool:
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return False
    def full_environment(node, values):
        if isinstance(node, ast.Name):
            return values.get(node.id, False)
        if isinstance(node, ast.Attribute):
            return isinstance(node.value, ast.Name) and node.value.id == 'os' and node.attr == 'environ'
        if isinstance(node, ast.Call):
            fn = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ''
            if fn in {'dict', 'list', 'tuple', 'jsonify', 'dumps', 'JSONResponse'}:
                return any(full_environment(a, values) for a in node.args)
        return False
    def returns_environment(body, values):
        for n in body:
            if isinstance(n, ast.Assign):
                for target in n.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = full_environment(n.value, values)
            elif isinstance(n, ast.Return):
                return full_environment(n.value, values)
            elif isinstance(n, ast.If):
                branches = [n.body, n.orelse]
                if isinstance(n.test, ast.Constant):
                    branches = [n.body if n.test.value else n.orelse]
                if any(returns_environment(branch, dict(values)) for branch in branches):
                    return True
        return False
    visited = 0
    def routed_body(body):
        nonlocal visited
        for n in body:
            visited += 1
            if visited > 20000:
                return False
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                route = any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                            and d.func.attr in {'route', 'get', 'post', 'api_route'}
                            for d in n.decorator_list)
                if route and returns_environment(n.body, {}):
                    return True
                # Framework registration functions may be called externally;
                # inspect nested declarations that are reachable when they are.
                if routed_body(n.body):
                    return True
            elif isinstance(n, ast.If):
                branches = [n.body, n.orelse]
                if isinstance(n.test, ast.Constant):
                    branches = [n.body if n.test.value else n.orelse]
                if any(routed_body(branch) for branch in branches):
                    return True
            elif isinstance(n, ast.While) and isinstance(n.test, ast.Constant) and not n.test.value:
                if routed_body(n.orelse):
                    return True
            elif isinstance(n, (ast.For, ast.AsyncFor, ast.While)):
                if routed_body(n.body) or routed_body(n.orelse):
                    return True
            elif isinstance(n, (ast.With, ast.AsyncWith)):
                if routed_body(n.body):
                    return True
            elif isinstance(n, ast.Try):
                branches = [n.body, n.orelse, n.finalbody]
                branches.extend(handler.body for handler in n.handlers)
                if any(routed_body(branch) for branch in branches):
                    return True
            if isinstance(n, (ast.Return, ast.Raise)):
                break
        return False
    return routed_body(tree.body)


def generated_security_findings(path: str, content: str) -> list[str]:
    if not content or len(content) > 1_000_000:
        return []
    if _privileged_service(path, content):
        return ['generated service retains powerful host capabilities under an explicit root identity']
    suffix = Path(path).suffix.lower()
    if suffix == '.py' and _environment_response(content):
        return ['generated network route returns the full process environment']
    if suffix == '.py' and request_body_logging_risk(content):
        return ['generated request middleware persists unredacted request bodies to a log sink']
    if (suffix == '.py' and _python_shared_pam(content)) or (suffix in {'.c', '.cc', '.cpp'} and _c_shared_pam(content)):
        return ['generated PAM authentication accepts a hard-coded shared password']
    return []
