"""Render transport changes only on real Dockerfile instructions, excluding heredocs."""
import re


def render(source, resolve):
    output, stages, heredocs = [], set(), []
    continued = False
    for line in source.splitlines():
        if not output and re.match(r'^#\s*syntax=',line):
            output.append('# Original frontend directive (using Docker 24 bundled frontend): '+line)
            continue
        if heredocs:
            output.append(line)
            delimiter, strip_tabs = heredocs[0]
            if (line.lstrip('\t') if strip_tabs else line) == delimiter:
                heredocs.pop(0)
            continue
        instruction = re.match(r'^\s*([A-Za-z]+)\s+(.*)$', line) if not continued else None
        if instruction and instruction[1].upper() == 'FROM':
            match = re.match(r'(?i)^(\s*FROM\s+)((?:--platform=\S+\s+)?)(\S+)(.*)$', line)
            reference = match[3]
            if '$' in reference:
                raise ValueError('Dynamic FROM requires explicit build argument resolution')
            if reference.lower() not in stages:
                line = match[1] + match[2] + resolve(reference) + match[4]
            alias = re.search(r'(?i)\sAS\s+(\S+)', match[4])
            if alias:
                stages.add(alias[1].lower())
        # Track shell and Docker heredocs before touching command text.
        if instruction and instruction[1].upper() in {'RUN','COPY','ADD'} or continued:
            heredocs.extend((m[2], bool(m[1])) for m in re.finditer(r'''<<(-?)["']?([A-Za-z_][\w.-]*)["']?''', line))
            line = re.sub(r'\bapt-get\s+', 'apt-get -o Acquire::Retries=5 -o Acquire::http::Pipeline-Depth=0 ', line)
            line = re.sub(r'(\bRUN\s+|&&\s*|\|\|\s*)curl\s+', r'\1curl --retry 5 --retry-all-errors --connect-timeout 30 ', line)
        output.append(line)
        continued = line.rstrip().endswith('\\')
    if heredocs:
        raise ValueError('Unterminated Dockerfile heredoc')
    return '\n'.join(output) + '\n'
