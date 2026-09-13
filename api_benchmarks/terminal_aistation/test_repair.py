import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
import json
import ipaddress
from dockerfile_transport import render
import network_pool


class RepairTests(unittest.TestCase):
    def test_heredoc_and_multistage(self):
        source="FROM python:3.13-slim AS builder\nRUN python3 - <<'PY'\nfrom pathlib import Path\nprint('apt-get install curl')\nPY\nFROM builder\nCOPY --from=builder /app /app\n"
        refs=[]
        output=render(source,lambda ref:refs.append(ref) or 'local:base')
        self.assertEqual(refs,['python:3.13-slim'])
        self.assertIn("from pathlib import Path\nprint('apt-get install curl')",output)
        self.assertIn('FROM builder\n',output)

    def test_entire_pinned_dataset_parses_without_fake_import_images(self):
        root=Path('/srv/benchmark/skills/datasets/terminal-bench-formal-83c7a617-r2')
        refs=[]
        for path in root.rglob('Dockerfile'):
            render(path.read_text(),lambda ref:refs.append(ref) or ref)
        self.assertNotIn('pathlib',refs)
        self.assertNotIn('collections',refs)
        self.assertGreater(len(refs),100)

    def test_curl_package_is_not_rewritten_as_command(self):
        source='FROM python:3.12\nRUN apt-get install -y curl git && curl -f https://example.com\n'
        output=render(source,lambda r:r)
        self.assertIn('install -y curl git && curl --retry',output)
        self.assertNotIn('install -y curl --retry',output)

    def test_small_subnets_skip_existing_and_stay_unique(self):
        root=Path(tempfile.mkdtemp(prefix='tb-subnet-test-',dir='/srv/benchmark/skills/cache'))
        (root/'host-routes.txt').write_text('Iface Destination Gateway Flags RefCnt Use Metric Mask\n')
        occupied=[{'IPAM':{'Config':[{'Subnet':'198.18.0.0/28'}]}}]
        def command(argv,**kwargs):
            return 'existing\n' if argv[2]=='ls' else json.dumps(occupied)
        with patch.object(network_pool,'ROOT',root),patch.object(network_pool.subprocess,'check_output',command):
            assigned=[network_pool.reserve('case-'+str(i)) for i in range(40)]
            self.assertEqual(network_pool.reserve('case-0'),assigned[0])
        self.assertEqual(len(set(assigned)),40)
        self.assertNotIn('198.18.0.0/28',assigned)
        self.assertTrue(all(ipaddress.ip_network(n).prefixlen==28 for n in assigned))


if __name__=='__main__':unittest.main()
