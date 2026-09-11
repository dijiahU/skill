"""Bounded source provenance for a literal create-then-execute shell command.

This is a parser, never a shell executor. Unknown syntax yields no evidence.
Only a leading, non-expanding cat heredoc and one immediate interpreter call
are supported. In particular a later write cannot justify an earlier execute.
"""
from pathlib import Path
import re
import shlex


def proposed_controller(command: str, cwd: Path):
    lines = command.splitlines(keepends=True)
    if not lines:
        return None
    header = lines[0].strip()
    directory = re.match(r"cd ([/A-Za-z0-9_.-]+)\s*&&\s*", header)
    if directory:
        cwd = (cwd / directory.group(1)).resolve()
        header = header[directory.end():]
    marker = re.search(r"<<\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1", header)
    if not marker:
        return None
    rest = header[:marker.start()] + header[marker.end():]
    # Literal paths only: no append, pipelines, expansions, extra redirections,
    # options, conditionals, or commands before the write.
    target = re.fullmatch(r"cat\s*>\s*([/A-Za-z0-9_.-]+)\s*", rest)
    if not target:
        return None
    end = next((i for i in range(1, len(lines))
                if lines[i].rstrip('\r\n') == marker.group(2)), None)
    if end is None:
        return None
    body = ''.join(lines[1:end])
    if len(body) > 1_000_000:
        return None
    suffix = ''.join(lines[end + 1:]).strip()
    # Only standard diagnostic duplication and a bounded output reader may
    # follow execution. No later rewrite, fallback, asynchronous execution,
    # changed working directory, or command substitution is modeled.
    tail = re.sub(r'\s+2>&1(?=\s|$)', ' ', suffix)
    if any(char in tail for char in '\n;&<>$`'):
        return None
    pieces = tail.split('|')
    if len(pieces) > 2:
        return None
    if len(pieces) == 2 and not re.fullmatch(
            r'\s*(?:head|tail)(?:\s+-(?:n\s*)?\d+)?\s*', pieces[1]):
        return None
    try:
        words = shlex.split(pieces[0])
    except ValueError:
        return None
    if len(words) < 2 or not re.fullmatch(r'(?:python(?:3(?:\.\d+)?)?|bash|sh)', words[0]):
        return None
    if words[1].startswith('-') or not re.fullmatch(r'[/A-Za-z0-9_.-]+', words[1]):
        return None
    path = (cwd / target.group(1)).resolve()
    if (cwd / words[1]).resolve() != path:
        return None
    # Paths/arguments containing glob characters are not statically literal.
    if any(re.search(r'[*?\[~]', word) for word in words[1:]):
        return None
    return path, body, suffix, cwd
