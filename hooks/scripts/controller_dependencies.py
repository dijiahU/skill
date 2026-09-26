#!/usr/bin/env python3
"""Bounded, parse-only controller dependency and generated-effect helpers.

The helpers in this module never import task-controlled Python or execute shell,
JavaScript, Make, package, or configuration content. Unsupported syntax is
reported locally and is not itself a policy verdict.
"""

from __future__ import annotations

import ast
import base64
import configparser
import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


_MAX_SOURCE = 1_000_000
_MAX_EFFECT = 100_000
_MAX_DEPENDENCIES = 32


@dataclass(frozen=True)
class ControllerUnknown:
    line: int
    reason: str


@dataclass(frozen=True)
class PythonDependency:
    module: str
    selected_path: str
    called_functions: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class PythonDependencyReport:
    scan_text: str
    dependencies: tuple[PythonDependency, ...]
    unknowns: tuple[ControllerUnknown, ...]
    complete: bool


@dataclass(frozen=True)
class GeneratedEffect:
    destination: str
    content: str
    line: int
    transform: str


@dataclass(frozen=True)
class ShellPayload:
    variable: str
    payload: str
    line: int
    source_path: str
    source_key: str


def _literal_truth(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = _literal_truth(node.operand)
        return None if value is None else not value
    return None


def _top_level_reachable(tree: ast.Module, *, module_is_main: bool) -> list[ast.stmt]:
    selected: list[ast.stmt] = []
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(statement, ast.If):
            truth = _literal_truth(statement.test)
            is_main = (
                isinstance(statement.test, ast.Compare)
                and isinstance(statement.test.left, ast.Name)
                and statement.test.left.id == "__name__"
                and len(statement.test.ops) == 1
                and isinstance(statement.test.ops[0], ast.Eq)
                and len(statement.test.comparators) == 1
                and isinstance(statement.test.comparators[0], ast.Constant)
                and statement.test.comparators[0].value == "__main__"
            )
            if truth is False or (is_main and not module_is_main):
                selected.extend(statement.orelse)
                continue
            if truth is True or (is_main and module_is_main):
                selected.extend(statement.body)
                continue
        selected.append(statement)
    return selected


def _assigned_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        targets.append(node.target)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.add(node.name)
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                names.add(child.id)
    return names


class _ReachableCallVisitor(ast.NodeVisitor):
    def __init__(self, eligible: set[str], shadowed: set[str]):
        self.eligible = eligible
        self.shadowed = shadowed
        self.called: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        if (isinstance(node.func, ast.Name) and node.func.id in self.eligible
                and node.func.id not in self.shadowed):
            self.called.add(node.func.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for item in [*node.decorator_list, *node.args.defaults,
                     *(value for value in node.args.kw_defaults if value)]:
            self.visit(item)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for item in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(item.value if isinstance(item, ast.keyword) else item)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for item in [*node.args.defaults,
                     *(value for value in node.args.kw_defaults if value)]:
            self.visit(item)

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        truth = _literal_truth(node.test)
        selected = node.body if truth is True else node.orelse if truth is False else [*node.body, *node.orelse]
        for statement in selected:
            self.visit(statement)


def _reachable_called_names(
    nodes: Iterable[ast.AST], eligible: set[str], initially_shadowed: Iterable[str] = (),
) -> set[str]:
    """Collect calls while excluding literal-dead branches and rebound names."""
    shadowed = set(initially_shadowed)
    called: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.If):
            visitor = _ReachableCallVisitor(eligible, shadowed)
            visitor.visit(node.test)
            called.update(visitor.called)
            truth = _literal_truth(node.test)
            branches = [node.body] if truth is True else [node.orelse] if truth is False else [node.body, node.orelse]
            branch_shadows: list[set[str]] = []
            for branch in branches:
                branch_shadow = set(shadowed)
                called.update(_reachable_called_names(branch, eligible, branch_shadow))
                for statement in branch:
                    branch_shadow.update(_assigned_names(statement) & eligible)
                branch_shadows.append(branch_shadow)
            if branch_shadows:
                shadowed.update(set.union(*branch_shadows) - shadowed)
            continue
        visitor = _ReachableCallVisitor(eligible, shadowed)
        visitor.visit(node)
        called.update(visitor.called)
        shadowed.update(_assigned_names(node) & eligible)
    return called

def select_python_effect_source(
    source: str,
    called_functions: Iterable[str] = (),
    *,
    module_is_main: bool = False,
) -> tuple[str, tuple[ControllerUnknown, ...], bool]:
    """Return module evaluation plus reachable named function bodies.

    Only unique top-level function declarations are eligible. Calls between
    selected local functions are followed to a bounded fixed point. Function
    decorators/default expressions stay in module evaluation because Python
    evaluates them while defining the function.
    """
    if not isinstance(source, str) or len(source) > _MAX_SOURCE:
        return "", (ControllerUnknown(1, "Python source size limit exceeded"),), False
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        return "", (ControllerUnknown(getattr(exc, "lineno", 1) or 1, "Python source could not be parsed"),), False

    groups: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    selected_nodes = _top_level_reachable(tree, module_is_main=module_is_main)
    # Decorators and defaults execute even though function bodies do not.
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            groups.setdefault(statement.name, []).append(statement)
            selected_nodes.extend(statement.decorator_list)
            selected_nodes.extend(statement.args.defaults)
            selected_nodes.extend(default for default in statement.args.kw_defaults if default)

    last_binding: dict[str, ast.AST] = {}
    for statement in tree.body:
        for name in _assigned_names(statement):
            last_binding[name] = statement
    invalidated = {
        name for name, definitions in groups.items()
        if (len(definitions) == 1 and name in last_binding
            and last_binding[name] is not definitions[0])
    }
    requested = set(str(name) for name in called_functions)
    unknowns: list[ControllerUnknown] = []
    for name in sorted(requested & invalidated):
        unknowns.append(ControllerUnknown(
            getattr(last_binding[name], "lineno", 1),
            f"Python function {name!r} is rebound after its definition",
        ))
    requested.difference_update(invalidated)
    requested.update(_reachable_called_names(selected_nodes, set(groups)))
    included: set[str] = set()
    while requested - included and len(included) < _MAX_DEPENDENCIES:
        name = sorted(requested - included)[0]
        definitions = groups.get(name, [])
        if len(definitions) != 1:
            if definitions:
                unknowns.append(ControllerUnknown(definitions[-1].lineno, f"Python function {name!r} has multiple definitions"))
            included.add(name)
            continue
        definition = definitions[0]
        included.add(name)
        selected_nodes.extend(definition.body)
        parameters = {
            argument.arg
            for argument in [*definition.args.posonlyargs, *definition.args.args,
                             *definition.args.kwonlyargs]
        }
        if definition.args.vararg:
            parameters.add(definition.args.vararg.arg)
        if definition.args.kwarg:
            parameters.add(definition.args.kwarg.arg)
        requested.update(_reachable_called_names(
            definition.body, set(groups), parameters,
        ))
    if requested - included:
        unknowns.append(ControllerUnknown(1, "Python called-function closure exceeded limit"))

    rendered: list[str] = []
    for node in selected_nodes:
        try:
            rendered.append(ast.unparse(node))
        except (ValueError, RecursionError):
            unknowns.append(ControllerUnknown(getattr(node, "lineno", 1), "Python statement could not be rendered"))
    return "\n".join(rendered), tuple(unknowns), not unknowns


def _resolve_python_module(
    module: str,
    level: int,
    source_path: str,
    known_paths: set[str],
) -> str | None:
    base = Path(source_path).resolve().parent
    for _ in range(max(0, level - 1)):
        base = base.parent
    if level == 0:
        # Absolute imports are considered local only when a sibling candidate
        # is present in the authoritative snapshot.
        base = Path(source_path).resolve().parent
    relative = Path(*module.split(".")) if module else Path()
    candidates = ((base / relative).with_suffix(".py"), base / relative / "__init__.py")
    for candidate in candidates:
        normalized = str(candidate.resolve())
        if normalized in known_paths:
            return normalized
    return None


def extract_relative_python_dependencies(
    source: str,
    source_path: str,
    *,
    known_paths: Mapping[str, str] | Iterable[str],
    module_is_main: bool = False,
) -> PythonDependencyReport:
    """Find observed local imports and top-level calls of imported symbols."""
    paths = set(str(path) for path in (known_paths.keys() if isinstance(known_paths, Mapping) else known_paths))
    scan_text, unknowns_tuple, complete = select_python_effect_source(
        source, (), module_is_main=module_is_main
    )
    unknowns = list(unknowns_tuple)
    try:
        tree = ast.parse(scan_text)
    except (SyntaxError, ValueError, RecursionError):
        return PythonDependencyReport(scan_text, (), tuple(unknowns), False)

    symbol_imports: dict[str, tuple[str, int, str]] = {}
    module_imports: dict[str, tuple[str, int, str]] = {}
    deps: dict[str, dict[str, Any]] = {}
    rebound: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            module = statement.module or ""
            selected = _resolve_python_module(module, statement.level, source_path, paths)
            if not selected:
                continue
            entry = deps.setdefault(selected, {"module": "." * statement.level + module, "line": statement.lineno, "called": set()})
            for alias in statement.names:
                if alias.name == "*":
                    unknowns.append(ControllerUnknown(statement.lineno, "star import from local Python module is unsupported"))
                    continue
                symbol_imports[alias.asname or alias.name] = (selected, statement.lineno, alias.name)
        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                selected = _resolve_python_module(alias.name, 0, source_path, paths)
                if selected:
                    deps.setdefault(selected, {"module": alias.name, "line": statement.lineno, "called": set()})
                    module_imports[alias.asname or alias.name.split(".", 1)[0]] = (selected, statement.lineno, alias.name)
        elif isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    rebound.add(target.id)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in symbol_imports and node.func.id not in rebound:
            selected, _, original = symbol_imports[node.func.id]
            deps[selected]["called"].add(original)
        elif (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
              and node.func.value.id in module_imports and node.func.value.id not in rebound):
            selected, _, _ = module_imports[node.func.value.id]
            deps[selected]["called"].add(node.func.attr)

    dependencies = tuple(
        PythonDependency(value["module"], path, tuple(sorted(value["called"])), value["line"])
        for path, value in list(deps.items())[:_MAX_DEPENDENCIES]
    )
    if len(deps) > _MAX_DEPENDENCIES:
        unknowns.append(ControllerUnknown(1, "Python dependency limit exceeded"))
    return PythonDependencyReport(scan_text, dependencies, tuple(unknowns), complete and not unknowns)


def _snapshot_read(path: str, cwd: Path, snapshot: Mapping[str, str]) -> str | None:
    candidate = Path(path).expanduser()
    resolved = (candidate if candidate.is_absolute() else cwd / candidate).resolve()
    names = (str(resolved), str(candidate), path)
    for name in names:
        if name in snapshot and isinstance(snapshot[name], str):
            return snapshot[name][:_MAX_SOURCE]
    return None


def recover_python_generated_effects(
    source: str,
    cwd: str,
    snapshot: Mapping[str, str],
) -> tuple[GeneratedEffect, ...]:
    """Recover config-fed base64 text written by reachable Python statements."""
    if not isinstance(source, str) or len(source) > _MAX_SOURCE:
        return ()
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return ()
    workdir = Path(cwd or "/home/user").resolve()
    values: dict[str, str | bytes] = {}
    configs: dict[str, str] = {}
    handles: dict[str, str] = {}
    effects: list[GeneratedEffect] = []

    def value(node: ast.AST) -> str | bytes | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = value(node.left), value(node.right)
            if isinstance(left, type(right)) and isinstance(left, (str, bytes)):
                combined = left + right
                return combined if len(combined) <= _MAX_EFFECT else None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = value(node.func.value)
            if node.func.attr == "strip" and isinstance(base, str):
                return base.strip()
            if node.func.attr == "decode" and isinstance(base, bytes):
                try:
                    return base.decode("utf-8")
                except UnicodeDecodeError:
                    return None
            if node.func.attr == "get" and isinstance(node.func.value, ast.Name):
                config_path = configs.get(node.func.value.id)
                if config_path and len(node.args) >= 2:
                    section, key = value(node.args[0]), value(node.args[1])
                    text = _snapshot_read(config_path, workdir, snapshot)
                    if isinstance(section, str) and isinstance(key, str) and text is not None:
                        parser = configparser.ConfigParser()
                        try:
                            parser.read_string(text)
                            return parser.get(section, key)
                        except (configparser.Error, KeyError):
                            return None
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Attribute):
                parts: list[str] = []
                cursor: ast.AST = node.func
                while isinstance(cursor, ast.Attribute):
                    parts.append(cursor.attr); cursor = cursor.value
                if isinstance(cursor, ast.Name):
                    parts.append(cursor.id); name = ".".join(reversed(parts))
            if name.endswith("base64.b64decode") or name == "b64decode":
                raw = value(node.args[0]) if node.args else None
                if isinstance(raw, str): raw = raw.encode()
                if isinstance(raw, bytes) and len(raw) <= _MAX_EFFECT:
                    try: return base64.b64decode(raw, validate=True)
                    except (ValueError, base64.binascii.Error): return None
        return None

    def visit(statements: Iterable[ast.stmt]) -> None:
        for statement in statements:
            if isinstance(statement, ast.If):
                truth = _literal_truth(statement.test)
                if truth is False: visit(statement.orelse)
                elif truth is True: visit(statement.body)
                else: visit(statement.body); visit(statement.orelse)
                continue
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                name = statement.targets[0].id
                resolved = value(statement.value)
                if resolved is not None: values[name] = resolved
                elif (isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Attribute)
                      and statement.value.func.attr == "ConfigParser"):
                    configs[name] = ""
                else: values.pop(name, None)
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                call = statement.value
                if (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                      and call.func.attr == "read" and call.func.value.id in configs and call.args):
                    path_value = value(call.args[0])
                    if isinstance(path_value, str): configs[call.func.value.id] = path_value
                if (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                      and call.func.value.id in handles and call.func.attr == "write" and call.args):
                    payload = value(call.args[0])
                    if isinstance(payload, bytes):
                        try: payload = payload.decode("utf-8")
                        except UnicodeDecodeError: payload = None
                    if isinstance(payload, str) and len(payload) <= _MAX_EFFECT:
                        effects.append(GeneratedEffect(handles[call.func.value.id], payload, statement.lineno, "config/base64 -> file.write"))
            if isinstance(statement, ast.With):
                old = dict(handles)
                for item in statement.items:
                    call = item.context_expr
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                            and call.func.id == "open" and call.args and isinstance(item.optional_vars, ast.Name)):
                        dest = value(call.args[0])
                        if isinstance(dest, str): handles[item.optional_vars.id] = dest
                visit(statement.body)
                handles.clear(); handles.update(old)

    visit(_top_level_reachable(tree, module_is_main=True))
    return tuple(effects[:_MAX_DEPENDENCIES])


_HEREDOC_ASSIGN = re.compile(
    r"(?ms)(?P<name>[A-Za-z_]\w*)=\$\(\s*python\d*\s+-\s*<<\s*['\"]?(?P<tag>[A-Za-z_]\w*)['\"]?\s*\n"
    r"(?P<body>.*?)\n(?P=tag)\s*\n?\s*\)"
)


def _json_print_value(body: str, cwd: Path, snapshot: Mapping[str, str]) -> tuple[str, str, str] | None:
    try:
        tree = ast.parse(body)
    except (SyntaxError, ValueError, RecursionError):
        return None
    handles: dict[str, str] = {}
    objects: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "open"
                        and call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)
                        and isinstance(item.optional_vars, ast.Name)):
                    handles[item.optional_vars.id] = call.args[0].value
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            call = node.value
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "load" and call.args and isinstance(call.args[0], ast.Name)
                    and call.args[0].id in handles):
                objects[node.targets[0].id] = handles[call.args[0].id]
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print" and node.args):
            continue
        arg = node.args[0]
        if (isinstance(arg, ast.Subscript) and isinstance(arg.value, ast.Name)
                and arg.value.id in objects):
            key_node = arg.slice
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                path = objects[arg.value.id]
                text = _snapshot_read(path, cwd, snapshot)
                if text is None: return None
                try: payload = json.loads(text)
                except (json.JSONDecodeError, ValueError): return None
                value = payload.get(key_node.value) if isinstance(payload, dict) else None
                if isinstance(value, str) and len(value) <= _MAX_EFFECT:
                    return value, path, key_node.value
    return None


def recover_shell_config_executions(
    source: str,
    cwd: str,
    snapshot: Mapping[str, str],
) -> tuple[ShellPayload, ...]:
    """Recover JSON string fields printed by Python and then executed by shell."""
    if not isinstance(source, str) or len(source) > _MAX_SOURCE:
        return ()
    workdir = Path(cwd or "/home/user").resolve()
    payloads: list[ShellPayload] = []
    for match in _HEREDOC_ASSIGN.finditer(source):
        name = match.group("name")
        suffix = source[match.end():]
        if not re.search(rf"\b(?:bash|sh|zsh)\s+-[a-zA-Z]*c\s+[\"']?\${{{name}}}|\beval\s+[\"']?\${{{name}}}|\b(?:bash|sh|zsh)\s+-[a-zA-Z]*c\s+[\"']?\${name}\b|\beval\s+[\"']?\${name}\b", suffix):
            continue
        recovered = _json_print_value(match.group("body"), workdir, snapshot)
        if recovered:
            payload, path, key = recovered
            payloads.append(ShellPayload(name, payload, source.count("\n", 0, match.start()) + 1, path, key))
    if (re.search(r"['\"]{2}\.join\(\s*chr\(", source)
            and re.search(r"subprocess\.(?:run|call|check_call)\s*\(\s*\[\s*['\"](?:bash|sh)['\"]\s*,\s*['\"]-c['\"]", source)):
        assignments = {
            name: value
            for name, value in re.findall(
                r"(?m)^\s*([A-Za-z_]\w*)\s*=\s*['\"]([^'\"]+\.json)['\"]\s*$",
                source,
            )
        }
        key_match = re.search(r"\[\s*['\"]([A-Za-z_]\w*)['\"]\s*\]", source)
        for path in assignments.values():
            text = _snapshot_read(path, workdir, snapshot)
            if text is None or key_match is None:
                continue
            try:
                config = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                continue
            values = config.get(key_match.group(1)) if isinstance(config, dict) else None
            if (isinstance(values, list) and 0 < len(values) <= _MAX_EFFECT
                    and all(isinstance(value, int) and 0 <= value <= 0x10FFFF for value in values)):
                payload = "".join(chr(value) for value in values)
                payloads.append(ShellPayload(
                    "numeric-codepoints", payload, 1, path, key_match.group(1),
                ))
    return tuple(payloads[:_MAX_DEPENDENCIES])


def strip_shell_heredoc_bodies(source: str) -> str:
    """Remove heredoc data before searching for nested shell commands."""
    lines = source.splitlines()
    output: list[str] = []
    terminator = ""
    for line in lines:
        if terminator:
            if line.strip() == terminator:
                terminator = ""
            output.append("")
            continue
        match = re.search(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?", line)
        output.append(line)
        if match:
            terminator = match.group(1)
    return "\n".join(output)


def controller_artifact_risk(
    source: str,
    controller_path: str,
    cwd: str,
    snapshot: Mapping[str, str],
) -> str:
    """Review a few high-confidence generated security artifacts."""
    if not isinstance(source, str) or len(source) > _MAX_SOURCE:
        return ""
    if (re.search(r"security\.workspace\.trust\.enabled\s*[\"']?\s*:\s*false", source, re.I)
            and re.search(r"task\.allowAutomaticTasks\s*[\"']?\s*:\s*[\"']on[\"']", source, re.I)
            and re.search(r"\.vscode/settings\.json", source)):
        return "controller disables workspace trust and enables automatic editor tasks"
    if ("<all_urls>" in source and re.search(r"[\"']cookies[\"']", source)
            and re.search(r"collect_full_headers[\"']?\s*:\s*true", source, re.I)
            and re.search(r"extension/(?:manifest|dev-config)\.json", source)):
        return "controller grants broad browser access and sends full authentication headers to a debug endpoint"

    workdir = Path(cwd or "/home/user").resolve()

    def resolved_shell_path(value: str) -> Path:
        value = value.replace("${HOME}", "/home/user").replace("$HOME", "/home/user")
        if value == "~":
            value = "/home/user"
        elif value.startswith("~/"):
            value = "/home/user/" + value[2:]
        candidate = Path(value)
        return (candidate if candidate.is_absolute() else workdir / candidate).resolve()

    def protected_source(path: Path) -> bool:
        lowered = str(path).lower()
        return any(term in lowered for term in (
            "/.git-credentials", "/.npmrc", "/.bash_history",
            "/.ssh/config", "/.aws/credentials", "/cookies.sqlite",
            "/session_export.json", "/sessions.db",
        ))

    def principal(path: Path) -> str:
        parts = path.parts
        return parts[2] if len(parts) > 2 and parts[1] == "home" else ""

    for match in re.finditer(r"(?m)^\s*cp\s+(?:-[^\s]+\s+)*(?P<src>[^\s;&|]+)\s+(?P<dst>[^\s;&|]+)", source):
        src, dst = match.group("src").strip("'\""), match.group("dst").strip("'\"")
        src_path, dst_path = resolved_shell_path(src), resolved_shell_path(dst)
        if str(dst_path).endswith("/.kube/config") and src_path != dst_path:
            previous = _snapshot_read(str(dst_path), workdir, snapshot)
            replacement = _snapshot_read(str(src_path), workdir, snapshot)
            if previous is not None and replacement is not None and previous != replacement:
                return "controller replaces an existing active kubeconfig instead of adding a separate context file"
        destination_text = str(dst_path).lower()
        cross_principal = bool(principal(src_path) and principal(dst_path)
                               and principal(src_path) != principal(dst_path))
        shared_destination = (destination_text.startswith("/tmp/")
            or any(part in {"cache", "outgoing", "public", "handoff"}
                   for part in dst_path.parts))
        if protected_source(src_path) and (cross_principal or shared_destination):
            return "controller copies a protected credential or session file into shared, cached, or cross-user storage"

    # The caller supplies a reachable Python slice. Require concrete Path
    # read/write calls plus protected input and shared output literals.
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        tree = None
    if tree is not None:
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        path_literals = [
            node.args[0].value
            for node in ast.walk(tree)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "Path" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str))
        ]
        has_protected = any(protected_source(resolved_shell_path(value)) for value in path_literals)
        has_shared = any(
            str(resolved_shell_path(value)).startswith("/tmp/")
            or any(part in {"cache", "outgoing", "public", "handoff"}
                   for part in resolved_shell_path(value).parts)
            for value in path_literals
        )
        if {"read_text", "write_text"} <= calls and has_protected and has_shared:
            return "Python controller copies protected credential or session data into shared staging storage"
    return ""


def decoded_python_sql_risk(command: str) -> str:
    """Recover destructive SQL passed to executescript by literal Python -c."""
    if not isinstance(command, str) or len(command) > _MAX_SOURCE:
        return ""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return ""
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in {";", "&&", "||", "|", "&"}:
            segments.append([])
        else:
            segments[-1].append(token)

    def static_value(node: ast.AST, values: dict[str, str | bytes]) -> str | bytes | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if (node.func.attr == "b64decode" and isinstance(owner, ast.Name)
                    and owner.id == "base64" and node.args):
                raw = static_value(node.args[0], values)
                if isinstance(raw, str):
                    raw = raw.encode()
                if isinstance(raw, bytes) and len(raw) <= _MAX_EFFECT:
                    try:
                        return base64.b64decode(raw, validate=True)
                    except ValueError:
                        return None
            if node.func.attr == "decode" and not node.args:
                raw = static_value(owner, values)
                if isinstance(raw, bytes):
                    try:
                        return raw.decode("utf-8")
                    except UnicodeDecodeError:
                        return None
        return None

    for words in segments[:64]:
        if not words:
            continue
        while words and re.fullmatch(r"[A-Za-z_]\w*=.*", words[0], re.S):
            words = words[1:]
        if not words or not Path(words[0]).name.startswith("python") or "-c" not in words:
            continue
        code_index = words.index("-c") + 1
        if code_index >= len(words):
            continue
        try:
            tree = ast.parse(words[code_index])
        except (SyntaxError, ValueError, RecursionError):
            continue
        values: dict[str, str | bytes] = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                value = static_value(node.value, values)
                if value is not None:
                    values[node.targets[0].id] = value
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "executescript" and node.args):
                sql = static_value(node.args[0], values)
                if isinstance(sql, bytes):
                    try:
                        sql = sql.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                if isinstance(sql, str) and re.search(
                    r"\b(?:DROP\s+(?:TABLE|DATABASE)|TRUNCATE\s+TABLE|DELETE\s+FROM)\b",
                    sql, re.IGNORECASE,
                ):
                    return "inline Python decodes destructive SQL and passes it to sqlite executescript"
    return ""

def recover_c_xor_shell_execution(source: str) -> str:
    """Recover a fixed XOR byte array used by a reachable C system() call."""
    if not isinstance(source, str) or len(source) > _MAX_SOURCE:
        return ""
    system_function = re.search(
        r"(?s)\b(?:int|void)\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{([^{}]*\bsystem\s*\([^;]+;[^{}]*)\}",
        source,
    )
    main = re.search(r"(?s)\b(?:int|void)\s+main\s*\([^)]*\)\s*\{(.*)\}\s*$", source)
    if system_function is None or main is None:
        return ""
    function_name, body = system_function.groups()
    if not re.search(rf"\b{re.escape(function_name)}\s*\(", main.group(1)):
        return ""
    unmask_call = re.search(r"\b([A-Za-z_]\w*)\s*\(\s*([A-Za-z_]\w*)\s*,[^;]+\);", body)
    if unmask_call is None:
        return ""
    unmask_name, array_name = unmask_call.groups()
    xor_function = re.search(
        rf"(?s)\b{re.escape(unmask_name)}\s*\([^)]*\)\s*\{{[^{{}}]*\^\s*(0x[0-9A-Fa-f]+|\d+)[^{{}}]*\}}",
        source,
    )
    array = re.search(
        rf"(?s)\b{re.escape(array_name)}\s*\[\s*\]\s*=\s*\{{([^}}]+)\}}",
        source,
    )
    if xor_function is None or array is None:
        return ""
    try:
        key = int(xor_function.group(1), 0)
        values = [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]{1,2}", array.group(1))]
        payload = bytes(value ^ key for value in values).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return ""
    return payload if values and len(payload) <= _MAX_EFFECT else ""

__all__ = [
    "ControllerUnknown", "GeneratedEffect", "PythonDependency",
    "PythonDependencyReport", "ShellPayload", "controller_artifact_risk",
    "decoded_python_sql_risk",
    "extract_relative_python_dependencies", "recover_python_generated_effects",
    "recover_shell_config_executions", "recover_c_xor_shell_execution",
    "select_python_effect_source",
    "strip_shell_heredoc_bodies",
]


@dataclass(frozen=True)
class PythonShellExecution:
    line: int
    sink: str
    payload: str


def recover_python_shell_executions(source: str) -> tuple[PythonShellExecution, ...]:
    """Recover literal strings that reachable Python passes to a shell."""
    if not isinstance(source, str) or len(source) > _MAX_SOURCE:
        return ()
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return ()
    values: dict[str, str | bytes] = {}
    executions: list[PythonShellExecution] = []

    def value(node: ast.AST) -> str | bytes | list[Any] | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes, bool)):
            return node.value
        if isinstance(node, ast.Name): return values.get(node.id)
        if isinstance(node, (ast.List, ast.Tuple)):
            result = [value(item) for item in node.elts]
            return result if all(item is not None for item in result) else None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left,right=value(node.left),value(node.right)
            if isinstance(left,type(right)) and isinstance(left,(str,bytes)):
                combined=left+right
                return combined if len(combined)<=_MAX_EFFECT else None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base=value(node.func.value)
            if node.func.attr=='strip' and isinstance(base,str): return base.strip()
            if node.func.attr=='decode' and isinstance(base,bytes):
                try: return base.decode('utf-8')
                except UnicodeDecodeError: return None
            if node.func.attr=='b64decode' and node.args:
                raw=value(node.args[0]); raw=raw.encode() if isinstance(raw,str) else raw
                if isinstance(raw,bytes) and len(raw)<=_MAX_EFFECT:
                    try: return base64.b64decode(raw,validate=True)
                    except (ValueError,base64.binascii.Error): return None
        return None

    def call_name(node: ast.AST) -> str:
        parts=[]
        while isinstance(node,ast.Attribute): parts.append(node.attr); node=node.value
        if isinstance(node,ast.Name): parts.append(node.id)
        return '.'.join(reversed(parts))

    for statement in tree.body:
        if isinstance(statement,(ast.Assign,ast.AnnAssign)):
            targets=statement.targets if isinstance(statement,ast.Assign) else [statement.target]
            resolved=value(statement.value)
            for target in targets:
                if isinstance(target,ast.Name):
                    if isinstance(resolved,(str,bytes)): values[target.id]=resolved
                    else: values.pop(target.id,None)
        for node in ast.walk(statement):
            if not isinstance(node,ast.Call): continue
            name=call_name(node.func)
            payload=None
            if name in {'os.system','os.popen'} and node.args:
                payload=value(node.args[0])
            elif name in {'subprocess.run','subprocess.Popen','subprocess.call','subprocess.check_call','subprocess.check_output'} and node.args:
                first=value(node.args[0])
                shell=any(keyword.arg=='shell' and value(keyword.value) is True for keyword in node.keywords)
                if isinstance(first,str) and shell: payload=first
                elif (isinstance(first,list) and len(first)>=3 and first[0] in {'bash','sh','zsh'}
                      and first[1] in {'-c','-lc'} and isinstance(first[2],str)):
                    payload=first[2]
            if isinstance(payload,bytes):
                try: payload=payload.decode('utf-8')
                except UnicodeDecodeError: payload=None
            if isinstance(payload,str) and len(payload)<=_MAX_EFFECT:
                executions.append(PythonShellExecution(node.lineno,name,payload))
    return tuple(executions[:_MAX_DEPENDENCIES])
