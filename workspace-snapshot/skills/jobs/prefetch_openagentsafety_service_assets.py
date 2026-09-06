"""Bounded, direct-only prefetch of cached OAS service-task attachments."""

import concurrent.futures
import json
import threading
from pathlib import Path

import requests
from datasets import load_dataset

from benchmarks.openagentsafety.run_infer import _asset_cache_path, _task_asset_urls


SELECTION = Path('/2024233123/skills/jobs/openagentsafety-services-137.txt')
REPORT = Path('/2024233123/skills/logs/openagentsafety-service-assets-20260905.json')
MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
budget_lock = threading.Lock()
received_bytes = 0


def fetch(url):
    global received_bytes
    path = _asset_cache_path(url)
    if path.is_file():
        return {'url': url, 'status': 'cached', 'bytes': path.stat().st_size}
    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.get(url, stream=True, timeout=(10, 30)) as response:
                response.raise_for_status()
                if int(response.headers.get('Content-Length', 0)) > MAX_FILE:
                    raise RuntimeError('attachment exceeds 2 MiB limit')
                chunks = []
                size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    with budget_lock:
                        received_bytes += len(chunk)
                        if received_bytes > MAX_TOTAL:
                            raise RuntimeError('download budget exceeds 16 MiB')
                    if size > MAX_FILE:
                        raise RuntimeError('attachment exceeds 2 MiB limit')
                    chunks.append(chunk)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Never replace an existing cache entry; a failed transfer is not cached.
        try:
            with path.open('xb') as output:
                output.write(b''.join(chunks))
        except FileExistsError:
            return {'url': url, 'status': 'cached', 'bytes': path.stat().st_size}
        return {'url': url, 'status': 'downloaded', 'bytes': size}
    except Exception as exc:
        return {'url': url, 'status': 'failed', 'error': str(exc)}


def main():
    ids = set(SELECTION.read_text().split())
    dataset = load_dataset('mgulavani/openagentsafety_full_updated_v3', split='train')
    urls = sorted({u for row in dataset if row['instance_id'] in ids
                   for u in _task_asset_urls(row)})
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for result in pool.map(fetch, urls):
            results.append(result)
            if result['status'] == 'failed' or len(results) % 25 == 0:
                print(json.dumps({'done': len(results), 'total': len(urls),
                                  'received_bytes': received_bytes,
                                  'last': result if result['status'] == 'failed'
                                  else result['status']}), flush=True)
    counts = {status: sum(r['status'] == status for r in results)
              for status in ('cached', 'downloaded', 'failed')}
    report = {'counts': counts, 'received_bytes': received_bytes, 'assets': results}
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'counts': counts, 'received_bytes': received_bytes,
                      'report': str(REPORT)}), flush=True)
    return bool(counts['failed'])


if __name__ == '__main__':
    raise SystemExit(main())
