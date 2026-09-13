"""Bounded Python data flow for bulk environment values reaching output sinks.

Inspect syntax only; follow direct local calls, never execute generated code.
Names, strings, comments and allowlisted single-key lookups alone are not sinks.
"""
from __future__ import annotations

import ast


def environment_persistence_risk(content: str) -> bool:
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return False
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    entered: set[str] = set()
    steps = 0

    def source(node, values):
        if isinstance(node, ast.Name):
            return values.get(node.id, '')
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == 'os' and node.attr == 'environ':
                return 'environment'
        if isinstance(node, ast.Subscript) and source(node.value, values) == 'environment':
            # Explicitly selected fields are outside this bulk-export check.
            if not isinstance(node.slice, ast.Constant):
                return 'value'
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
            if isinstance(node.func, ast.Attribute) and source(node.func.value, values) == 'environment':
                if name in {'copy', 'items', 'values'}:
                    return 'environment'
                if name == 'keys':
                    return 'key'
            if name in {'dict', 'str', 'repr', 'list', 'tuple', 'sorted', 'dumps'}:
                kinds = [source(a, values) for a in node.args]
                if any(k in {'environment', 'value'} for k in kinds):
                    return 'environment' if 'environment' in kinds else 'value'
        if isinstance(node, (ast.JoinedStr, ast.FormattedValue, ast.BinOp, ast.Dict, ast.List, ast.Tuple)):
            if any(source(child, values) in {'environment', 'value'} for child in ast.iter_child_nodes(node)):
                return 'value'
        return ''

    def writable_open(node):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != 'open':
            return False
        mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == 'mode'), None)
        return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in 'wax+')

    def expression(node, values):
        if node is None or isinstance(node, ast.Lambda):
            return False
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
            tainted = any(source(a, values) in {'environment', 'value'} for a in node.args)
            if tainted and name in {'write', 'writelines', 'write_text', 'write_bytes', 'dump', 'print'}:
                if name == 'print':
                    return True
                if name == 'dump' and len(node.args) > 1 and (source(node.args[1], values) == 'file' or writable_open(node.args[1])):
                    return True
                if isinstance(node.func, ast.Attribute):
                    receiver = node.func.value
                    if source(receiver, values) == 'file' or writable_open(receiver) or name in {'write_text', 'write_bytes'}:
                        return True
            if isinstance(node.func, ast.Name) and name in functions and name not in entered and len(entered) < 32:
                entered.add(name)
                local = dict(values)
                for parameter, arg in zip(functions[name].args.args, node.args):
                    local[parameter.arg] = source(arg, values)
                if statements(functions[name].body, local):
                    return True
        return any(expression(child, values) for child in ast.iter_child_nodes(node))

    def statements(body, values):
        nonlocal steps
        for node in body:
            steps += 1
            if steps > 20000:
                return False
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                if expression(node.value, values):
                    return True
                kind = 'file' if writable_open(node.value) else source(node.value, values)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = kind
                continue
            if isinstance(node, (ast.With, ast.AsyncWith)):
                local = dict(values)
                for item in node.items:
                    if isinstance(item.optional_vars, ast.Name) and writable_open(item.context_expr):
                        local[item.optional_vars.id] = 'file'
                if statements(node.body, local):
                    return True
                continue
            if isinstance(node, (ast.For, ast.AsyncFor)):
                local = dict(values)
                if source(node.iter, values) == 'environment':
                    if isinstance(node.target, ast.Name):
                        method = getattr(getattr(node.iter, 'func', None), 'attr', '')
                        local[node.target.id] = 'value' if method == 'values' else 'key'
                    elif isinstance(node.target, (ast.Tuple, ast.List)):
                        for index, item in enumerate(node.target.elts):
                            if isinstance(item, ast.Name):
                                local[item.id] = 'key' if index == 0 else 'value'
                if statements(node.body, local) or statements(node.orelse, dict(values)):
                    return True
                continue
            if isinstance(node, (ast.If, ast.While)):
                if expression(node.test, values):
                    return True
                branches = [node.body, node.orelse]
                if isinstance(node.test, ast.Constant):
                    branches = [node.body if node.test.value else node.orelse]
                if any(statements(branch, dict(values)) for branch in branches):
                    return True
                continue
            if isinstance(node, ast.Try):
                branches = [node.body, node.orelse, node.finalbody] + [h.body for h in node.handlers]
                if any(statements(branch, dict(values)) for branch in branches):
                    return True
                continue
            if expression(node, values):
                return True
            if isinstance(node, (ast.Return, ast.Raise)):
                break
        return False

    return statements(tree.body, {})
