"""Track statically generated account rows into whole authentication databases."""
import posixpath
import re
import shlex

_DATABASES = {'/etc/shadow', '/etc/passwd', '/etc/gshadow', '/etc/group'}


def generated_account_database_risk(command: str) -> str:
    if len(command) > 100000:
        return ''
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|<>')
        lexer.whitespace_split = True
        lexer.commenters = '#'
        tokens = list(lexer)
    except ValueError:
        return ''
    units, words = [], []
    for token in tokens:
        if token in {';', '&&', '||', '|', '&'}:
            units.append((words, token))
            words = []
        else:
            words.append(token)
    units.append((words, ''))
    row_files = set()
    row_stream = False
    for words, separator in units[:128]:
        incoming = row_stream
        row_stream = False
        while words and (words[0] in {'sudo', 'command'} or re.fullmatch(r'[A-Za-z_]\w*=.*', words[0])):
            words = words[1:]
        if not words:
            continue
        head = posixpath.basename(words[0])
        args, redirects = [], []
        i = 1
        while i < len(words):
            if words[i] in {'>', '>>'} and i + 1 < len(words):
                redirects.append((words[i], posixpath.normpath(words[i+1])))
                i += 2
            else:
                args.append(words[i])
                i += 1
        row = head in {'echo', 'printf'} and any(re.match(r'^(?:root|[A-Za-z_]\w*):[^\n]*:', value) or value.startswith('root:') for value in args)
        destinations = [target for operator, target in redirects if operator == '>']
        if head == 'tee':
            row = incoming
            if '-a' not in args and '--append' not in args:
                destinations += [posixpath.normpath(x) for x in args if not x.startswith('-')]
        elif head in {'cp', 'mv'}:
            paths = [posixpath.normpath(x) for x in args if not x.startswith('-')]
            if len(paths) == 2:
                row = paths[0] in row_files
                destinations.append(paths[1])
        elif head == 'cat':
            row = any(posixpath.normpath(x) in row_files for x in args if not x.startswith('-'))
        for target in destinations:
            if row:
                if target in _DATABASES:
                    return 'generated account record replaces an entire system authentication database'
                row_files.add(target)
            else:
                row_files.discard(target)
        row_stream = row and separator == '|'
    return ''
