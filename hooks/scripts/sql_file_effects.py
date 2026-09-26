"""Static SQL-file invocation review using the supplied workspace snapshot."""
from __future__ import annotations

import posixpath
import re
import shlex


def sql_code(sql: str) -> str:
    """Mask comments and quoted data before recognizing statement verbs."""
    return re.sub(r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", ' ', sql, flags=re.S)


def sql_file_command_risk(command: str, cwd: str, files: dict[str, str]) -> str:
    if len(command) > 100000:
        return ''
    def resolved(path):
        return posixpath.normpath(path if path.startswith('/') else posixpath.join(cwd, path))
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|<>')
        lexer.whitespace_split = True
        lexer.commenters = '#'
        words = list(lexer)
    except ValueError:
        return ''
    segments = [[]]
    for word in words:
        if word in {';', '&&', '||', '|'}:
            segments.append([])
        else:
            segments[-1].append(word)
    for words in segments[:32]:
        if len(words) == 2 and words[0] == 'cd':
            cwd = resolved(words[1])
            continue
        if not words or posixpath.basename(words[0]) != 'sqlite3' or '-readonly' in words:
            continue
        # Keep the narrow direct database form. Unknown option values and shell
        # expansion are not guessed; callers may perform their own bounded unwrap.
        if len(words) < 3 or words[1].startswith('-'):
            continue
        database = words[1]
        if database == ':memory:' or any(c in database for c in '$`*?'):
            continue
        source = ''
        if '<' in words:
            i = words.index('<')
            if i + 1 < len(words):
                source = words[i + 1]
        elif words[2].startswith('.read '):
            try:
                args = shlex.split(words[2])
                source = args[1] if len(args) == 2 else ''
            except ValueError:
                pass
        if not source or any(c in source for c in '$`*?'):
            continue
        sql = files.get(resolved(source))
        if not isinstance(sql, str) or len(sql) > 500000:
            continue
        code = sql_code(sql)
        destructive = re.search(r'(?:^|;)\s*(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)\b|TRUNCATE\s+(?:TABLE\s+)?\w|DELETE\s+FROM\b)', code, re.I)
        if not destructive:
            continue
        hold = re.search(r'LEGAL\s+HOLD', sql, re.I) and re.search(r'do\s+not\s+delete|不得删除|禁止删除', sql, re.I)
        if hold:
            return 'destructive SQL execution conflicts with an explicit legal-hold retention marker'
        # Production evidence is scoped to this workspace; a test database in a
        # regenerable subtree is not made production by an unrelated changelog.
        db = resolved(database)
        parts = db.split('/')
        scratch = any(p in {'tmp', 'temp', 'tests', 'test', 'fixtures', '.cache'} for p in parts)
        production = bool(re.search(r'(?:^|[/_.-])prod(?:uction)?(?:[/_.-]|$)', db, re.I))
        if not production and not scratch:
            for path, content in files.items():
                if not path.startswith(cwd.rstrip('/') + '/') or not path.lower().endswith(('.md', '.txt')):
                    continue
                if re.search(r'\bCURRENT\s+PRODUCTION\b|\bproduction\s+database\b|生产数据库', content[:100000], re.I):
                    production = True
                    break
        if production and not scratch:
            return 'SQL file destroys tables or rows in a workspace identified as production'
    return ''
