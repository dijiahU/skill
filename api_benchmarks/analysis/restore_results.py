"""Verify exported archive parts and optionally restore their regular files."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--output', type=Path, help='New directory; omit to verify only')
    parser.add_argument('--source', help='Restore only the specified manifest source label')
    args = parser.parse_args()
    manifest = json.loads((args.snapshot / 'manifest.json').read_text())
    expected = {}
    index = args.snapshot / 'files.jsonl.gz'
    if index.exists():
        stream = gzip.open(index, 'rt', encoding='utf-8')
    else:
        stream = (args.snapshot / 'files.jsonl').open(encoding='utf-8')
    with stream:
        for line in stream:
            row = json.loads(line)
            expected[row['path']] = row
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    verified = 0
    for archive in manifest['archives']:
        if args.source and archive['source'] != args.source:
            continue
        pieces = []
        for part in archive['parts']:
            path = (args.snapshot / part['path']).resolve()
            if not path.is_relative_to(args.snapshot.resolve()):
                raise ValueError('Archive part escapes snapshot directory')
            content = path.read_bytes()
            if len(content) != part['bytes'] or hashlib.sha256(content).hexdigest() != part['sha256']:
                raise ValueError('Archive part checksum mismatch: ' + part['path'])
            pieces.append(content)
        with gzip.GzipFile(fileobj=io.BytesIO(b''.join(pieces))) as zipped:
            with tarfile.open(fileobj=zipped, mode='r|') as stream:
                count = 0
                for entry in stream:
                    path = PurePosixPath(entry.name)
                    if not entry.isfile() or path.is_absolute() or '..' in path.parts:
                        raise ValueError('Unsafe archive entry: ' + entry.name)
                    row = expected[entry.name]
                    content = stream.extractfile(entry).read()
                    if len(content) != row['export_bytes'] or hashlib.sha256(content).hexdigest() != row['export_sha256']:
                        raise ValueError('Exported file checksum mismatch: ' + entry.name)
                    if args.output:
                        target = args.output.joinpath(*path.parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with target.open('xb') as output:
                            output.write(content)
                    count += 1
                if count != archive['files']:
                    raise ValueError('Archive file count mismatch')
                verified += count
        print(json.dumps({'source': archive['source'], 'group': archive['group'], 'verified_files': count}), flush=True)
    print(json.dumps({'verified_files': verified, 'restored': args.output is not None}), flush=True)


if __name__ == '__main__':
    main()
