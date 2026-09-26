"""Bounded WSGI request-body-to-log analysis for generated Python code.

Interprets only abstract values. It never imports or executes inspected code.
Unknown call results retain argument taint; a sanitizer name is not proof.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class Value:
    tainted: bool = False
    literal: object = None
    log_handle: bool = False


def merged(*values):
    return Value(any(v.tainted for v in values), log_handle=any(v.log_handle for v in values))


def name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return name(node.value) + '.' + node.attr
    return ''


def returns_unconditionally(body):
    for node in body:
        if isinstance(node, ast.Return):
            return True
        if isinstance(node, ast.If):
            if isinstance(node.test, ast.Constant):
                if returns_unconditionally(node.body if node.test.value else node.orelse):
                    return True
            elif returns_unconditionally(node.body) and returns_unconditionally(node.orelse):
                return True
        if isinstance(node, ast.With) and returns_unconditionally(node.body):
            return True
    return False


class RequestLogReview:
    def __init__(self, methods):
        self.methods = methods
        self.attributes = {}
        self.found = False
        self.steps = 0
        self.stack = []

    def call(self, method, args):
        if method in self.stack or len(self.stack) >= 8:
            return merged(*args)
        fn = self.methods[method]
        env = dict(zip((a.arg for a in fn.args.args[1:]), args))
        self.stack.append(method)
        result = self.statements(fn.body, env)
        self.stack.pop()
        return result

    def expression(self, node, env):
        self.steps += 1
        if node is None or self.steps > 12000:
            return Value()
        if isinstance(node, ast.Constant):
            return Value(literal=node.value)
        if isinstance(node, ast.Name):
            return env.get(node.id, Value())
        if isinstance(node, ast.Attribute):
            return self.attributes.get(name(node), self.expression(node.value, env))
        if isinstance(node, ast.Subscript):
            key = self.expression(node.slice, env).literal
            if key == 'wsgi.input':
                return Value(tainted=True)
            return self.expression(node.value, env)
        if isinstance(node, ast.Call):
            target = name(node.func)
            args = [self.expression(a, env) for a in node.args]
            args += [self.expression(k.value, env) for k in node.keywords]
            receiver = self.expression(node.func.value, env) if isinstance(node.func, ast.Attribute) else Value()
            if target.startswith('self.') and target[5:] in self.methods:
                return self.call(target[5:], args)
            if target in {'len', 'bool', 'type', 'isinstance'}:
                return Value()
            if target == 'open' and args:
                path = args[0].literal
                mode = args[1].literal if len(args) > 1 else 'r'
                log = isinstance(path, str) and (path.endswith('.log') or 'logs' in PurePosixPath(path).parts)
                return Value(log_handle=bool(log and isinstance(mode, str) and any(c in mode for c in 'wax+')))
            if target == 'os.path.join' and args and all(isinstance(v.literal, str) for v in args):
                return Value(literal=str(PurePosixPath(*(v.literal for v in args))))
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {'write', 'writelines'} and receiver.log_handle and any(v.tainted for v in args):
                    self.found = True
                if node.func.attr in {'debug', 'info', 'warning', 'error', 'critical', 'log'} and target.split('.')[0] in {'logging', 'logger'}:
                    if any(v.tainted for v in args):
                        self.found = True
            return merged(receiver, *args)
        if isinstance(node, (ast.JoinedStr, ast.BinOp, ast.FormattedValue, ast.List, ast.Tuple, ast.Dict)):
            return merged(*(self.expression(n, env) for n in ast.iter_child_nodes(node)))
        return Value()

    def assign(self, target, value, env):
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, ast.Attribute) and name(target).startswith('self.'):
            self.attributes[name(target)] = value

    def statements(self, body, env):
        returns = []
        for node in body:
            if self.steps > 12000:
                break
            if isinstance(node, ast.Assign):
                value = self.expression(node.value, env)
                for target in node.targets:
                    self.assign(target, value, env)
            elif isinstance(node, ast.AnnAssign):
                self.assign(node.target, self.expression(node.value, env), env)
            elif isinstance(node, ast.AugAssign):
                self.assign(node.target, merged(self.expression(node.target, env), self.expression(node.value, env)), env)
            elif isinstance(node, ast.Expr):
                self.expression(node.value, env)
            elif isinstance(node, ast.Return):
                returns.append(self.expression(node.value, env))
                break
            elif isinstance(node, ast.With):
                for item in node.items:
                    self.assign(item.optional_vars, self.expression(item.context_expr, env), env)
                returns.append(self.statements(node.body, env))
                if returns_unconditionally(node.body):
                    break
            elif isinstance(node, ast.If):
                condition = self.expression(node.test, env).literal
                if isinstance(condition, bool):
                    branch = node.body if condition else node.orelse
                    returns.append(self.statements(branch, env))
                    if returns_unconditionally(branch):
                        break
                else:
                    left, right = dict(env), dict(env)
                    returns.extend((self.statements(node.body, left), self.statements(node.orelse, right)))
                    for key in left.keys() | right.keys():
                        a, b = left.get(key, Value()), right.get(key, Value())
                        env[key] = a if a == b else merged(a, b)
                    if returns_unconditionally(node.body) and returns_unconditionally(node.orelse):
                        break
            elif isinstance(node, ast.Try):
                returns.append(self.statements(node.body, env))
                for handler in node.handlers:
                    returns.append(self.statements(handler.body, dict(env)))
                returns.append(self.statements(node.orelse + node.finalbody, env))
            # Nested function definitions are not executed by declaration.
        return merged(*returns)


def request_body_logging_risk(content: str) -> bool:
    if not content or len(content) > 500000:
        return False
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return False
    if sum(1 for _ in ast.walk(tree)) > 20000:
        return False
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        entry = methods.get('__call__')
        if entry is None or len(entry.args.args) != 3:
            continue
        # WSGI callable must actually access the WSGI input in a reachable method.
        review = RequestLogReview(methods)
        if '__init__' in methods:
            review.call('__init__', [Value()] * (len(methods['__init__'].args.args) - 1))
        review.call('__call__', [Value(), Value()])
        if review.found:
            return True
    return False
