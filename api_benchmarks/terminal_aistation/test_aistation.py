import asyncio
import os
import unittest
from unittest.mock import patch

from aistation import AIStationDocker, host_path


class AdapterSafetyTests(unittest.TestCase):
    def test_tcp_maps_only_inside_persistent_root(self):
        with patch.dict(os.environ, {'DOCKER_HOST': 'tcp://node:2375',
                'POD_USER_ROOT': '/srv/benchmark', 'HOST_USER_ROOT': '/srv/benchmark-host'}):
            self.assertEqual(host_path('/srv/benchmark/skills/results'), '/srv/benchmark-host/skills/results')
            with self.assertRaises(ValueError):
                host_path('/srv/benchmark0/not-ours')
            with self.assertRaises(ValueError):
                host_path('/srv/benchmark/../etc/passwd')

    def test_unix_socket_preserves_path(self):
        with patch.dict(os.environ, {'DOCKER_HOST': 'unix:///var/run/docker.sock'}):
            self.assertEqual(host_path('/tmp/local'), '/tmp/local')

    def test_cleanup_never_reaches_docker(self):
        obj = object.__new__(AIStationDocker)
        obj._started_here = True
        for verb in ('down', 'stop', 'rm', 'kill', 'restart'):
            with self.assertRaises(RuntimeError):
                asyncio.run(obj._run_docker_compose_command([verb]))

    def test_upstream_stale_cleanup_is_skipped_only_before_start(self):
        obj = object.__new__(AIStationDocker)
        obj._started_here = False
        result = asyncio.run(obj._run_docker_compose_command(['down', '--remove-orphans']))
        self.assertEqual(result.return_code, 0)
        obj._started_here = True
        with self.assertRaises(RuntimeError):
            asyncio.run(obj._run_docker_compose_command(['down', '--remove-orphans']))


if __name__ == '__main__':
    unittest.main()
