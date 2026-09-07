#!/usr/bin/env python3
"""Bounded, parse-only discovery of relative CommonJS dependencies.

This module intentionally does not import or execute JavaScript.  It recognizes
only direct, unshadowed ``require(<string literal>)`` calls whose specifier is
relative.  The small lexer is conservative: constructs it cannot safely
interpret are reported as unknown rather than promoted to confirmed edges.

``export_call_evidence`` is syntactic evidence only.  It says that a local
binding created by a require expression is later used in a direct call
expression; it does not prove control-flow reachability or that the call has a
particular effect.  Callers must still inspect the selected dependency with
their existing semantic/effect checks.
"""

from dataclasses import dataclass, field
import posixpath
from typing import Iterable


_IDENTIFIER_START = "_$"
_IDENTIFIER_CONTINUE = "_$"
_DECLARATION_KEYWORDS = {"const", "let", "var"}
_REGEX_PREFIX_KEYWORDS = {
    "await", "case", "delete", "do", "else", "in", "instanceof", "new",
    "of", "return", "throw", "typeof", "void", "yield",
}
_MAX_SOURCE_CHARS = 1_000_000
_MAX_TOKENS = 100_000
_MAX_DEPENDENCIES = 64
_MAX_UNKNOWNS = 64


@dataclass(frozen=True)
class JavascriptCallEvidence:
    """A direct call expression involving a binding from one require call."""

    export_name: str
    local_name: str
    line: int
    form: str
    confidence: str = "module-top-level-direct"
    reachability: str = "module-top-level-direct"


@dataclass(frozen=True)
class JavascriptDependency:
    """One confirmed static relative CommonJS dependency edge."""

    specifier: str
    candidate_paths: tuple[str, ...]
    selected_path: str | None
    line: int
    module_evaluation: bool = True
    confidence: str = "static-unshadowed"
    export_call_evidence: tuple[JavascriptCallEvidence, ...] = ()


@dataclass(frozen=True)
class JavascriptDependencyUnknown:
    """A construct deliberately excluded from confirmed dependency edges."""

    line: int
    reason: str


@dataclass(frozen=True)
class JavascriptDependencyReport:
    dependencies: tuple[JavascriptDependency, ...]
    unknowns: tuple[JavascriptDependencyUnknown, ...]
    complete: bool


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    line: int
    start: int
    end: int


@dataclass
class _Scope:
    start: int
    end: int
    parent: int | None
    kind: str = "block"
    bindings: set[str] = field(default_factory=set)


def _is_identifier_start(character: str) -> bool:
    return character.isalpha() or character in _IDENTIFIER_START


def _is_identifier_continue(character: str) -> bool:
    return character.isalnum() or character in _IDENTIFIER_CONTINUE


def _decode_escape(source: str, index: int) -> tuple[str, int, bool]:
    if index >= len(source):
        return "", index, False
    character = source[index]
    simple = {
        "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
        "v": "\v", "0": "\0",
    }
    if character in simple:
        return simple[character], index + 1, True
    if character == "x" and index + 2 < len(source):
        digits = source[index + 1:index + 3]
        if all(item in "0123456789abcdefABCDEF" for item in digits):
            return chr(int(digits, 16)), index + 3, True
        return "", index + 1, False
    if character == "u":
        if index + 1 < len(source) and source[index + 1] == "{":
            close = source.find("}", index + 2, min(len(source), index + 10))
            digits = source[index + 2:close] if close >= 0 else ""
            if digits and all(item in "0123456789abcdefABCDEF" for item in digits):
                try:
                    return chr(int(digits, 16)), close + 1, True
                except ValueError:
                    pass
            return "", index + 1, False
        digits = source[index + 1:index + 5]
        if len(digits) == 4 and all(item in "0123456789abcdefABCDEF" for item in digits):
            return chr(int(digits, 16)), index + 5, True
        return "", index + 1, False
    if character in "\r\n":
        if character == "\r" and index + 1 < len(source) and source[index + 1] == "\n":
            return "", index + 2, True
        return "", index + 1, True
    return character, index + 1, True


def _regex_can_start(previous: _Token | None) -> bool:
    if previous is None:
        return True
    if previous.kind in {"string", "number", "regex", "template"}:
        return False
    if previous.kind == "identifier":
        return previous.value in _REGEX_PREFIX_KEYWORDS
    return previous.value not in {")", "]", "}", "++", "--"}


def _lex(source: str) -> tuple[list[_Token], list[JavascriptDependencyUnknown]]:
    tokens: list[_Token] = []
    unknowns: list[JavascriptDependencyUnknown] = []
    index = 0
    line = 1
    length = len(source)
    if source.startswith("#!"):
        newline = source.find("\n")
        index = length if newline < 0 else newline + 1
        line = 1 if newline < 0 else 2

    while index < length and len(tokens) < _MAX_TOKENS:
        character = source[index]
        if character.isspace():
            if character == "\n":
                line += 1
            index += 1
            continue
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            if newline < 0:
                break
            index = newline
            continue
        if source.startswith("/*", index):
            close = source.find("*/", index + 2)
            if close < 0:
                unknowns.append(JavascriptDependencyUnknown(line, "unterminated block comment"))
                break
            line += source.count("\n", index, close + 2)
            index = close + 2
            continue
        if character in {"'", '"'}:
            start = index
            start_line = line
            quote = character
            index += 1
            value: list[str] = []
            valid = True
            terminated = False
            while index < length:
                character = source[index]
                if character == quote:
                    index += 1
                    terminated = True
                    break
                if character == "\\":
                    decoded, next_index, escape_valid = _decode_escape(source, index + 1)
                    line += source.count("\n", index, next_index)
                    value.append(decoded)
                    valid = valid and escape_valid
                    index = next_index
                    continue
                if character in "\r\n":
                    valid = False
                    break
                value.append(character)
                index += 1
            kind = "string" if valid and terminated else "invalid-string"
            tokens.append(_Token(kind, "".join(value), start_line, start, index))
            if kind != "string":
                unknowns.append(JavascriptDependencyUnknown(start_line, "invalid or unterminated string literal"))
            continue
        if character == "`":
            start = index
            start_line = line
            index += 1
            escaped = False
            interpolation = False
            terminated = False
            while index < length:
                character = source[index]
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == "`":
                    index += 1
                    terminated = True
                    break
                elif source.startswith("${", index):
                    interpolation = True
                if character == "\n":
                    line += 1
                index += 1
            tokens.append(_Token("template", source[start:index], start_line, start, index))
            if interpolation:
                unknowns.append(JavascriptDependencyUnknown(
                    start_line, "template literal interpolation was not analyzed"
                ))
            if not terminated:
                unknowns.append(JavascriptDependencyUnknown(start_line, "unterminated template literal"))
            continue
        if _is_identifier_start(character):
            start = index
            index += 1
            while index < length and _is_identifier_continue(source[index]):
                index += 1
            tokens.append(_Token("identifier", source[start:index], line, start, index))
            continue
        if character.isdigit():
            start = index
            index += 1
            while index < length and (source[index].isalnum() or source[index] in "._"):
                index += 1
            tokens.append(_Token("number", source[start:index], line, start, index))
            continue
        if character == "/" and _regex_can_start(tokens[-1] if tokens else None):
            start = index
            start_line = line
            index += 1
            escaped = False
            in_class = False
            terminated = False
            while index < length:
                character = source[index]
                if character in "\r\n":
                    break
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == "[":
                    in_class = True
                elif character == "]":
                    in_class = False
                elif character == "/" and not in_class:
                    index += 1
                    while index < length and source[index].isalpha():
                        index += 1
                    terminated = True
                    break
                index += 1
            if terminated:
                tokens.append(_Token("regex", source[start:index], start_line, start, index))
                continue
            # A slash in an ambiguous position is safer as punctuation.  The
            # remaining text is tokenized and the incomplete parse is exposed.
            index = start + 1
            unknowns.append(JavascriptDependencyUnknown(start_line, "ambiguous or unterminated regular expression"))
            tokens.append(_Token("punctuation", "/", start_line, start, index))
            continue

        start = index
        operator = next(
            (value for value in ("===", "!==", "??=", "=>", "?.", "==", "!=", "<=", ">=", "++", "--", "&&", "||", "??", "+=", "-=", "*=", "/=")
             if source.startswith(value, index)),
            character,
        )
        index += len(operator)
        tokens.append(_Token("punctuation", operator, line, start, index))

    if len(tokens) >= _MAX_TOKENS and index < length:
        unknowns.append(JavascriptDependencyUnknown(line, "JavaScript token limit exceeded"))
    return tokens, unknowns[:_MAX_UNKNOWNS]


def _matching_delimiters(tokens: list[_Token]) -> tuple[dict[int, int], bool]:
    pairs: dict[int, int] = {}
    stack: list[tuple[str, int]] = []
    closes = {")": "(", "]": "[", "}": "{"}
    complete = True
    for index, token in enumerate(tokens):
        if token.value in {"(", "[", "{"}:
            stack.append((token.value, index))
        elif token.value in closes:
            if not stack or stack[-1][0] != closes[token.value]:
                complete = False
                continue
            _, opened = stack.pop()
            pairs[opened] = index
            pairs[index] = opened
    return pairs, complete and not stack


def _build_scopes(tokens: list[_Token], pairs: dict[int, int]) -> tuple[list[_Scope], list[int]]:
    scopes = [_Scope(0, max(0, len(tokens) - 1), None, "program")]
    scope_by_open: dict[int, int] = {}
    stack = [0]
    token_scopes = [0] * len(tokens)
    for index, token in enumerate(tokens):
        token_scopes[index] = stack[-1]
        if token.value == "{" and index in pairs:
            scope = _Scope(index, pairs[index], stack[-1])
            scopes.append(scope)
            scope_by_open[index] = len(scopes) - 1
            stack.append(len(scopes) - 1)
        elif token.value == "}" and len(stack) > 1 and scopes[stack[-1]].end == index:
            token_scopes[index] = stack[-1]
            stack.pop()

    def add_binding(scope_index: int, name: str = "require") -> None:
        scopes[scope_index].bindings.add(name)

    # Function and catch parameters establish bindings in their body scope.
    for index, token in enumerate(tokens):
        if token.value == "function":
            cursor = index + 1
            if cursor < len(tokens) and tokens[cursor].value == "*":
                cursor += 1
            function_name = tokens[cursor].value if cursor < len(tokens) and tokens[cursor].kind == "identifier" else ""
            if function_name:
                if function_name == "require":
                    add_binding(token_scopes[index])
                cursor += 1
            while cursor < len(tokens) and tokens[cursor].value != "(":
                cursor += 1
            if cursor >= len(tokens) or cursor not in pairs:
                continue
            close = pairs[cursor]
            body = close + 1
            if body < len(tokens) and tokens[body].value == "{" and body in scope_by_open:
                body_scope = scope_by_open[body]
                scopes[body_scope].kind = "function"
                if any(item.kind == "identifier" and item.value == "require" for item in tokens[cursor + 1:close]):
                    add_binding(body_scope)
                if function_name == "require":
                    add_binding(body_scope)
        elif token.value == "catch" and index + 1 < len(tokens) and tokens[index + 1].value == "(":
            opened = index + 1
            close = pairs.get(opened)
            body = close + 1 if close is not None else -1
            if close is not None and body < len(tokens) and tokens[body].value == "{" and body in scope_by_open:
                if any(item.kind == "identifier" and item.value == "require" for item in tokens[opened + 1:close]):
                    add_binding(scope_by_open[body])

    # Arrow parameters have the same shadowing behavior.  Braced bodies get a
    # normal scope; expression bodies use an explicit interval below.
    expression_shadow_ranges: list[tuple[int, int]] = []
    for index, token in enumerate(tokens):
        if token.value != "=>" or index == 0:
            continue
        previous = index - 1
        parameter_has_require = False
        if tokens[previous].kind == "identifier":
            parameter_has_require = tokens[previous].value == "require"
        elif tokens[previous].value == ")" and previous in pairs:
            opened = pairs[previous]
            parameter_has_require = any(
                item.kind == "identifier" and item.value == "require"
                for item in tokens[opened + 1:previous]
            )
        if not parameter_has_require or index + 1 >= len(tokens):
            continue
        body = index + 1
        if tokens[body].value == "{" and body in scope_by_open:
            add_binding(scope_by_open[body])
        else:
            end = body
            while end + 1 < len(tokens) and tokens[end + 1].value not in {";"}:
                end += 1
            expression_shadow_ranges.append((body, end))

    # Lexical declarations bind the whole containing scope.  ``var`` binds the
    # nearest function/program scope.  Only the declaration's left-hand side is
    # inspected, so ``const helper = require(...)`` does not shadow require.
    for index, token in enumerate(tokens):
        if token.value not in _DECLARATION_KEYWORDS:
            continue
        cursor = index + 1
        segment_start = cursor
        nesting = 0
        while cursor < len(tokens):
            value = tokens[cursor].value
            if value in {"(", "[", "{"}:
                nesting += 1
            elif value in {")", "]", "}"}:
                if nesting == 0:
                    break
                nesting -= 1
            if (value == "," and nesting == 0) or (value == ";" and nesting == 0):
                segment = tokens[segment_start:cursor]
                equals = next((offset for offset, item in enumerate(segment) if item.value == "="), len(segment))
                if any(item.kind == "identifier" and item.value == "require" for item in segment[:equals]):
                    scope_index = token_scopes[index]
                    if token.value == "var":
                        while scopes[scope_index].kind not in {"function", "program"} and scopes[scope_index].parent is not None:
                            scope_index = scopes[scope_index].parent
                    add_binding(scope_index)
                segment_start = cursor + 1
                if value == ";":
                    break
            cursor += 1
        if segment_start < cursor:
            segment = tokens[segment_start:cursor]
            equals = next((offset for offset, item in enumerate(segment) if item.value == "="), len(segment))
            if any(item.kind == "identifier" and item.value == "require" for item in segment[:equals]):
                scope_index = token_scopes[index]
                if token.value == "var":
                    while scopes[scope_index].kind not in {"function", "program"} and scopes[scope_index].parent is not None:
                        scope_index = scopes[scope_index].parent
                add_binding(scope_index)

    for index, token in enumerate(tokens[:-1]):
        if token.value in {"class", "import"} and tokens[index + 1].value == "require":
            add_binding(token_scopes[index])
        elif token.value == "require" and tokens[index + 1].value in {
            "=", "+=", "-=", "*=", "/=", "??=",
        }:
            # Once source replaces CommonJS require, calls in that function are
            # no longer trusted as loader edges.  The whole function is marked
            # conservatively around branches and use-before-assignment.
            scope_index = token_scopes[index]
            while scopes[scope_index].kind not in {"function", "program"} and scopes[scope_index].parent is not None:
                scope_index = scopes[scope_index].parent
            add_binding(scope_index)

    # Encode expression-arrow ranges as synthetic child scopes.
    for start, end in expression_shadow_ranges:
        parent = token_scopes[start] if start < len(token_scopes) else 0
        scopes.append(_Scope(start, end, parent, "arrow-expression", {"require"}))
        scope_index = len(scopes) - 1
        for index in range(start, min(end + 1, len(token_scopes))):
            token_scopes[index] = scope_index
    return scopes, token_scopes


def _is_shadowed(index: int, scopes: list[_Scope], token_scopes: list[int]) -> bool:
    scope_index: int | None = token_scopes[index]
    while scope_index is not None:
        scope = scopes[scope_index]
        if "require" in scope.bindings:
            return True
        scope_index = scope.parent
    return False


def resolve_relative_javascript_candidates(specifier: str, source_path: str) -> tuple[str, ...]:
    """Return Node-style logical candidates without touching the filesystem."""
    if not specifier.startswith(("./", "../")) or "\0" in specifier:
        return ()
    parent = posixpath.dirname(source_path) or "."
    base = posixpath.normpath(posixpath.join(parent, specifier))
    final_name = posixpath.basename(base)
    if "." in final_name and not final_name.startswith("."):
        return (base,)
    return (
        base,
        base + ".js",
        base + ".json",
        base + ".node",
        posixpath.join(base, "package.json"),
        posixpath.join(base, "index.js"),
        posixpath.join(base, "index.json"),
        posixpath.join(base, "index.node"),
    )


def _binding_from_require(tokens: list[_Token], require_index: int) -> tuple[str, dict[str, str]]:
    declaration = require_index - 1
    while declaration >= 0 and tokens[declaration].value != ";":
        if tokens[declaration].value in _DECLARATION_KEYWORDS:
            break
        declaration -= 1
    segment = tokens[declaration:require_index] if declaration >= 0 else []
    if not segment or segment[0].value not in _DECLARATION_KEYWORDS:
        return "", {}
    equals = max((index for index, token in enumerate(segment) if token.value == "="), default=-1)
    if equals < 1 or equals != len(segment) - 1:
        return "", {}
    left = segment[1:equals]
    if len(left) == 1 and left[0].kind == "identifier":
        return left[0].value, {}
    if len(left) >= 2 and left[0].value == "{" and left[-1].value == "}":
        exports: dict[str, str] = {}
        entries: list[list[_Token]] = []
        current: list[_Token] = []
        for token in left[1:-1]:
            if token.value == ",":
                if current:
                    entries.append(current)
                    current = []
            else:
                current.append(token)
        if current:
            entries.append(current)
        for entry in entries:
            names = [item.value for item in entry if item.kind == "identifier"]
            if not names:
                continue
            export_name = names[0]
            local_name = names[-1]
            exports[local_name] = export_name
        return "", exports
    return "", {}


def _curly_depths(tokens: list[_Token]) -> list[int]:
    depths: list[int] = []
    depth = 0
    for token in tokens:
        if token.value == "}":
            depth = max(0, depth - 1)
        depths.append(depth)
        if token.value == "{":
            depth += 1
    return depths


def _is_module_top_level_call_statement(
    tokens: list[_Token], start: int, opened: int,
    pairs: dict[int, int], depths: list[int],
) -> bool:
    """Accept only a standalone call statement at module lexical depth zero."""
    close = pairs.get(opened)
    if close is None or depths[start] != 0:
        return False
    if start and tokens[start - 1].value not in {";", "}"}:
        return False
    return close + 1 == len(tokens) or tokens[close + 1].value == ";"


def _export_call_evidence(
    tokens: list[_Token], require_index: int, close_index: int,
    pairs: dict[int, int],
) -> tuple[JavascriptCallEvidence, ...]:
    evidence: list[JavascriptCallEvidence] = []
    depths = _curly_depths(tokens)
    if close_index + 3 < len(tokens) and tokens[close_index + 1].value in {".", "?."}:
        name = tokens[close_index + 2]
        if (name.kind == "identifier" and tokens[close_index + 3].value == "("
                and _is_module_top_level_call_statement(
                    tokens, require_index, close_index + 3, pairs, depths
                )):
            evidence.append(JavascriptCallEvidence(
                name.value, name.value, name.line, "direct-member-call"
            ))
    if close_index + 1 < len(tokens) and tokens[close_index + 1].value == "(":
        if _is_module_top_level_call_statement(
            tokens, require_index, close_index + 1, pairs, depths
        ):
            evidence.append(JavascriptCallEvidence(
                "module.exports", "", tokens[close_index + 1].line,
                "direct-module-call",
            ))

    namespace, bindings = _binding_from_require(tokens, require_index)
    for index in range(close_index + 1, len(tokens) - 1):
        token = tokens[index]
        if namespace and token.value == namespace:
            if tokens[index + 1].value in {"=", "+=", "-=", "*=", "/="}:
                namespace = ""
                continue
            if index + 3 < len(tokens) and tokens[index + 1].value in {".", "?."}:
                member = tokens[index + 2]
                if (member.kind == "identifier"
                        and tokens[index + 3].value == "("
                        and _is_module_top_level_call_statement(
                            tokens, index, index + 3, pairs, depths
                        )):
                    evidence.append(JavascriptCallEvidence(
                        member.value, namespace, member.line,
                        "namespace-member-call",
                    ))
        if token.value in bindings:
            if tokens[index + 1].value in {"=", "+=", "-=", "*=", "/="}:
                bindings.pop(token.value, None)
                continue
            previous = tokens[index - 1].value if index else ""
            if (tokens[index + 1].value == "("
                    and previous not in {".", "?."}
                    and _is_module_top_level_call_statement(
                        tokens, index, index + 1, pairs, depths
                    )):
                evidence.append(JavascriptCallEvidence(
                    bindings[token.value], token.value, token.line,
                    "destructured-binding-call",
                ))
    unique: dict[tuple[str, str, int, str], JavascriptCallEvidence] = {}
    for item in evidence:
        unique[(item.export_name, item.local_name, item.line, item.form)] = item
    return tuple(unique.values())


def extract_relative_javascript_dependencies(
    source: str,
    source_path: str,
    *,
    known_paths: Iterable[str] = (),
    max_dependencies: int = _MAX_DEPENDENCIES,
) -> JavascriptDependencyReport:
    """Extract confirmed relative ``require`` edges without executing source.

    ``known_paths`` should normally be the authoritative snapshot's file names.
    It is used only to select the first existing Node-style candidate.  With no
    match, ``selected_path`` remains ``None`` and callers can apply their own
    missing-content policy.
    """
    if not isinstance(source, str) or not isinstance(source_path, str):
        raise TypeError("source and source_path must be strings")
    if len(source) > _MAX_SOURCE_CHARS:
        return JavascriptDependencyReport((), (
            JavascriptDependencyUnknown(1, "JavaScript source size limit exceeded"),
        ), False)
    tokens, unknowns = _lex(source)
    pairs, delimiters_complete = _matching_delimiters(tokens)
    scopes, token_scopes = _build_scopes(tokens, pairs)
    known = {posixpath.normpath(str(path)) for path in known_paths}
    dependencies: list[JavascriptDependency] = []
    complete = delimiters_complete and not any(
        item.reason.endswith(("limit exceeded", "unterminated block comment", "unterminated template literal"))
        or item.reason.startswith("invalid or unterminated")
        for item in unknowns
    )
    if not delimiters_complete:
        unknowns.append(JavascriptDependencyUnknown(1, "unbalanced JavaScript delimiters"))

    for index, token in enumerate(tokens):
        if token.kind != "identifier" or token.value != "require":
            continue
        if index and tokens[index - 1].value in {".", "?."}:
            continue
        if index + 1 >= len(tokens) or tokens[index + 1].value != "(":
            continue
        opened = index + 1
        close = pairs.get(opened)
        if close is None:
            if len(unknowns) < _MAX_UNKNOWNS:
                unknowns.append(JavascriptDependencyUnknown(token.line, "require call has no balanced closing parenthesis"))
            complete = False
            continue
        if _is_shadowed(index, scopes, token_scopes):
            if len(unknowns) < _MAX_UNKNOWNS:
                unknowns.append(JavascriptDependencyUnknown(token.line, "require identifier is lexically shadowed"))
            continue
        arguments = tokens[opened + 1:close]
        if len(arguments) != 1 or arguments[0].kind != "string":
            if len(unknowns) < _MAX_UNKNOWNS:
                unknowns.append(JavascriptDependencyUnknown(token.line, "dynamic require specifier was not resolved"))
            continue
        specifier = arguments[0].value
        if not specifier.startswith(("./", "../")):
            continue
        candidates = resolve_relative_javascript_candidates(specifier, source_path)
        if not candidates:
            if len(unknowns) < _MAX_UNKNOWNS:
                unknowns.append(JavascriptDependencyUnknown(token.line, "relative require path was invalid"))
            continue
        selected = next((candidate for candidate in candidates[:4] if candidate in known), None)
        package_manifest = candidates[4]
        if selected is None and package_manifest in known:
            if len(unknowns) < _MAX_UNKNOWNS:
                unknowns.append(JavascriptDependencyUnknown(
                    token.line,
                    "relative require uses a directory package whose main entry was not resolved",
                ))
        elif selected is None:
            selected = next(
                (candidate for candidate in candidates[5:] if candidate in known), None
            )
        dependencies.append(JavascriptDependency(
            specifier=specifier,
            candidate_paths=candidates,
            selected_path=selected,
            line=token.line,
            export_call_evidence=_export_call_evidence(tokens, index, close, pairs),
        ))
        if len(dependencies) >= max_dependencies:
            unknowns.append(JavascriptDependencyUnknown(token.line, "JavaScript dependency limit exceeded"))
            complete = False
            break

    return JavascriptDependencyReport(
        tuple(dependencies), tuple(unknowns[:_MAX_UNKNOWNS]), complete
    )


@dataclass(frozen=True)
class JavascriptExportEffectSource:
    """Source selected for one statically called CommonJS export."""

    export_name: str
    function_name: str
    line: int
    body_text: str
    confidence: str = "module-top-level-direct-export"


@dataclass(frozen=True)
class JavascriptEffectSourceReport:
    """A narrow source view suitable for the controller's existing checks."""

    scan_text: str
    top_level_text: str
    selected_exports: tuple[JavascriptExportEffectSource, ...]
    unknowns: tuple[JavascriptDependencyUnknown, ...]
    complete: bool


@dataclass(frozen=True)
class _JavascriptFunctionBody:
    name: str
    declaration: int
    body_open: int
    body_close: int
    line: int
    form: str


def _javascript_function_bodies(
    tokens: list[_Token], pairs: dict[int, int], depths: list[int],
) -> tuple[list[_JavascriptFunctionBody], list[JavascriptDependencyUnknown]]:
    """Find bodies so top-level rendering never includes dormant function text."""
    bodies: list[_JavascriptFunctionBody] = []
    unknowns: list[JavascriptDependencyUnknown] = []
    seen: set[tuple[int, int]] = set()

    for index, token in enumerate(tokens):
        if token.value == "function":
            cursor = index + 1
            if cursor < len(tokens) and tokens[cursor].value == "*":
                unknowns.append(JavascriptDependencyUnknown(
                    token.line, "generator function export slicing is unsupported"
                ))
                cursor += 1
            name = (
                tokens[cursor].value
                if cursor < len(tokens) and tokens[cursor].kind == "identifier"
                else ""
            )
            if name:
                cursor += 1
            if cursor >= len(tokens) or tokens[cursor].value != "(":
                unknowns.append(JavascriptDependencyUnknown(
                    token.line, "function signature could not be resolved"
                ))
                continue
            parameters_close = pairs.get(cursor)
            body_open = parameters_close + 1 if parameters_close is not None else -1
            if (parameters_close is None or body_open >= len(tokens)
                    or tokens[body_open].value != "{"
                    or body_open not in pairs):
                unknowns.append(JavascriptDependencyUnknown(
                    token.line, "function body could not be resolved"
                ))
                continue
            body_close = pairs[body_open]
            key = (body_open, body_close)
            if key not in seen:
                bodies.append(_JavascriptFunctionBody(
                    name, index, body_open, body_close, token.line,
                    "function-declaration",
                ))
                seen.add(key)
            if depths[index] != 0:
                unknowns.append(JavascriptDependencyUnknown(
                    token.line, "nested or block function slicing is unsupported"
                ))
            elif not name:
                unknowns.append(JavascriptDependencyUnknown(
                    token.line, "anonymous function export slicing is unsupported"
                ))
            continue

        if token.value == "=>":
            body_open = index + 1
            if (body_open < len(tokens) and tokens[body_open].value == "{"
                    and body_open in pairs):
                body_close = pairs[body_open]
                key = (body_open, body_close)
                if key not in seen:
                    bodies.append(_JavascriptFunctionBody(
                        "", index, body_open, body_close, token.line,
                        "arrow-function",
                    ))
                    seen.add(key)
            unknowns.append(JavascriptDependencyUnknown(
                token.line, "arrow function export slicing is unsupported"
            ))
            continue

        if (token.kind == "identifier" and token.value not in {
                "catch", "for", "if", "switch", "while", "with",
            } and index + 1 < len(tokens) and tokens[index + 1].value == "("
                and not (index and tokens[index - 1].value == "function")):
            parameters_close = pairs.get(index + 1)
            body_open = parameters_close + 1 if parameters_close is not None else -1
            if (parameters_close is not None and body_open < len(tokens)
                    and tokens[body_open].value == "{"
                    and body_open in pairs):
                body_close = pairs[body_open]
                key = (body_open, body_close)
                if key not in seen:
                    bodies.append(_JavascriptFunctionBody(
                        token.value, index, body_open, body_close,
                        token.line, "method",
                    ))
                    seen.add(key)
                unknowns.append(JavascriptDependencyUnknown(
                    token.line, "method export slicing is unsupported"
                ))

    return bodies, unknowns


def _comment_free_gap(gap: str) -> str:
    """Keep layout while ensuring skipped comments cannot trigger text rules."""
    return "".join(character if character.isspace() else " " for character in gap)


def _render_javascript_tokens(
    source: str, tokens: list[_Token], included: Iterable[int],
) -> str:
    indexes = sorted(set(included))
    if not indexes:
        return ""
    output: list[str] = []
    previous_index: int | None = None
    previous_end = 0
    for index in indexes:
        token = tokens[index]
        if previous_index is not None:
            if index == previous_index + 1:
                output.append(_comment_free_gap(source[previous_end:token.start]))
            else:
                output.append("\n")
        output.append(source[token.start:token.end])
        previous_index = index
        previous_end = token.end
    return "".join(output).strip()


def _split_javascript_object_entries(
    tokens: list[_Token], opened: int, closed: int, depths: list[int],
) -> list[list[int]]:
    entries: list[list[int]] = []
    current: list[int] = []
    entry_depth = depths[opened] + 1
    for index in range(opened + 1, closed):
        if tokens[index].value == "," and depths[index] == entry_depth:
            if current:
                entries.append(current)
                current = []
        else:
            current.append(index)
    if current:
        entries.append(current)
    return entries


def _literal_false_branch_tokens(
    tokens: list[_Token], pairs: dict[int, int],
) -> set[int]:
    """Return braced if(false) statements that cannot execute."""
    unreachable: set[int] = set()
    for index, token in enumerate(tokens):
        if token.value != "if" or index + 1 >= len(tokens):
            continue
        condition_open = index + 1
        if tokens[condition_open].value != "(":
            continue
        condition_close = pairs.get(condition_open)
        if condition_close is None:
            continue
        condition = tokens[condition_open + 1:condition_close]
        body_open = condition_close + 1
        if (len(condition) != 1 or condition[0].value != "false"
                or body_open >= len(tokens)
                or tokens[body_open].value != "{"
                or body_open not in pairs):
            continue
        unreachable.update(range(index, pairs[body_open] + 1))
    return unreachable


def _module_top_level_called_functions(
    tokens: list[_Token],
    pairs: dict[int, int],
    depths: list[int],
    names: Iterable[str],
) -> tuple[str, ...]:
    """Find standalone top-level calls to locally declared named functions."""
    available = set(names)
    called: list[str] = []
    for index, token in enumerate(tokens[:-1]):
        if (token.value in available and tokens[index + 1].value == "("
                and _is_module_top_level_call_statement(
                    tokens, index, index + 1, pairs, depths
                )):
            called.append(token.value)
    return tuple(dict.fromkeys(called))


def select_javascript_effect_source(
    source: str,
    called_exports: Iterable[str],
) -> JavascriptEffectSourceReport:
    """Select top-level evaluation plus directly called exported function bodies.

    Supported export form is deliberately narrow: named top-level function
    declarations exposed through a module.exports object shorthand. Unsupported
    syntax produces local unknowns; it is not a global policy verdict.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if len(source) > _MAX_SOURCE_CHARS:
        unknown = JavascriptDependencyUnknown(
            1, "JavaScript source size limit exceeded"
        )
        return JavascriptEffectSourceReport("", "", (), (unknown,), False)

    requested = tuple(dict.fromkeys(str(name) for name in called_exports))
    if len(requested) > _MAX_DEPENDENCIES:
        unknown = JavascriptDependencyUnknown(
            1, "called JavaScript export limit exceeded"
        )
        return JavascriptEffectSourceReport("", "", (), (unknown,), False)
    if any(not name or not all(_is_identifier_continue(char) for char in name)
           or not _is_identifier_start(name[0]) for name in requested):
        unknown = JavascriptDependencyUnknown(
            1, "called JavaScript export name is unsupported"
        )
        return JavascriptEffectSourceReport("", "", (), (unknown,), False)

    tokens, lexer_unknowns = _lex(source)
    pairs, delimiters_complete = _matching_delimiters(tokens)
    depths = _curly_depths(tokens)
    bodies, body_unknowns = _javascript_function_bodies(tokens, pairs, depths)
    unknowns = list(lexer_unknowns) + body_unknowns
    if not delimiters_complete:
        unknowns.append(JavascriptDependencyUnknown(
            1, "unbalanced JavaScript delimiters"
        ))

    commonjs_ambiguous = False
    for index, token in enumerate(tokens[:-1]):
        declaration_shadow = (
            token.value in _DECLARATION_KEYWORDS
            and tokens[index + 1].value in {"module", "exports"}
        )
        function_shadow = (
            token.value == "function"
            and tokens[index + 1].value in {"module", "exports"}
        )
        if depths[index] == 0 and (declaration_shadow or function_shadow):
            commonjs_ambiguous = True
            unknowns.append(JavascriptDependencyUnknown(
                token.line, "module or exports identifier is shadowed"
            ))

    top_level_function_groups: dict[str, list[_JavascriptFunctionBody]] = {}
    for body in bodies:
        if (body.form == "function-declaration"
                and depths[body.declaration] == 0 and body.name):
            top_level_function_groups.setdefault(body.name, []).append(body)
    top_level_functions: dict[str, _JavascriptFunctionBody] = {}
    for name, definitions in top_level_function_groups.items():
        if len(definitions) == 1:
            top_level_functions[name] = definitions[0]
        else:
            commonjs_ambiguous = True
            unknowns.append(JavascriptDependencyUnknown(
                definitions[-1].line,
                f"top-level function {name!r} has multiple declarations",
            ))

    module_export_assignments: list[int] = []
    for index in range(max(0, len(tokens) - 3)):
        if depths[index] != 0:
            continue
        if (tokens[index].value == "module"
                and tokens[index + 1].value == "."
                and tokens[index + 2].value == "exports"):
            if tokens[index + 3].value == "=":
                module_export_assignments.append(index)
            elif tokens[index + 3].value in {".", "?."}:
                commonjs_ambiguous = True
                unknowns.append(JavascriptDependencyUnknown(
                    tokens[index].line,
                    "extended module.exports mutation is unsupported",
                ))
        elif (tokens[index].value == "exports"
                and tokens[index + 1].value in {".", "?."}):
            commonjs_ambiguous = True
            unknowns.append(JavascriptDependencyUnknown(
                tokens[index].line, "exports property mutation is unsupported"
            ))

    if len(module_export_assignments) > 1:
        commonjs_ambiguous = True
        unknowns.append(JavascriptDependencyUnknown(
            tokens[module_export_assignments[-1]].line,
            "multiple module.exports assignments are unsupported",
        ))

    exported_locals: dict[str, str] = {}
    if not commonjs_ambiguous and len(module_export_assignments) == 1:
        index = module_export_assignments[0]
        value_index = index + 4
        if tokens[value_index].value != "{" or value_index not in pairs:
            commonjs_ambiguous = True
            unknowns.append(JavascriptDependencyUnknown(
                tokens[index].line,
                "non-object module.exports assignment is unsupported",
            ))
        else:
            close = pairs[value_index]
            for entry in _split_javascript_object_entries(
                tokens, value_index, close, depths
            ):
                if len(entry) == 1 and tokens[entry[0]].kind == "identifier":
                    name = tokens[entry[0]].value
                    exported_locals[name] = name
                else:
                    commonjs_ambiguous = True
                    unknowns.append(JavascriptDependencyUnknown(
                        tokens[entry[0]].line,
                        "non-shorthand module.exports entry is unsupported",
                    ))
            if commonjs_ambiguous:
                exported_locals.clear()

    assignment_operators = {"=", "+=", "-=", "*=", "/=", "??="}
    reassigned_functions = {
        name
        for name in top_level_functions
        if any(
            token.value == name
            and index + 1 < len(tokens)
            and tokens[index + 1].value in assignment_operators
            and depths[index] == 0
            for index, token in enumerate(tokens)
        )
    }
    for name in reassigned_functions:
        unknowns.append(JavascriptDependencyUnknown(
            top_level_functions[name].line,
            f"top-level function binding {name!r} is reassigned",
        ))
        top_level_functions.pop(name, None)
        for export_name, local_name in list(exported_locals.items()):
            if local_name == name:
                exported_locals.pop(export_name, None)

    unreachable_tokens = _literal_false_branch_tokens(tokens, pairs)
    excluded_from_top_level: set[int] = set(unreachable_tokens)
    for body in bodies:
        excluded_from_top_level.update(
            range(body.body_open + 1, body.body_close)
        )
    top_level_text = _render_javascript_tokens(
        source,
        tokens,
        (index for index in range(len(tokens))
         if index not in excluded_from_top_level),
    )

    selected: list[JavascriptExportEffectSource] = []
    for export_name in requested:
        local_name = exported_locals.get(export_name)
        body = top_level_functions.get(local_name or "")
        if local_name is None or body is None:
            unknowns.append(JavascriptDependencyUnknown(
                1,
                f"called export {export_name!r} could not be mapped "
                "to a named top-level function",
            ))
            continue
        nested_interiors: set[int] = set()
        for nested in bodies:
            if (nested.body_open != body.body_open
                    and body.body_open < nested.body_open
                    and nested.body_close < body.body_close):
                nested_interiors.update(
                    range(nested.body_open + 1, nested.body_close)
                )
        body_text = _render_javascript_tokens(
            source,
            tokens,
            (index for index in range(body.body_open + 1, body.body_close)
             if index not in nested_interiors
             and index not in unreachable_tokens),
        )
        selected.append(JavascriptExportEffectSource(
            export_name, local_name, body.line, body_text
        ))

    selected_function_names = {
        item.function_name for item in selected
    }
    directly_called_body_texts: list[str] = []
    for name in _module_top_level_called_functions(
        tokens, pairs, depths, top_level_functions
    ):
        if name in selected_function_names:
            continue
        body = top_level_functions[name]
        nested_interiors: set[int] = set()
        for nested in bodies:
            if (nested.body_open != body.body_open
                    and body.body_open < nested.body_open
                    and nested.body_close < body.body_close):
                nested_interiors.update(
                    range(nested.body_open + 1, nested.body_close)
                )
        directly_called_body_texts.append(_render_javascript_tokens(
            source,
            tokens,
            (index for index in range(body.body_open + 1, body.body_close)
             if index not in nested_interiors
             and index not in unreachable_tokens),
        ))

    fragments = [top_level_text]
    fragments.extend(item.body_text for item in selected if item.body_text)
    fragments.extend(text for text in directly_called_body_texts if text)
    scan_text = "\n".join(fragment for fragment in fragments if fragment)
    bounded_unknowns = tuple(unknowns[:_MAX_UNKNOWNS])
    complete = delimiters_complete and not unknowns
    return JavascriptEffectSourceReport(
        scan_text, top_level_text, tuple(selected), bounded_unknowns, complete
    )
