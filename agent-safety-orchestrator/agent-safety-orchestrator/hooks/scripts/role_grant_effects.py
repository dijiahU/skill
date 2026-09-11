"""Resolve declared role aliases into approval-sensitive grant artifacts.

This is snapshot-only abstract interpretation. It does not execute a script,
activate a grant, or trust approval flags supplied by the script itself.
"""
from __future__ import annotations

import ast
import json
import posixpath
import re
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Value:
    literal: Any = None
    roles: frozenset[str] = frozenset()
    path: str = ''
    scope: frozenset[str] = frozenset()


def role_grant_risk(source: str, cwd: str, snapshot: Mapping[str, str]) -> str:
    if len(source) > 500000:
        return ''
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return ''
    if sum(1 for _ in ast.walk(tree)) > 20000:
        return ''
    protected = set()
    policies = {}
    for path, content in snapshot.items():
        if not path.endswith('.json') or len(content) > 500000:
            continue
        try:
            config = json.loads(content)
        except (ValueError, TypeError):
            continue
        if not isinstance(config, dict) or not isinstance(config.get('role_aliases'), dict):
            continue
        metadata = config.get('metadata', {})
        if isinstance(metadata, dict):
            roles = {role for role, policy in metadata.items()
                     if isinstance(policy, dict) and policy.get('requires_security_approval') is True}
            policies[path] = frozenset(roles)
            protected.update(roles)
    if not protected:
        return ''
    found = False
    steps = 0

    def tagged(raw, inherited=frozenset(), scope=frozenset()):
        roles = inherited | ({raw} if isinstance(raw, str) and raw in scope else set())
        return Value(raw, frozenset(roles), scope=scope)

    def expr(node, env):
        nonlocal found, steps
        steps += 1
        if steps > 10000 or node is None:
            return Value()
        if isinstance(node, ast.Constant):
            return tagged(node.value)
        if isinstance(node, ast.Name):
            return env.get(node.id, Value())
        if isinstance(node, ast.Subscript):
            parent, key = expr(node.value, env), expr(node.slice, env)
            if isinstance(parent.literal, dict) and isinstance(key.literal, (str, int)):
                return tagged(parent.literal.get(key.literal), parent.roles, parent.scope)
            return Value(roles=parent.roles)
        if isinstance(node, ast.JoinedStr):
            parts = [expr(v.value if isinstance(v, ast.FormattedValue) else v, env) for v in node.values]
            return Value(roles=frozenset().union(*(v.roles for v in parts)))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = expr(node.left, env), expr(node.right, env)
            literal = left.literal + right.literal if isinstance(left.literal, str) and isinstance(right.literal, str) else None
            return Value(literal, left.roles | right.roles)
        if isinstance(node, ast.Call):
            args = [expr(a, env) for a in node.args]
            if isinstance(node.func, ast.Name) and node.func.id == 'Path' and args and isinstance(args[0].literal, str):
                raw = args[0].literal
                return Value(path=posixpath.normpath(raw if raw.startswith('/') else posixpath.join(cwd, raw)))
            if isinstance(node.func, ast.Attribute):
                obj = expr(node.func.value, env)
                method = node.func.attr
                if method == 'read_text' and obj.path:
                    return tagged(snapshot.get(obj.path), scope=policies.get(obj.path, frozenset()))
                if method == 'strip' and isinstance(obj.literal, str):
                    return tagged(obj.literal.strip(), obj.roles, obj.scope)
                if method == 'loads' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'json' and args:
                    try:
                        return tagged(json.loads(args[0].literal), scope=args[0].scope)
                    except (ValueError, TypeError):
                        return Value()
                if method == 'write_text' and obj.path and args:
                    leaf = posixpath.basename(obj.path)
                    if re.fullmatch(r'(?:role[_-])?grants?(?:\.(?:out|json|csv|txt))?', leaf, re.I) and args[0].roles:
                        found = True
                if method in {'format', 'join'}:
                    return Value(roles=obj.roles | frozenset().union(*(a.roles for a in args)))
            return Value()
        return Value()

    def statements(body, env):
        for node in body:
            if steps > 10000:
                break
            if isinstance(node, ast.Assign):
                value = expr(node.value, env)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        env[target.id] = value
            elif isinstance(node, ast.Expr):
                expr(node.value, env)
            elif isinstance(node, ast.If):
                condition = expr(node.test, env).literal
                if isinstance(condition, bool):
                    statements(node.body if condition else node.orelse, env)
                elif isinstance(node.test, ast.Constant):
                    statements(node.body if node.test.value else node.orelse, env)
                else:
                    left, right = dict(env), dict(env)
                    statements(node.body, left)
                    statements(node.orelse, right)
                    for key in left.keys() | right.keys():
                        a, b = left.get(key, Value()), right.get(key, Value())
                        env[key] = a if a == b else Value(roles=a.roles | b.roles)
            elif isinstance(node, (ast.Return, ast.Raise)):
                break
    statements(tree.body, {})
    return 'resolved role requires security approval but is materialized as a grant artifact without an independently verified approval' if found else ''
