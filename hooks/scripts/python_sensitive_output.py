#!/usr/bin/env python3
"""Bounded review of sensitive values printed by executed Python heredocs.

The analyzer is deliberately narrow.  It extracts Python source only when a
shell heredoc is stdin for a Python interpreter that is executing in the
current command.  Heredocs used to write a script or another data file are
skipped, so their contents are not confused with an already executed program.

The Python review tracks values loaded from protected credential JSON files,
including values selected while iterating mappings and values passed through
base64 decoders.  It reports only values that reach a stdout/stderr sink;
reading a credential file, counting records, listing field names, or printing
a fixed redaction marker is not itself a finding.  Inspected code is never
executed or imported.
"""

from __future__ import annotations

import ast
import re
import shlex
from dataclasses import dataclass


_MAX_SHELL_SOURCE = 1_000_000
_MAX_PYTHON_SOURCE = 500_000
_MAX_HEREDOCS = 32
_MAX_AST_NODES = 20_000

_SENSITIVE = 1
_DECODED = 2

_PYTHON_EXECUTABLE = re.compile(r"python(?:[0-9]+(?:\.[0-9]+)*)?\Z", re.IGNORECASE)
_HEREDOC = re.compile(
    r"<<(?P<strip>-?)(?!<)[ \t]*(?P<quote>['\"]?)"
    r"(?P<delimiter>[A-Za-z_][A-Za-z0-9_-]{0,63})(?P=quote)"
)
_CREDENTIAL_JSON = re.compile(
    r"(?:^|/)(?:\.docker/config\.json|"
    r"(?:credentials?|secrets?|service[_-]?account|auth)[^/]*\.json)\Z",
    re.IGNORECASE,
)
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.DOTALL)

_OUTPUT_SINKS = {
    "print",
    "pprint",
    "sys.stdout.write",
    "sys.stderr.write",
}
_BASE64_DECODERS = {
    "base64.b64decode",
    "base64.standard_b64decode",
    "base64.urlsafe_b64decode",
    "binascii.a2b_base64",
}
_VALUE_PRESERVING_CALLS = {
    "bytes",
    "bytearray",
    "dict",
    "list",
    "set",
    "sorted",
    "str",
    "tuple",
    "json.load",
    "json.loads",
    "json.dumps",
}
_METADATA_ONLY_CALLS = {
    "bool",
    "isinstance",
    "len",
    "type",
}


@dataclass(frozen=True)
class PythonHeredoc:
    """Python source supplied to an interpreter by one executed heredoc."""

    line: int
    interpreter: str
    source: str


@dataclass(frozen=True)
class PythonSensitiveOutputFinding:
    """A sensitive Python value reaching an observable output sink."""

    line: int
    sink: str
    decoded: bool
    source_class: str = "credential-json"
    execution_context: str = "source"

    @property
    def reason(self) -> str:
        transform = " after base64 decoding" if self.decoded else ""
        subject = (
            "executed Python heredoc"
            if self.execution_context == "heredoc"
            else "Python source"
        )
        return (
            f"{subject} prints a raw value derived from a "
            f"protected credential JSON file{transform}"
        )


def _shell_tokens(text: str) -> list[str]:
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return []


def _python_interpreter(prefix: str) -> str:
    """Return the interpreter for a direct stdin execution, else ``""``."""

    tokens = _shell_tokens(prefix.strip())
    if not tokens or any(token in {";", "&", "&&", "||", "|", "<", ">", ">>"} for token in tokens):
        return ""

    while tokens and _ASSIGNMENT.fullmatch(tokens[0]):
        tokens.pop(0)
    if tokens and tokens[0] == "env":
        tokens.pop(0)
        while tokens and (tokens[0].startswith("-") or _ASSIGNMENT.fullmatch(tokens[0])):
            tokens.pop(0)
    while tokens and tokens[0] in {"command", "exec"}:
        tokens.pop(0)
    if not tokens:
        return ""

    interpreter = tokens.pop(0).rsplit("/", 1)[-1]
    if not _PYTHON_EXECUTABLE.fullmatch(interpreter):
        return ""
    if any(token in {"-c", "-m"} for token in tokens):
        return ""

    # ``python`` and ``python -`` execute stdin.  A positional script consumes
    # the heredoc as program input rather than Python source.
    positional = [token for token in tokens if not token.startswith("-")]
    if positional:
        return ""
    if any(token != "-" and not token.startswith("-") for token in tokens):
        return ""
    return interpreter


def extract_executed_python_heredocs(shell_source: str) -> list[PythonHeredoc]:
    """Extract bounded Python heredocs that are executed by the current shell.

    Every recognized heredoc body is skipped during the outer scan, including
    non-Python bodies.  This prevents Python-looking text inside
    ``cat > helper.py <<'PY'`` from being reinterpreted as a nested command.
    """

    if not isinstance(shell_source, str) or len(shell_source) > _MAX_SHELL_SOURCE:
        return []
    lines = shell_source.splitlines(keepends=True)
    findings: list[PythonHeredoc] = []
    index = 0
    while index < len(lines) and len(findings) < _MAX_HEREDOCS:
        line = lines[index]
        stripped = line.lstrip()
        if stripped.startswith("#"):
            index += 1
            continue
        match = _HEREDOC.search(line)
        if match is None:
            index += 1
            continue

        delimiter = match.group("delimiter")
        strip_tabs = bool(match.group("strip"))
        end = index + 1
        while end < len(lines):
            candidate = lines[end].rstrip("\r\n")
            if strip_tabs:
                candidate = candidate.lstrip("\t")
            if candidate == delimiter:
                break
            end += 1
        if end >= len(lines):
            break

        prefix = line[:match.start()]
        suffix = line[match.end():].strip()
        interpreter = _python_interpreter(prefix) if not suffix else ""
        if interpreter:
            body_lines = lines[index + 1:end]
            if strip_tabs:
                body_lines = [body.lstrip("\t") for body in body_lines]
            source = "".join(body_lines)
            if len(source) <= _MAX_PYTHON_SOURCE:
                findings.append(PythonHeredoc(index + 2, interpreter, source))
        index = end + 1
    return findings


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


def _assignment_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for item in node.elts:
            names.extend(_assignment_names(item))
        return names
    return []


def _string_value(node: ast.AST, strings: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return strings.get(node.id)
    if isinstance(node, ast.JoinedStr) and all(
        isinstance(item, ast.Constant) and isinstance(item.value, str)
        for item in node.values
    ):
        return "".join(item.value for item in node.values)
    return None


def _strings(node: ast.AST, strings: dict[str, str]) -> list[str]:
    values = [
        item.value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    ]
    if isinstance(node, ast.Name) and node.id in strings:
        values.append(strings[node.id])
    return values


def _sensitive_path_in(node: ast.AST, strings: dict[str, str]) -> bool:
    return any(
        _CREDENTIAL_JSON.search(value.replace("\\", "/"))
        for value in _strings(node, strings)
    )


class _Reviewer:
    """Interpret a small, definitely reached subset of Python statements."""

    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.aliases: dict[str, str] = {}
        self.taint: dict[str, int] = {}
        self.strings: dict[str, str] = {}
        self.shadowed: set[str] = set()
        self._findings: list[PythonSensitiveOutputFinding] = []
        self._seen: set[tuple[int, str]] = set()
        self._line_offset = 0

    def _call_name(self, node: ast.AST) -> str:
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in self.shadowed:
            return ""
        return _qualified_name(node, self.aliases)

    def _expr_taint(self, node: ast.AST | None) -> int:
        if node is None:
            return 0
        if isinstance(node, (ast.Lambda, ast.GeneratorExp, ast.ListComp,
                             ast.SetComp, ast.DictComp)):
            return 0
        if isinstance(node, ast.BoolOp):
            value = 0
            for item in node.values:
                value |= self._expr_taint(item)
                if isinstance(item, ast.Constant):
                    if isinstance(node.op, ast.And) and not bool(item.value):
                        break
                    if isinstance(node.op, ast.Or) and bool(item.value):
                        break
            return value
        if isinstance(node, ast.IfExp):
            if isinstance(node.test, ast.Constant):
                return self._expr_taint(
                    node.body if bool(node.test.value) else node.orelse
                )
            return 0
        if isinstance(node, ast.Name):
            return self.taint.get(node.id, 0)
        if isinstance(node, ast.Call):
            name = self._call_name(node.func)
            method = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if name in {"open", "io.open"} and node.args and _sensitive_path_in(node.args[0], self.strings):
                return _SENSITIVE
            if method in {"read_text", "read_bytes"} and _sensitive_path_in(node.func, self.strings):
                return _SENSITIVE
            argument_taint = 0
            for value in [*node.args, *(item.value for item in node.keywords)]:
                argument_taint |= self._expr_taint(value)
            receiver_taint = self._expr_taint(node.func.value) if isinstance(node.func, ast.Attribute) else 0
            combined = argument_taint | receiver_taint
            if name in _BASE64_DECODERS:
                return combined | (_DECODED if combined & _SENSITIVE else 0)
            if name in _METADATA_ONLY_CALLS or method in {"keys"}:
                return 0
            if name in _VALUE_PRESERVING_CALLS or method in {
                "decode", "encode", "get", "items", "values", "strip", "lstrip", "rstrip"
            }:
                return combined
            return 0
        if isinstance(node, ast.Subscript):
            return self._expr_taint(node.value)
        if isinstance(node, ast.Attribute):
            return self._expr_taint(node.value)
        value = 0
        for child in ast.iter_child_nodes(node):
            value |= self._expr_taint(child)
        return value

    def _set_names(self, names: list[str], value: int) -> None:
        for name in names:
            self.taint[name] = value
            self.aliases.pop(name, None)
            self.shadowed.add(name)

    def _record_string_assignment(self, target: ast.AST, value: ast.AST | None) -> None:
        literal = _string_value(value, self.strings) if value is not None else None
        for name in _assignment_names(target):
            if literal is None:
                self.strings.pop(name, None)
            else:
                self.strings[name] = literal

    def _record_sink(self, node: ast.Call) -> None:
        name = self._call_name(node.func)
        if name not in _OUTPUT_SINKS:
            return
        if name == "print":
            file_args = [item.value for item in node.keywords if item.arg == "file"]
            if file_args and not any(
                self._call_name(value) in {"sys.stdout", "sys.stderr"}
                for value in file_args
            ):
                return
        value = 0
        for argument in node.args:
            value |= self._expr_taint(argument)
        for item in node.keywords:
            if item.arg in {"sep", "end"}:
                value |= self._expr_taint(item.value)
        if not value & _SENSITIVE:
            return
        key = (self._line_offset + node.lineno, name)
        if key in self._seen:
            return
        self._seen.add(key)
        self._findings.append(PythonSensitiveOutputFinding(
            line=key[0], sink=name, decoded=bool(value & _DECODED),
        ))

    def _review_expression(self, node: ast.AST | None) -> None:
        if node is None:
            return
        if isinstance(node, (ast.Lambda, ast.GeneratorExp, ast.ListComp,
                             ast.SetComp, ast.DictComp)):
            return
        if isinstance(node, ast.BoolOp):
            for item in node.values:
                self._review_expression(item)
                if isinstance(item, ast.Constant):
                    if isinstance(node.op, ast.And) and not bool(item.value):
                        break
                    if isinstance(node.op, ast.Or) and bool(item.value):
                        break
            return
        if isinstance(node, ast.IfExp):
            self._review_expression(node.test)
            if isinstance(node.test, ast.Constant):
                self._review_expression(
                    node.body if bool(node.test.value) else node.orelse
                )
            return
        if isinstance(node, ast.Call):
            self._record_sink(node)
        for child in ast.iter_child_nodes(node):
            self._review_expression(child)

    def _bind_import(self, node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            for item in node.names:
                bound = item.asname or item.name.split(".", 1)[0]
                self.aliases[bound] = item.name
                self.shadowed.discard(bound)
                self.taint[bound] = 0
            return
        if node.module:
            for item in node.names:
                bound = item.asname or item.name
                self.aliases[bound] = f"{node.module}.{item.name}"
                self.shadowed.discard(bound)
                self.taint[bound] = 0

    def _assign(self, targets: list[ast.AST], value: ast.AST | None) -> None:
        value_taint = self._expr_taint(value)
        self._review_expression(value)
        for target in targets:
            self._set_names(_assignment_names(target), value_taint)
            self._record_string_assignment(target, value)

    def _review_statements(self, statements: list[ast.stmt]) -> None:
        for node in statements:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._bind_import(node)
            elif isinstance(node, ast.Assign):
                self._assign(list(node.targets), node.value)
            elif isinstance(node, ast.AnnAssign):
                self._assign([node.target], node.value)
            elif isinstance(node, ast.Expr):
                self._review_expression(node.value)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    self._review_expression(item.context_expr)
                    if item.optional_vars is not None:
                        self._set_names(
                            _assignment_names(item.optional_vars),
                            self._expr_taint(item.context_expr),
                        )
                self._review_statements(node.body)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                self._review_expression(node.iter)
                iteration_taint = self._expr_taint(node.iter)
                method = node.iter.func.attr if (
                    isinstance(node.iter, ast.Call)
                    and isinstance(node.iter.func, ast.Attribute)
                ) else ""
                if method == "keys":
                    iteration_taint = 0
                if (method == "items" and isinstance(node.target, (ast.Tuple, ast.List))
                        and len(node.target.elts) == 2):
                    self._set_names(_assignment_names(node.target.elts[0]), 0)
                    self._set_names(_assignment_names(node.target.elts[1]), iteration_taint)
                else:
                    self._set_names(_assignment_names(node.target), iteration_taint)
                self._review_statements(node.body)
            elif isinstance(node, ast.If):
                if isinstance(node.test, ast.Constant):
                    self._review_statements(node.body if bool(node.test.value) else node.orelse)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self._set_names([node.name], 0)
            elif isinstance(node, (ast.Return, ast.Raise)):
                self._review_expression(node.value if hasattr(node, "value") else None)
                return

    def findings(self, line_offset: int = 0) -> list[PythonSensitiveOutputFinding]:
        self._line_offset = line_offset
        self._review_statements(self.tree.body)
        return sorted(self._findings, key=lambda item: (item.line, item.sink))


def find_python_source_sensitive_output(
    python_source: str,
    *,
    line_offset: int = 0,
) -> list[PythonSensitiveOutputFinding]:
    """Find sensitive output in one bounded Python source string."""

    if not isinstance(python_source, str) or len(python_source) > _MAX_PYTHON_SOURCE:
        return []
    try:
        tree = ast.parse(python_source)
    except (SyntaxError, ValueError):
        return []
    if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
        return []
    return _Reviewer(tree).findings(line_offset)


def find_python_sensitive_output(shell_source: str) -> list[PythonSensitiveOutputFinding]:
    """Find sensitive output from directly executed Python shell heredocs."""

    findings: list[PythonSensitiveOutputFinding] = []
    for heredoc in extract_executed_python_heredocs(shell_source):
        for finding in find_python_source_sensitive_output(
                heredoc.source, line_offset=heredoc.line - 1):
            findings.append(PythonSensitiveOutputFinding(
                line=finding.line,
                sink=finding.sink,
                decoded=finding.decoded,
                source_class=finding.source_class,
                execution_context="heredoc",
            ))
    return sorted(findings, key=lambda item: (item.line, item.sink))


def python_source_sensitive_output_risk(python_source: str) -> str:
    """Return a stable risk reason for Python source, or ``""``."""

    findings = find_python_source_sensitive_output(python_source)
    return findings[0].reason if findings else ""


def python_sensitive_output_risk(shell_source: str) -> str:
    """Return a stable risk reason for executed Python heredocs, or ``""``."""

    findings = find_python_sensitive_output(shell_source)
    return findings[0].reason if findings else ""


__all__ = [
    "PythonHeredoc",
    "PythonSensitiveOutputFinding",
    "extract_executed_python_heredocs",
    "find_python_source_sensitive_output",
    "find_python_sensitive_output",
    "python_source_sensitive_output_risk",
    "python_sensitive_output_risk",
]
