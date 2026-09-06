"""Opt-in repair for URL-encoded href comparisons in the cached OAS helper."""

import ast
import hashlib
import json
import re
from pathlib import Path


HELPERS = {"check_and_download_file", "check_file_in_owncloud_directory"}
IMPORT = "from urllib.parse import unquote as _oas_unquote\n"


def decode_owncloud_hrefs(source: str) -> str:
    """Repair only the two known comparisons, preserving other helper code.

    Preserve upstream substring matching and public signatures. Only decode the
    WebDAV href once: spaces, Unicode, plus signs and literal percent escapes
    must retain their normal URL semantics. Reject unexpected helper versions.
    """
    tree = ast.parse(source)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in HELPERS
    ]
    if {node.name for node in functions} != HELPERS or len(functions) != 2:
        raise ValueError("Unexpected ownCloud helper definitions")
    lines = source.splitlines(keepends=True)
    changed = False
    for node in reversed(functions):
        start, end = node.lineno - 1, node.end_lineno
        segment = "".join(lines[start:end])
        old = r"(?m)^(\s*if file_name in )href(:\s*)$"
        fixed = r"(?m)^\s*if file_name in _oas_unquote\(href\):\s*$"
        if len(re.findall(fixed, segment)) == 1 and not re.search(old, segment):
            continue
        replacement, count = re.subn(old, r"\1_oas_unquote(href)\2", segment)
        if count != 1 or re.search(fixed, segment):
            raise ValueError(f"Unexpected href comparison in {node.name}")
        lines[start:end] = replacement.splitlines(keepends=True)
        changed = True
    if IMPORT not in source:
        if not changed:
            raise ValueError("Patched comparisons have no decoding import")
        insert_at = 0
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str) and node is tree.body[0]:
                    insert_at = node.end_lineno or 0
                    continue
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                insert_at = node.end_lineno or 0
                continue
            break
        lines.insert(insert_at, IMPORT)
    repaired = "".join(lines)
    compile(repaired, "<oas-owncloud-helpers>", "exec")
    return repaired


def repair_file(path: Path) -> dict[str, str | bool]:
    """Keep the original helper before a mechanical, idempotent source repair."""
    original = path.read_text()
    repaired = decode_owncloud_hrefs(original)
    changed = repaired != original
    if changed:
        backup = path.with_name(path.name + ".before-owncloud-url-decoding")
        if backup.exists():
            raise FileExistsError(f"Refusing to replace existing backup: {backup}")
        with backup.open("x") as stream:
            stream.write(original)
        path.write_text(repaired)
    return {
        "repair": "owncloud-url-decoding-v1",
        "changed": changed,
        "before_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "after_sha256": hashlib.sha256(repaired.encode()).hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(repair_file(Path("/utils/common.py"))))
