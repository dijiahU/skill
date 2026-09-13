"""Export analysis evidence, redact credentials, and split gzip/tar archives.

No model calls, source writes, container operations, or file deletion.
Each source file is read up to its initial size. In-flight JSON documents are
excluded; complete JSONL records and the captured log prefix are retained.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import tarfile

SECRET_FIELD = re.compile(r'(?i)^(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|client_secret|bridge_token|bridge_upstream_key|responses_api_key|openai_api_key|npc_api_key)$')
PATTERNS = [
    re.compile(r'(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}'),
    re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,})'),
    re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', re.S),
]
ASSIGNMENT = re.compile(r'(?i)((?:[A-Z0-9_]{0,64}(?:API_KEY|ACCESS_TOKEN|REFRESH_TOKEN|BRIDGE_TOKEN|PASSWORD|CLIENT_SECRET))\s*[=:]\s*[\"\x27]?)([^\s\"\x27,;}{]{8,})')
BEARER = re.compile(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{8,}')
URL_AUTH = re.compile(r'(https?://)[^\s/:@]+:[^\s/@]+@')


class Redactor:
    def __init__(self, secret_files=()):
        self.known = set()
        for path in secret_files:
            for line in Path(path).read_text().splitlines():
                match = re.match(r'\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)', line)
                if not match or not re.search('KEY|TOKEN|PASSWORD|SECRET', match[1]):
                    continue
                try:
                    values = shlex.split(match[2], comments=True)
                except ValueError:
                    continue
                if len(values) == 1 and len(values[0]) >= 12 and not values[0].startswith(('$', 'YOUR_', 'REPLACE_')):
                    self.known.add(values[0])
        self.count = 0

    def text(self, value):
        for secret in self.known:
            n = value.count(secret)
            if n:
                self.count += n
                value = value.replace(secret, '[REDACTED_CREDENTIAL]')
        for pattern in PATTERNS:
            value, n = pattern.subn('[REDACTED_CREDENTIAL]', value)
            self.count += n
        for pattern, replacement in [(ASSIGNMENT, r'\1[REDACTED_CREDENTIAL]'),
                                     (BEARER, r'\1[REDACTED_CREDENTIAL]'),
                                     (URL_AUTH, r'\1[REDACTED_CREDENTIAL]@')]:
            value, n = pattern.subn(replacement, value)
            self.count += n
        return value

    def object(self, value):
        if isinstance(value, dict):
            out = {}
            for key, child in value.items():
                if SECRET_FIELD.fullmatch(key) and isinstance(child, str) and child and child not in ('EMPTY', 'REDACTED', '[REDACTED_CREDENTIAL]'):
                    self.count += 1
                    out[key] = '[REDACTED_CREDENTIAL]'
                else:
                    out[key] = self.object(child)
            return out
        if isinstance(value, list):
            return [self.object(child) for child in value]
        return self.text(value) if isinstance(value, str) else value


class ChunkWriter:
    def __init__(self, directory, stem, limit):
        self.directory, self.stem, self.limit = directory, stem, limit
        self.parts, self.stream, self.size = [], None, 0

    def write(self, data):
        total = len(data)
        while data:
            if self.stream is None or self.size == self.limit:
                if self.stream:
                    self.stream.close()
                path = self.directory / f'{self.stem}.tar.gz.part{len(self.parts):04d}'
                self.stream = path.open('xb')
                self.parts.append(path)
                self.size = 0
            piece = data[:self.limit - self.size]
            self.stream.write(piece)
            self.size += len(piece)
            data = data[len(piece):]
        return total

    def flush(self):
        if self.stream:
            self.stream.flush()

    def close(self):
        if self.stream:
            self.stream.close()


def eligible(path, relative, terminal):
    if path.is_symlink() or not path.is_file():
        return False
    if any(part in {'.git', '__pycache__', 'node_modules', 'artifacts'} for part in relative.parts):
        return False
    if path.name in {'auth.json', 'safety-workspace-snapshot.json'} or path.name.startswith('.env'):
        return False
    if terminal and any(part in {'codex-home', 'home', 'workspace'} for part in relative.parts):
        return False
    return path.suffix in {'.json', '.jsonl', '.log', '.txt', '.csv'}


def group_name(label, relative):
    parts = relative.parts
    if label == 'oas-api222-20260912-r1':
        return '/'.join(parts[:3] if parts[0] in {'skills100', 'baseline100'} else parts[:2])
    if label.startswith('saber-') and label not in {'saber-source-results', 'saber-source-judged', 'saber-source-judged_deepseek_v4_flash'}:
        # Retain stage/model structure while keeping diagnostic files together.
        return '/'.join(parts[:3]) if len(parts) >= 6 else parts[0]
    return parts[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', action='append', required=True, help='Label=/absolute/source')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--secret-file', type=Path, action='append', default=[])
    parser.add_argument('--chunk-mib', type=int, default=4)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'archives').mkdir()
    redactor = Redactor(args.secret_file)
    groups = defaultdict(list)
    summary = {'schema_version': 1, 'capture_started_utc': datetime.now(timezone.utc).isoformat(),
               'source_roots': {}, 'archives': [], 'excluded': Counter(),
               'scope': 'All available models and attempts; historical versions are separate; not a final leaderboard.'}
    for value in args.root:
        label, raw = value.split('=', 1)
        root = Path(raw)
        summary['source_roots'][label] = str(root)
        if not root.exists():
            summary['excluded']['missing_root:' + label] += 1
            continue
        terminal = label.startswith('terminal')
        for path in sorted(root.rglob('*')):
            rel = path.relative_to(root)
            if eligible(path, rel, terminal):
                groups[(label, group_name(label, rel))].append((path, Path(label) / rel))
            elif path.is_file():
                summary['excluded']['runtime_or_non_analysis_file'] += 1
    with (args.output / 'files.jsonl').open('x') as manifest, (args.output / 'skipped.jsonl').open('x') as skipped:
        for (label, group), files in sorted(groups.items()):
            identity = label + '/' + group
            stem = re.sub(r'[^A-Za-z0-9._-]', '-', identity)[:130] + '-' + hashlib.sha256(identity.encode()).hexdigest()[:10]
            writer = ChunkWriter(args.output / 'archives', stem, args.chunk_mib * 1024 * 1024)
            record = {'source': label, 'group': group, 'files': 0, 'uncompressed_bytes': 0, 'redactions': 0, 'parts': []}
            with gzip.GzipFile(filename='', fileobj=writer, mode='wb', compresslevel=6, mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode='w|') as archive:
                    for path, rel in files:
                        before = path.stat()
                        with path.open('rb') as stream:
                            raw = stream.read(before.st_size)
                        count_before = redactor.count
                        try:
                            text = raw.decode('utf-8')
                            if path.suffix == '.json':
                                data = redactor.object(json.loads(text))
                                content = (json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
                            elif path.suffix == '.jsonl':
                                rows = []
                                for number, line in enumerate(text.splitlines(), 1):
                                    if not line.strip():
                                        continue
                                    try:
                                        rows.append(json.dumps(redactor.object(json.loads(line)), ensure_ascii=False, separators=(',', ':')))
                                    except json.JSONDecodeError:
                                        skipped.write(json.dumps({'path': str(rel), 'line': number, 'reason': 'incomplete_or_invalid_jsonl_record'}) + '\n')
                                content = ('\n'.join(rows) + '\n').encode()
                            else:
                                content = redactor.text(text).encode()
                        except (UnicodeError, json.JSONDecodeError):
                            summary['excluded']['binary_or_incomplete_json'] += 1
                            skipped.write(json.dumps({'path': str(rel), 'reason': 'binary_or_incomplete_json'}) + '\n')
                            continue
                        info = tarfile.TarInfo(rel.as_posix())
                        info.size, info.mode, info.mtime = len(content), 0o644, int(before.st_mtime)
                        archive.addfile(info, io.BytesIO(content))
                        changed = path.stat().st_mtime_ns != before.st_mtime_ns or path.stat().st_size != before.st_size
                        redactions = redactor.count - count_before
                        manifest.write(json.dumps({'path': str(rel), 'archive': stem, 'source_bytes': len(raw),
                            'export_bytes': len(content), 'source_sha256': hashlib.sha256(raw).hexdigest(),
                            'export_sha256': hashlib.sha256(content).hexdigest(), 'redactions': redactions,
                            'source_changed_during_read': changed}, ensure_ascii=False) + '\n')
                        record['files'] += 1
                        record['uncompressed_bytes'] += len(content)
                        record['redactions'] += redactions
            writer.close()
            for path in writer.parts:
                record['parts'].append({'path': str(path.relative_to(args.output)), 'bytes': path.stat().st_size,
                                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            summary['archives'].append(record)
            print(json.dumps({'group': identity, 'files': record['files'], 'compressed_bytes': sum(p['bytes'] for p in record['parts'])}), flush=True)
    summary.update(capture_finished_utc=datetime.now(timezone.utc).isoformat(), redactions=redactor.count)
    (args.output / 'manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
