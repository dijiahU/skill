import os
import unittest
from unittest.mock import patch
from batch_docker import direct_download_env


class DirectDownloadTests(unittest.TestCase):
    def test_direct_mode_cannot_inherit_proxy(self):
        env = {key:'http://127.0.0.1:17892' for key in ('http_proxy','https_proxy','all_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')}
        env['PIP_INDEX_URL'] = 'https://pypi.tuna.tsinghua.edu.cn/simple'
        with patch.dict(os.environ, {'TERMINAL_BENCH_DIRECT_DOWNLOAD':'1'}):
            result = direct_download_env(env)
        self.assertFalse(any(key in result for key in env if 'proxy' in key.lower()))
        self.assertEqual(result['NO_PROXY'], '*')
        self.assertEqual(result['PIP_INDEX_URL'], env['PIP_INDEX_URL'])

    def test_normal_mode_preserves_environment(self):
        env = {'https_proxy':'http://example.test:8080'}
        with patch.dict(os.environ, {'TERMINAL_BENCH_DIRECT_DOWNLOAD':'0'}):
            self.assertEqual(direct_download_env(env), env)


if __name__ == '__main__':
    unittest.main()
