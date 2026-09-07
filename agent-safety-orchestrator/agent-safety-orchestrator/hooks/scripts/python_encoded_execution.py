#!/usr/bin/env python3
"""Bounded static review of encoded Python passed to ``exec`` or ``eval``.

This module intentionally implements a small constant evaluator.  It never
executes, evaluates, compiles, imports, or unmarshals the inspected program.
Callers can use :func:`python_encoded_execution_risk` while reviewing the
contents of a Python automation controller.
"""

from __future__ import annotations

import ast
import base64
import binascii
import codecs
import posixpath
import re
import zlib
from dataclasses import dataclass
from typing import Any


_MAX_SOURCE = 1_000_000
_MAX_VALUE = 65_536
_MAX_SEQUENCE = 16_384
_MAX_STEPS = 20_000
_MAX_CALL_DEPTH = 12

_ENCODING_TRANSFORMS = {
    "base64",
    "hex",
    "integer chr/join",
    "rot13",
    "zlib",
}

_PROTECTED_DELETE_PART = re.compile(
    r"(?:^|/)(?:src|source|data|uploads?|exports?|\.git|\.ssh|\.aws|"
    r"etc|var/lib)(?:/|$)|"
    r"(?:^|/)(?:\.env|[^/]+\.(?:db|sqlite|sqlite3))$",
    re.IGNORECASE,
)
_SAFE_REGENERABLE_DELETE = re.compile(
    r"(?:^|/)(?:tmp|temp|cache|caches|build|dist|target|\.cache)(?:/|$)",
    re.IGNORECASE,
)
_SHELL_DESTRUCTIVE = re.compile(
    r"\brm\s+(?:-[A-Za-z]*[rR][A-Za-z]*f?|-[A-Za-z]*f[A-Za-z]*[rR])\b|"
    r"\b(?:DROP\s+(?:TABLE|DATABASE)|TRUNCATE\s+TABLE)\b|"
    r"\b(?:mkfs(?:\.[a-z0-9]+)?|wipefs|shred)\b|"
    r"\b(?:dd\b[^\n;&|]*\bof\s*=\s*/dev/)",
    re.IGNORECASE,
)
_SHELL_EXFILTRATION = re.compile(
    r"(?:\bcurl\b|\bwget\b|requests?\.(?:post|put|get))[^\n]{0,500}"
    r"(?:/etc/(?:shadow|passwd)|\.ssh/|\.aws/|\.env\b|TOKEN|PASSWORD)|"
    r"(?:/etc/(?:shadow|passwd)|\.ssh/|\.aws/|\.env\b|TOKEN|PASSWORD)"
    r"[^\n]{0,500}(?:\bcurl\b|\bwget\b|requests?\.(?:post|put|get))",
    re.IGNORECASE,
)
_SHELL_REVERSE = re.compile(
    r"/dev/(?:tcp|udp)/|\b(?:nc|ncat|netcat)\b[^\n;&|]*\s-e\s|"
    r"\b(?:bash|sh)\s+-i\b",
    re.IGNORECASE,
)
_PERSISTENCE = re.compile(
    r"(?:\.ssh/authorized_keys|\.bashrc|\.profile|\.zshrc|"
    r"/etc/(?:cron|systemd|sudoers)|\.git/hooks/)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PythonEncodedExecutionFinding:
    """One reachable encoded execution sink and its statically recovered text."""

    line: int
    sink: str
    transforms: tuple[str, ...]
    decoded_source: str
    effect: str

    @property
    def decoded_excerpt(self) -> str:
        return " ".join(self.decoded_source.split())[:240]

    @property
    def reason(self) -> str:
        transforms = ", ".join(self.transforms)
        return (
            f"encoded Python reaches {self.sink} after {transforms}; "
            f"decoded payload {self.effect}"
        )


@dataclass(frozen=True)
class _Value:
    value: Any
    transforms: tuple[str, ...] = ()

    def with_transform(self, transform: str) -> "_Value":
        return _Value(self.value, _merge_transforms(self.transforms, (transform,)))


class _BudgetExceeded(Exception):
    pass


class _Budget:
    def __init__(self) -> None:
        self.remaining = _MAX_STEPS

    def spend(self, amount: int = 1) -> None:
        self.remaining -= amount
        if self.remaining < 0:
            raise _BudgetExceeded


def _merge_transforms(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item not in merged:
                merged.append(item)
    return tuple(merged)


def _qualified_name(node: ast.AST, aliases: dict[str, str]) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return ""
    root = aliases.get(current.id, current.id)
    suffix = ".".join(reversed(parts))
    return root + ("." + suffix if suffix else "")


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for item in node.elts:
            names.update(_target_names(item))
        return names
    return set()


def _function_local_names(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    """Return lexical local bindings without entering nested scopes."""

    names = {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }
    if function.args.vararg:
        names.add(function.args.vararg.arg)
    if function.args.kwarg:
        names.add(function.args.kwarg.arg)

    class BindingVisitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Store):
                names.add(node.id)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                names.add(alias.asname or alias.name)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            names.add(node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            names.add(node.name)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            names.add(node.name)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return

    visitor = BindingVisitor()
    for statement in function.body:
        visitor.visit(statement)
    return names


def _bounded(value: Any) -> bool:
    if isinstance(value, (str, bytes, bytearray)):
        return len(value) <= _MAX_VALUE
    if isinstance(value, (list, tuple)):
        return len(value) <= _MAX_SEQUENCE
    return isinstance(value, (bool, int, type(None)))


def _bytes(value: _Value) -> bytes | None:
    if isinstance(value.value, bytes):
        return value.value
    if isinstance(value.value, bytearray):
        return bytes(value.value)
    if isinstance(value.value, str):
        try:
            return value.value.encode("ascii")
        except UnicodeEncodeError:
            return None
    return None


def _string(value: _Value) -> str | None:
    if isinstance(value.value, str):
        return value.value
    if isinstance(value.value, (bytes, bytearray)):
        try:
            return bytes(value.value).decode("utf-8")
        except UnicodeDecodeError:
            return None
    return None


def _zlib_decompress_bounded(raw: bytes) -> bytes | None:
    try:
        decoder = zlib.decompressobj()
        result = decoder.decompress(raw, _MAX_VALUE + 1)
    except zlib.error:
        return None
    if len(result) > _MAX_VALUE or decoder.unconsumed_tail or not decoder.eof:
        return None
    return result


class _StaticReviewer:
    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.budget = _Budget()
        self.aliases: dict[str, str] = {}
        self.functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.findings: list[PythonEncodedExecutionFinding] = []
        self.active_calls: set[str] = set()

    def review(self) -> list[PythonEncodedExecutionFinding]:
        environment: dict[str, _Value] = {"__name__": _Value("__main__")}
        try:
            self._run_block(self.tree.body, environment, set(), 0)
        except _BudgetExceeded:
            pass
        return self.findings

    def _eval(self, node: ast.AST | None, environment: dict[str, _Value]) -> _Value | None:
        self.budget.spend()
        if node is None:
            return None
        if isinstance(node, ast.Constant) and _bounded(node.value):
            return _Value(node.value)
        if isinstance(node, ast.Name):
            return environment.get(node.id)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            if len(node.elts) > _MAX_SEQUENCE:
                return None
            values = [self._eval(item, environment) for item in node.elts]
            if any(item is None for item in values):
                return None
            raw = [item.value for item in values if item is not None]
            transforms = _merge_transforms(*(
                item.transforms for item in values if item is not None
            ))
            return _Value(raw, transforms)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._eval(node.left, environment)
            right = self._eval(node.right, environment)
            if left is None or right is None:
                return None
            try:
                value = left.value + right.value
            except (TypeError, ValueError):
                return None
            if not _bounded(value):
                return None
            return _Value(value, _merge_transforms(left.transforms, right.transforms))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = self._eval(node.operand, environment)
            return _Value(not value.value) if value is not None else None
        if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
            left = self._eval(node.left, environment)
            right = self._eval(node.comparators[0], environment)
            if left is None or right is None:
                return None
            operator = node.ops[0]
            if isinstance(operator, ast.Eq):
                return _Value(left.value == right.value)
            if isinstance(operator, ast.NotEq):
                return _Value(left.value != right.value)
            if isinstance(operator, ast.Is):
                return _Value(left.value is right.value)
            if isinstance(operator, ast.IsNot):
                return _Value(left.value is not right.value)
            return None
        if isinstance(node, ast.Subscript):
            container = self._eval(node.value, environment)
            if container is None:
                return None
            if isinstance(node.slice, ast.Slice):
                lower = self._eval(node.slice.lower, environment)
                upper = self._eval(node.slice.upper, environment)
                step = self._eval(node.slice.step, environment)
                try:
                    value = container.value[slice(
                        lower.value if lower else None,
                        upper.value if upper else None,
                        step.value if step else None,
                    )]
                except (TypeError, ValueError, IndexError):
                    return None
            else:
                index = self._eval(node.slice, environment)
                if index is None:
                    return None
                try:
                    value = container.value[index.value]
                except (TypeError, ValueError, IndexError, KeyError):
                    return None
            return _Value(value, container.transforms) if _bounded(value) else None
        if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
            return self._eval_comprehension(node, environment)
        if not isinstance(node, ast.Call):
            return None

        name = _qualified_name(node.func, self.aliases)
        arguments = [self._eval(argument, environment) for argument in node.args]
        if any(argument is None for argument in arguments):
            return None
        values = [argument for argument in arguments if argument is not None]
        transforms = _merge_transforms(*(value.transforms for value in values))

        if name in {"chr", "builtins.chr"} and len(values) == 1:
            try:
                return _Value(chr(values[0].value), _merge_transforms(transforms, ("chr",)))
            except (TypeError, ValueError, OverflowError):
                return None
        if name in {"bytes", "builtins.bytes", "bytearray", "builtins.bytearray"} and len(values) == 1:
            try:
                value = bytes(values[0].value)
            except (TypeError, ValueError, OverflowError):
                return None
            return _Value(value, transforms) if _bounded(value) else None
        if name in {"bytes.fromhex", "bytearray.fromhex"} and len(values) == 1:
            source = _string(values[0])
            if source is None or len(source) > _MAX_VALUE * 2:
                return None
            try:
                value = bytes.fromhex(source)
            except ValueError:
                return None
            return _Value(value, _merge_transforms(transforms, ("hex",)))
        if name in {
            "base64.b64decode", "base64.standard_b64decode",
            "base64.urlsafe_b64decode",
        } and values:
            raw = _bytes(values[0])
            if raw is None or len(raw) > _MAX_VALUE * 2:
                return None
            try:
                value = (
                    base64.urlsafe_b64decode(raw)
                    if name.endswith("urlsafe_b64decode")
                    else base64.b64decode(raw, validate=False)
                )
            except (binascii.Error, ValueError):
                return None
            if not _bounded(value):
                return None
            return _Value(value, _merge_transforms(transforms, ("base64",)))
        if name == "codecs.decode" and len(values) >= 2:
            encoding = _string(values[1])
            source = values[0].value
            if not encoding or not isinstance(source, (str, bytes)):
                return None
            normalized = encoding.lower().replace("-", "_")
            if normalized not in {"rot13", "rot_13", "hex", "base64"}:
                return None
            try:
                value = codecs.decode(source, encoding)
            except (LookupError, TypeError, ValueError, binascii.Error):
                return None
            if not _bounded(value):
                return None
            label = "rot13" if normalized in {"rot13", "rot_13"} else normalized
            return _Value(value, _merge_transforms(transforms, (label,)))
        if name == "zlib.decompress" and values:
            raw = _bytes(values[0])
            value = _zlib_decompress_bounded(raw) if raw is not None else None
            if value is None:
                return None
            return _Value(value, _merge_transforms(transforms, ("zlib",)))
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"decode", "encode"}:
            receiver = self._eval(node.func.value, environment)
            if receiver is None:
                return None
            encoding = _string(values[0]) if values else "utf-8"
            if not encoding:
                return None
            try:
                if node.func.attr == "decode" and isinstance(receiver.value, (bytes, bytearray)):
                    value = bytes(receiver.value).decode(encoding)
                elif node.func.attr == "encode" and isinstance(receiver.value, str):
                    value = receiver.value.encode(encoding)
                else:
                    return None
            except (LookupError, UnicodeError):
                return None
            return _Value(value, _merge_transforms(receiver.transforms, transforms))
        if isinstance(node.func, ast.Attribute) and node.func.attr == "join":
            receiver = self._eval(node.func.value, environment)
            if receiver is None or not isinstance(receiver.value, (str, bytes)) or len(values) != 1:
                return None
            sequence = values[0]
            if not isinstance(sequence.value, list) or len(sequence.value) > _MAX_SEQUENCE:
                return None
            try:
                value = receiver.value.join(sequence.value)
            except (TypeError, ValueError):
                return None
            if not _bounded(value):
                return None
            combined = _merge_transforms(receiver.transforms, sequence.transforms)
            if "chr" in combined:
                combined = tuple(item for item in combined if item != "chr")
                combined = _merge_transforms(combined, ("integer chr/join",))
            return _Value(value, combined)
        if name in {"compile", "builtins.compile"} and values:
            # Preserve source text as data.  Python's compile() is never called.
            return _Value(values[0].value, _merge_transforms(transforms, ("compile wrapper",)))
        return None

    def _eval_comprehension(
        self,
        node: ast.GeneratorExp | ast.ListComp,
        environment: dict[str, _Value],
    ) -> _Value | None:
        if len(node.generators) != 1 or node.generators[0].is_async:
            return None
        generator = node.generators[0]
        iterable = self._eval(generator.iter, environment)
        if iterable is None or not isinstance(iterable.value, (list, tuple)):
            return None
        if len(iterable.value) > _MAX_SEQUENCE or not isinstance(generator.target, ast.Name):
            return None
        results: list[Any] = []
        transforms = iterable.transforms
        for item in iterable.value:
            self.budget.spend()
            local = dict(environment)
            local[generator.target.id] = _Value(item, iterable.transforms)
            conditions = [self._eval(condition, local) for condition in generator.ifs]
            if any(condition is None for condition in conditions):
                return None
            if not all(bool(condition.value) for condition in conditions if condition is not None):
                continue
            value = self._eval(node.elt, local)
            if value is None:
                return None
            results.append(value.value)
            transforms = _merge_transforms(transforms, value.transforms)
        return _Value(results, transforms)

    def _assign(self, target: ast.AST, value: _Value, environment: dict[str, _Value]) -> None:
        if isinstance(target, ast.Name):
            environment[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value.value, (list, tuple)):
            if len(target.elts) == len(value.value):
                for child, item in zip(target.elts, value.value):
                    self._assign(child, _Value(item, value.transforms), environment)

    def _invalidate(self, target: ast.AST, environment: dict[str, _Value]) -> None:
        for name in _target_names(target):
            environment.pop(name, None)
            self.aliases.pop(name, None)

    def _inspect_sink(
        self,
        node: ast.Call,
        environment: dict[str, _Value],
        shadowed: set[str],
    ) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in shadowed:
            return
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in shadowed
        ):
            return
        name = _qualified_name(node.func, self.aliases)
        if name not in {"exec", "eval", "builtins.exec", "builtins.eval"} or not node.args:
            return
        payload = self._eval(node.args[0], environment)
        if payload is None or not (_ENCODING_TRANSFORMS & set(payload.transforms)):
            return
        text = _string(payload)
        if text is None or len(text) > _MAX_VALUE:
            return
        effect = _dangerous_decoded_effect(text, sink=name.rsplit(".", 1)[-1])
        self.findings.append(PythonEncodedExecutionFinding(
            line=getattr(node, "lineno", 0),
            sink=name,
            transforms=tuple(
                item for item in payload.transforms if item != "compile wrapper"
            ),
            decoded_source=text,
            effect=effect,
        ))

    def _inspect_expression(
        self,
        node: ast.AST,
        environment: dict[str, _Value],
        shadowed: set[str],
        depth: int,
    ) -> None:
        self.budget.spend()
        if isinstance(node, ast.Lambda):
            return
        if isinstance(node, ast.BoolOp):
            for value_node in node.values:
                self._inspect_expression(value_node, environment, shadowed, depth)
                value = self._eval(value_node, environment)
                if value is None:
                    return
                if isinstance(node.op, ast.And) and not bool(value.value):
                    return
                if isinstance(node.op, ast.Or) and bool(value.value):
                    return
            return
        if isinstance(node, ast.IfExp):
            self._inspect_expression(node.test, environment, shadowed, depth)
            condition = self._condition(node.test, environment)
            if condition is True:
                self._inspect_expression(node.body, environment, shadowed, depth)
            elif condition is False:
                self._inspect_expression(node.orelse, environment, shadowed, depth)
            return
        if isinstance(node, ast.GeneratorExp):
            # Creating a generator evaluates only its outer iterable.  Its body
            # is deferred and this helper does not prove a consumer iterates it.
            if node.generators:
                self._inspect_expression(
                    node.generators[0].iter, environment, shadowed, depth
                )
            return
        if isinstance(node, ast.Call):
            self._inspect_expression(node.func, environment, shadowed, depth)
            for argument in node.args:
                self._inspect_expression(argument, environment, shadowed, depth)
            for keyword in node.keywords:
                self._inspect_expression(keyword.value, environment, shadowed, depth)
            self._inspect_sink(node, environment, shadowed)

            if not isinstance(node.func, ast.Name):
                return
            name = node.func.id
            function = self.functions.get(name)
            if function is None or name in self.active_calls or depth >= _MAX_CALL_DEPTH:
                return
            arguments = [self._eval(argument, environment) for argument in node.args]
            local = dict(environment)
            for parameter, value in zip(function.args.args, arguments):
                if value is not None:
                    local[parameter.arg] = value
                else:
                    local.pop(parameter.arg, None)
            local_names = _function_local_names(function)
            local_shadowed = set(shadowed) | local_names
            saved_aliases = self.aliases
            saved_functions = self.functions
            self.aliases = {
                key: value
                for key, value in self.aliases.items()
                if key not in local_names
            }
            self.functions = dict(self.functions)
            for local_name in local_names:
                if local_name in self.functions:
                    self.functions.pop(local_name, None)
            self.active_calls.add(name)
            try:
                self._run_block(
                    function.body, local, local_shadowed, depth + 1
                )
            finally:
                self.active_calls.remove(name)
                self.aliases = saved_aliases
                self.functions = saved_functions
            return
        for child in ast.iter_child_nodes(node):
            self._inspect_expression(child, environment, shadowed, depth)

    def _condition(self, node: ast.AST, environment: dict[str, _Value]) -> bool | None:
        value = self._eval(node, environment)
        return bool(value.value) if value is not None else None

    def _run_block(
        self,
        statements: list[ast.stmt],
        environment: dict[str, _Value],
        shadowed: set[str],
        depth: int,
    ) -> bool:
        for statement in statements:
            self.budget.spend()
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                if isinstance(statement, ast.Import):
                    for alias in statement.names:
                        bound = alias.asname or alias.name.split(".", 1)[0]
                        self.aliases[bound] = alias.name
                        shadowed.discard(bound)
                else:
                    module = statement.module or ""
                    for alias in statement.names:
                        bound = alias.asname or alias.name
                        self.aliases[bound] = f"{module}.{alias.name}"
                        shadowed.discard(bound)
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[statement.name] = statement
                shadowed.add(statement.name)
                environment.pop(statement.name, None)
                self.aliases.pop(statement.name, None)
                continue
            if isinstance(statement, ast.ClassDef):
                shadowed.add(statement.name)
                environment.pop(statement.name, None)
                self.aliases.pop(statement.name, None)
                continue
            if isinstance(statement, ast.Assign):
                value = self._eval(statement.value, environment)
                self._inspect_expression(statement.value, environment, shadowed, depth)
                for target in statement.targets:
                    self._invalidate(target, environment)
                    shadowed.update(_target_names(target))
                if value is not None:
                    for target in statement.targets:
                        self._assign(target, value, environment)
                continue
            if isinstance(statement, ast.AnnAssign):
                value = self._eval(statement.value, environment)
                if statement.value is not None:
                    self._inspect_expression(statement.value, environment, shadowed, depth)
                self._invalidate(statement.target, environment)
                shadowed.update(_target_names(statement.target))
                if value is not None:
                    self._assign(statement.target, value, environment)
                continue
            if isinstance(statement, ast.AugAssign):
                current = self._eval(statement.target, environment)
                addition = self._eval(statement.value, environment)
                self._inspect_expression(statement.value, environment, shadowed, depth)
                self._invalidate(statement.target, environment)
                shadowed.update(_target_names(statement.target))
                if current is not None and addition is not None and isinstance(statement.op, ast.Add):
                    try:
                        value = current.value + addition.value
                    except (TypeError, ValueError):
                        value = None
                    if value is not None and _bounded(value):
                        self._assign(statement.target, _Value(
                            value, _merge_transforms(current.transforms, addition.transforms)
                        ), environment)
                continue
            if isinstance(statement, ast.Expr):
                self._inspect_expression(statement.value, environment, shadowed, depth)
                continue
            if isinstance(statement, ast.If):
                self._inspect_expression(statement.test, environment, shadowed, depth)
                condition = self._condition(statement.test, environment)
                if condition is True:
                    if self._run_block(statement.body, environment, shadowed, depth):
                        return True
                elif condition is False:
                    if self._run_block(statement.orelse, environment, shadowed, depth):
                        return True
                continue
            if isinstance(statement, (ast.For, ast.AsyncFor)):
                self._inspect_expression(statement.iter, environment, shadowed, depth)
                iterable = self._eval(statement.iter, environment)
                if iterable is not None and isinstance(iterable.value, (list, tuple)):
                    for item in iterable.value[:_MAX_SEQUENCE]:
                        self._assign(statement.target, _Value(item, iterable.transforms), environment)
                        if self._run_block(statement.body, environment, shadowed, depth):
                            break
                continue
            if isinstance(statement, (ast.With, ast.AsyncWith)):
                for item in statement.items:
                    self._inspect_expression(
                        item.context_expr, environment, shadowed, depth
                    )
                if self._run_block(statement.body, environment, shadowed, depth):
                    return True
                continue
            if isinstance(statement, ast.Try):
                self._run_block(statement.body, environment, shadowed, depth)
                self._run_block(statement.finalbody, environment, shadowed, depth)
                continue
            if isinstance(statement, ast.Return):
                if statement.value is not None:
                    self._inspect_expression(
                        statement.value, environment, shadowed, depth
                    )
                return True
        return False


def _expression_strings(node: ast.AST) -> list[str]:
    """Collect literal parts of an evaluated argument without entering code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for item in node.elts:
            values.extend(_expression_strings(item))
        return values
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _expression_strings(node.left) + _expression_strings(node.right)
    if isinstance(node, ast.JoinedStr):
        values: list[str] = []
        for item in node.values:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                values.append(item.value)
        return values
    return []


def _dangerous_path(value: str | None, *, recursive: bool = False) -> bool:
    if value is None:
        return recursive
    normalized = posixpath.normpath(value.replace("\\", "/"))
    if _SAFE_REGENERABLE_DELETE.search(normalized) and not _PROTECTED_DELETE_PART.search(normalized):
        return False
    return normalized in {
        "/", ".", "..", "~", "/home", "/root", "/etc", "/var", "/var/lib"
    } or bool(_PROTECTED_DELETE_PART.search(normalized))


def _constant_argument(call: ast.Call, index: int = 0) -> str | None:
    if len(call.args) <= index:
        return None
    value = call.args[index]
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def _decoded_call_effect(
    call: ast.Call,
    aliases: dict[str, str],
    shadowed: set[str],
) -> str:
    if isinstance(call.func, ast.Name) and call.func.id in shadowed:
        return ""
    if (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in shadowed
    ):
        return ""
    name = _qualified_name(call.func, aliases)
    target = _constant_argument(call)
    if name == "shutil.rmtree" and _dangerous_path(target, recursive=True):
        return "recursively deletes protected or non-regenerable files"
    if name == "os.removedirs" and _dangerous_path(target, recursive=True):
        return "recursively removes protected directories"
    if name in {"os.remove", "os.unlink", "os.rmdir"} and _dangerous_path(target):
        return "deletes a protected file or directory"
    if name in {
        "os.system", "os.popen", "subprocess.run", "subprocess.Popen",
        "subprocess.call", "subprocess.check_call", "subprocess.check_output",
    }:
        command = " ".join(
            part for argument in call.args for part in _expression_strings(argument)
        )
        if _SHELL_DESTRUCTIVE.search(command):
            return "launches a destructive shell or database command"
        if _SHELL_EXFILTRATION.search(command):
            return "sends credential or secret material over the network"
        if _SHELL_REVERSE.search(command):
            return "opens an interactive or reverse network shell"
        if _PERSISTENCE.search(command) and re.search(r">|tee|cp|install|append", command, re.I):
            return "modifies a persistent startup or authorization target"
    if name in {"open", "builtins.open", "io.open"} and target and _PERSISTENCE.search(target):
        mode = _constant_argument(call, 1) or "r"
        if any(character in mode for character in "wax+"):
            return "writes a persistent startup or authorization target"
    return ""


def _simple_condition(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = _simple_condition(node.operand)
        return not value if value is not None else None
    if (
        isinstance(node, ast.Compare)
        and len(node.ops) == len(node.comparators) == 1
        and isinstance(node.left, ast.Name)
        and node.left.id == "__name__"
        and isinstance(node.comparators[0], ast.Constant)
    ):
        right = node.comparators[0].value
        if isinstance(node.ops[0], (ast.Eq, ast.Is)):
            return "__main__" == right
        if isinstance(node.ops[0], (ast.NotEq, ast.IsNot)):
            return "__main__" != right
    return None


class _DecodedEffectReviewer:
    """Small execution-order reviewer for an already recovered payload."""

    def __init__(self, tree: ast.Module | ast.Expression) -> None:
        self.tree = tree
        self.steps = _Budget()
        self.active: set[str] = set()

    def review(self) -> str:
        try:
            if isinstance(self.tree, ast.Expression):
                return self._expression(self.tree.body, {}, {}, set(), 0)
            return self._block(self.tree.body, {}, {}, set(), 0)
        except _BudgetExceeded:
            return ""

    def _expression(
        self,
        node: ast.AST,
        aliases: dict[str, str],
        functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
        shadowed: set[str],
        depth: int,
    ) -> str:
        self.steps.spend()
        if isinstance(node, (ast.Lambda, ast.GeneratorExp)):
            return ""
        if isinstance(node, ast.BoolOp):
            for value_node in node.values:
                effect = self._expression(
                    value_node, aliases, functions, shadowed, depth
                )
                if effect:
                    return effect
                value = _simple_condition(value_node)
                if value is None:
                    return ""
                if isinstance(node.op, ast.And) and not value:
                    return ""
                if isinstance(node.op, ast.Or) and value:
                    return ""
            return ""
        if isinstance(node, ast.IfExp):
            effect = self._expression(node.test, aliases, functions, shadowed, depth)
            if effect:
                return effect
            condition = _simple_condition(node.test)
            if condition is None:
                return ""
            return self._expression(
                node.body if condition else node.orelse,
                aliases,
                functions,
                shadowed,
                depth,
            )
        if isinstance(node, ast.Call):
            for argument in node.args:
                effect = self._expression(argument, aliases, functions, shadowed, depth)
                if effect:
                    return effect
            for keyword in node.keywords:
                effect = self._expression(keyword.value, aliases, functions, shadowed, depth)
                if effect:
                    return effect
            effect = _decoded_call_effect(node, aliases, shadowed)
            if effect:
                return effect
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in functions
                and node.func.id not in self.active
                and depth < _MAX_CALL_DEPTH
            ):
                function = functions[node.func.id]
                local_names = _function_local_names(function)
                local_aliases = {
                    name: value for name, value in aliases.items()
                    if name not in local_names
                }
                local_functions = {
                    name: value for name, value in functions.items()
                    if name not in local_names
                }
                self.active.add(node.func.id)
                try:
                    return self._block(
                        function.body,
                        local_aliases,
                        local_functions,
                        set(shadowed) | local_names,
                        depth + 1,
                    )
                finally:
                    self.active.remove(node.func.id)
            return ""
        for child in ast.iter_child_nodes(node):
            effect = self._expression(child, aliases, functions, shadowed, depth)
            if effect:
                return effect
        return ""

    def _block(
        self,
        statements: list[ast.stmt],
        aliases: dict[str, str],
        functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
        shadowed: set[str],
        depth: int,
    ) -> str:
        for statement in statements:
            self.steps.spend()
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    aliases[bound] = alias.name
                    shadowed.discard(bound)
                continue
            if isinstance(statement, ast.ImportFrom):
                module = statement.module or ""
                for alias in statement.names:
                    bound = alias.asname or alias.name
                    aliases[bound] = f"{module}.{alias.name}"
                    shadowed.discard(bound)
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[statement.name] = statement
                aliases.pop(statement.name, None)
                shadowed.add(statement.name)
                continue
            if isinstance(statement, ast.ClassDef):
                functions.pop(statement.name, None)
                aliases.pop(statement.name, None)
                shadowed.add(statement.name)
                continue
            expression: ast.AST | None = None
            targets: list[ast.AST] = []
            if isinstance(statement, ast.Assign):
                expression = statement.value
                targets = list(statement.targets)
            elif isinstance(statement, ast.AnnAssign):
                expression = statement.value
                targets = [statement.target]
            elif isinstance(statement, ast.AugAssign):
                expression = statement.value
                targets = [statement.target]
            elif isinstance(statement, ast.Expr):
                expression = statement.value
            elif isinstance(statement, ast.Return):
                expression = statement.value
            if expression is not None:
                effect = self._expression(
                    expression, aliases, functions, shadowed, depth
                )
                if effect:
                    return effect
            for target in targets:
                for name in _target_names(target):
                    aliases.pop(name, None)
                    functions.pop(name, None)
                    shadowed.add(name)
            if isinstance(statement, ast.Return):
                return ""
            if isinstance(statement, ast.If):
                effect = self._expression(
                    statement.test, aliases, functions, shadowed, depth
                )
                if effect:
                    return effect
                condition = _simple_condition(statement.test)
                if condition is None:
                    continue
                effect = self._block(
                    statement.body if condition else statement.orelse,
                    aliases,
                    functions,
                    shadowed,
                    depth,
                )
                if effect:
                    return effect
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                for item in statement.items:
                    effect = self._expression(
                        item.context_expr, aliases, functions, shadowed, depth
                    )
                    if effect:
                        return effect
                effect = self._block(
                    statement.body, aliases, functions, shadowed, depth
                )
                if effect:
                    return effect
            elif isinstance(statement, ast.Try):
                effect = self._block(
                    statement.body, aliases, functions, shadowed, depth
                )
                if effect:
                    return effect
                effect = self._block(
                    statement.finalbody, aliases, functions, shadowed, depth
                )
                if effect:
                    return effect
        return ""


def _dangerous_decoded_effect(source: str, *, sink: str) -> str:
    """Classify effects in decoded source without evaluating that source."""
    try:
        tree = ast.parse(source, mode="eval" if sink == "eval" else "exec")
    except (SyntaxError, ValueError, RecursionError):
        return ""

    return _DecodedEffectReviewer(tree).review()


def find_python_encoded_execution(
    source: str,
) -> list[PythonEncodedExecutionFinding]:
    """Return dangerous reachable encoded-execution findings for Python source.

    Parsing, constant decoding, call-graph traversal, and decompression are all
    bounded.  Syntax errors, dynamic values, and unsupported codecs return no
    finding from this helper; other matcher rules may still act.
    """
    return [
        execution
        for execution in recover_python_encoded_executions(source)
        if execution.effect
    ]


def recover_python_encoded_executions(
    source: str,
) -> list[PythonEncodedExecutionFinding]:
    """Recover reachable encoded ``exec``/``eval`` inputs without running them.

    The returned ``decoded_source`` is suitable for a caller's existing
    semantic-risk rules.  ``effect`` is this helper's own narrow classification
    and can be empty for a recovered, apparently harmless payload.
    """
    if not isinstance(source, str) or len(source) > _MAX_SOURCE:
        return []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []
    return _StaticReviewer(tree).review()


def python_encoded_execution_risk(source: str) -> str:
    """Return the first concise risk reason, or an empty string."""
    findings = find_python_encoded_execution(source)
    return findings[0].reason if findings else ""


__all__ = [
    "PythonEncodedExecutionFinding",
    "find_python_encoded_execution",
    "python_encoded_execution_risk",
    "recover_python_encoded_executions",
]
