"""Bounded, parse-only proof of reachable remote JavaScript execution chains."""

from __future__ import annotations

import re


def _reachable_view(source: str):
    # Import at call time: javascript_dependencies invokes us only after its
    # lexer and function-body helpers have been defined.
    from javascript_dependencies import (
        _DECLARATION_KEYWORDS, _curly_depths, _javascript_function_bodies,
        _lex, _literal_false_branch_tokens, _matching_delimiters,
        _render_javascript_tokens,
    )

    tokens, _ = _lex(source)
    pairs, _ = _matching_delimiters(tokens)
    depths = _curly_depths(tokens)
    bodies, _ = _javascript_function_bodies(tokens, pairs, depths)
    grouped = {}
    for body in bodies:
        if body.name and depths[body.declaration] == 0:
            grouped.setdefault(body.name, []).append(body)
    functions = {name: values[0] for name, values in grouped.items() if len(values) == 1}
    assignments = {"=", "+=", "-=", "*=", "/=", "??="}
    for name in list(functions):
        if any(
            token.value == name and index + 1 < len(tokens)
            and tokens[index + 1].value in assignments and depths[index] == 0
            for index, token in enumerate(tokens)
        ):
            functions.pop(name, None)

    unreachable = _literal_false_branch_tokens(tokens, pairs)
    included = set(range(len(tokens))) - unreachable
    for body in bodies:
        included.difference_update(range(body.body_open + 1, body.body_close))

    entered = set()
    for _ in range(64):
        changed = False
        for body in bodies:
            callback = body.form == "arrow-function" or not body.name
            named_call = body.name in functions and any(
                index in included and token.value == body.name
                and index + 1 < len(tokens) and tokens[index + 1].value == "("
                and not (index and tokens[index - 1].value == "function")
                for index, token in enumerate(tokens)
            )
            if not ((callback and body.declaration in included) or named_call):
                continue
            key = (body.body_open, body.body_close)
            if key in entered:
                continue
            entered.add(key)
            for index in range(body.body_open + 1, body.body_close):
                if index not in unreachable and index not in included:
                    included.add(index)
                    changed = True
            for nested in bodies:
                if body.body_open < nested.body_open < nested.body_close < body.body_close:
                    included.difference_update(range(nested.body_open + 1, nested.body_close))
        if not changed:
            break
    text = _render_javascript_tokens(source, tokens, included)
    return tokens, pairs, included, functions, text, _DECLARATION_KEYWORDS, _render_javascript_tokens


def _required_bindings(tokens, pairs, included, declaration_keywords, modules):
    namespaces, bindings = set(), set()
    for index in range(len(tokens) - 5):
        if index not in included or tokens[index].value not in declaration_keywords:
            continue
        if (tokens[index + 1].kind == "identifier" and tokens[index + 2].value == "="
                and tokens[index + 3].value == "require" and tokens[index + 4].value == "("
                and tokens[index + 5].kind == "string" and tokens[index + 5].value in modules):
            namespaces.add(tokens[index + 1].value)
        if tokens[index + 1].value == "{" and index + 1 in pairs:
            closed = pairs[index + 1]
            if (closed + 4 < len(tokens) and tokens[closed + 1].value == "="
                    and tokens[closed + 2].value == "require"
                    and tokens[closed + 3].value == "("
                    and tokens[closed + 4].kind == "string"
                    and tokens[closed + 4].value in modules):
                bindings.update(
                    token.value for token in tokens[index + 2:closed]
                    if token.kind == "identifier"
                )
    return namespaces, bindings


def _brace_depth_at(text: str, position: int) -> int:
    depth = 0
    quote = ""
    escaped = False
    index = 0
    while index < min(position, len(text)):
        character = text[index]
        if escaped:
            escaped = False
        elif quote:
            if character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
        elif character in {"'", '"', chr(96)}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth = max(0, depth - 1)
        index += 1
    return depth


def _top_level_match(pattern: str, text: str, start: int = 0):
    for match in re.finditer(pattern, text[start:]):
        absolute = start + match.start()
        if _brace_depth_at(text, absolute) == 0:
            return match, absolute
    return None, -1


def _pinned_sha256_guard(
    window: str, payload: str, full_source: str, scope: str,
    scope_parameters: tuple[str, ...],
) -> bool:
    """Prove an in-order, unconditional pinned digest guard for one payload."""
    def shadowed(name: str) -> bool:
        if name in scope_parameters:
            return True
        return bool(re.search(
            r"\b(?:const|let|var|function|class)\s+" + re.escape(name) + r"\b",
            scope,
        ))

    namespace_declarations = {}
    for match in re.finditer(
        r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*require\s*\(\s*"
        r"['\"](?:node:)?crypto['\"]\s*\)",
        full_source,
    ):
        if _brace_depth_at(full_source, match.start()) == 0:
            namespace_declarations.setdefault(match.group(1), []).append(match)

    crypto_namespaces = set()
    for name, declarations in namespace_declarations.items():
        if len(declarations) != 1 or shadowed(name):
            continue
        declaration = declarations[0]
        single_purpose = True
        for occurrence in re.finditer(r"\b" + re.escape(name) + r"\b", full_source):
            if declaration.start() <= occurrence.start() < declaration.end():
                continue
            if re.match(
                re.escape(name) + r"\s*\.\s*createHash\s*\(",
                full_source[occurrence.start():],
            ):
                continue
            single_purpose = False
            break
        if single_purpose:
            crypto_namespaces.add(name)
    direct_create_hash = not shadowed("createHash") and any(
        re.search(r"(?:^|,)\s*createHash\s*(?:,|$)", match.group(1))
        for match in re.finditer(
            r"\bconst\s*\{([^{}]+)\}\s*=\s*require\s*\(\s*"
            r"['\"](?:node:)?crypto['\"]\s*\)",
            full_source,
        )
        if _brace_depth_at(full_source, match.start()) == 0
    )
    create_hash_forms = [
        re.escape(name) + r"\s*\.\s*createHash"
        for name in sorted(crypto_namespaces)
    ]
    if direct_create_hash:
        create_hash_forms.append(r"createHash")
    if not create_hash_forms:
        return False

    expected_names = {
        match.group(1)
        for match in re.finditer(
            r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*['\"][0-9a-fA-F]{64}['\"]",
            full_source,
        )
        if _brace_depth_at(full_source, match.start()) == 0
    }
    hash_pattern = (
        r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*(?:"
        + "|".join(create_hash_forms)
        + r")\s*\(\s*['\"]sha256['\"]\s*\)"
        r"\s*\.\s*update\s*\(\s*" + re.escape(payload) + r"\s*\)"
        r"\s*\.\s*digest\s*\(\s*['\"]hex['\"]\s*\)"
    )
    for hashed in re.finditer(hash_pattern, window):
        if _brace_depth_at(window, hashed.start()) != 0:
            continue
        terminator, _ = _top_level_match(r"\b(?:return|throw)\b", window[:hashed.start()])
        if terminator:
            continue
        guard_pattern = (
            r"\bif\s*\(\s*" + re.escape(hashed.group(1))
            + r"\s*!==?\s*(?P<expected>['\"][0-9a-fA-F]{64}['\"]|[A-Za-z_$][\w$]*)\s*\)"
            r"\s*\{?\s*throw\b"
        )
        for guard in re.finditer(guard_pattern, window[hashed.end():]):
            guard_start = hashed.end() + guard.start()
            guard_end = hashed.end() + guard.end()
            if _brace_depth_at(window, guard_start) != 0:
                continue
            expected = guard.group("expected")
            if not (expected.startswith(("'", '"')) or expected in expected_names):
                continue
            mutation = re.search(
                r"\b" + re.escape(payload) + r"\s*(?:=|\+=|-=|\*=|/=|\?\?=)",
                window[guard_end:],
            )
            if mutation:
                continue
            return True
    return False

def javascript_remote_payload_execution_risk(source: str) -> str:
    """Return a reason only for a statically linked, reachable download/exec chain."""
    if not isinstance(source, str) or len(source) > 1_000_000:
        return ""
    tokens, pairs, included, functions, reachable, declarations, render = _reachable_view(source)
    network, _ = _required_bindings(
        tokens, pairs, included, declarations,
        {"http", "https", "node:http", "node:https"},
    )
    child_namespaces, child_calls = _required_bindings(
        tokens, pairs, included, declarations,
        {"child_process", "node:child_process"},
    )
    if not network or not (child_namespaces or child_calls):
        return ""
    derived_network = set(network)
    for match in re.finditer(r"\b(?:const|let|var)\s+(\w+)\s*=\s*([^;]+)", reachable):
        if any(re.search(r"\b" + re.escape(name) + r"\b", match.group(2)) for name in network):
            derived_network.add(match.group(1))
    if not any(re.search(
        r"\b" + re.escape(name) + r"\s*\.\s*(?:get|request)\s*\(", reachable,
    ) for name in derived_network):
        return ""
    exec_calls = set(child_calls)
    for namespace in child_namespaces:
        exec_calls.update(match.group(1) for match in re.finditer(
            r"\b" + re.escape(namespace)
            + r"\s*\.\s*(exec|execSync|spawn|spawnSync)\s*\(", reachable,
        ))
    if not exec_calls:
        return ""

    # Direct response stream -> file -> completion callback -> shell(file).
    for stream in re.finditer(
        r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:\w+\.)?createWriteStream\s*\(\s*"
        r"(?P<q>['\"])(?P<path>[^'\"\n]+)(?P=q)\s*\)", reachable,
    ):
        variable, path = stream.group(1), stream.group("path")
        if not re.search(r"\.\s*pipe\s*\(\s*" + re.escape(variable) + r"\s*\)", reachable):
            continue
        if not re.search(r"\b" + re.escape(variable) + r"\s*\.\s*on\s*\(\s*['\"]finish['\"]", reachable):
            continue
        for sink in exec_calls:
            execution = re.search(
                r"\b" + re.escape(sink) + r"\s*\(\s*(['\"])(?P<cmd>[^'\"\n]+)\1",
                reachable,
            )
            if execution and re.search(r"(?:^|[\s/])" + re.escape(path) + r"(?:\s|$)", execution.group("cmd")):
                return "JavaScript streams a remote response into a file and executes that file in its completion callback without a pinned integrity check"

    texts, parameters = {}, {}
    for name, body in functions.items():
        if not any(index in included for index in range(body.body_open + 1, body.body_close)):
            continue
        texts[name] = render(
            source, tokens,
            (index for index in range(body.body_open + 1, body.body_close) if index in included),
        )
        opened = next((i for i in range(body.declaration, body.body_open) if tokens[i].value == "("), -1)
        closed = pairs.get(opened, -1)
        parameters[name] = tuple(
            token.value for token in tokens[opened + 1:closed] if token.kind == "identifier"
        ) if opened >= 0 and closed >= 0 else ()

    downloads = set()
    for name, text in texts.items():
        network_call = any(re.search(
            r"\b" + re.escape(item) + r"\s*\.\s*(?:get|request)\s*\(", text,
        ) for item in derived_network)
        resolved = re.search(r"\bresolve\s*\(\s*(\w+)\s*\)", text)
        if (network_call and resolved and re.search(r"\.\s*on\s*\(\s*['\"]data['\"]", text)
                and re.search(r"\b" + re.escape(resolved.group(1)) + r"\s*\+=", text)):
            downloads.add(name)

    executors = set()
    for name, text in texts.items():
        for parameter in parameters.get(name, ()):
            write = re.search(
                r"\bwriteFileSync\s*\(\s*(\w+)\s*,\s*" + re.escape(parameter) + r"\b", text,
            )
            if not write:
                continue
            target = write.group(1)
            spawn = any(re.search(
                r"\b" + re.escape(sink) + r"\s*\(\s*['\"](?:ba|z|k)?sh['\"]\s*,\s*"
                r"\[\s*" + re.escape(target) + r"\s*\]", text,
            ) for sink in exec_calls)
            execute = any(re.search(
                r"\b" + re.escape(sink) + r"\s*\(\s*`[^`]*\$\{"
                + re.escape(target) + r"\}[^`]*`", text,
            ) for sink in exec_calls)
            if spawn or execute:
                executors.add(name)

    # Keep assignment, guard, and first execution in the same called function.
    # The global rendered view is deliberately not used for ordering because
    # function declaration order is not runtime call order.
    for scope_name, scope in texts.items():
        for download in downloads:
            assignment_pattern = (
                r"\b(?:const|let|var)\s+(\w+)\s*=\s*await\s+"
                + re.escape(download) + r"\s*\("
            )
            for assignment in re.finditer(assignment_pattern, scope):
                if _brace_depth_at(scope, assignment.start()) != 0:
                    continue
                payload = assignment.group(1)
                remainder = scope[assignment.end():]
                execution_candidates = []
                for executor in executors:
                    execution = re.search(
                        r"\b(?:await\s+)?" + re.escape(executor)
                        + r"\s*\(\s*" + re.escape(payload) + r"\s*\)",
                        remainder,
                    )
                    if execution is not None:
                        absolute = assignment.end() + execution.start()
                        if _brace_depth_at(scope, absolute) == 0:
                            execution_candidates.append(execution)
                if not execution_candidates:
                    continue
                first_execution = min(execution_candidates, key=lambda item: item.start())
                guard_window = remainder[:first_execution.start()]
                if not _pinned_sha256_guard(
                    guard_window, payload, reachable, scope,
                    parameters.get(scope_name, ()),
                ):
                    return "JavaScript passes remote response data to a reachable file-and-shell executor without a pinned integrity check"
    return ""

