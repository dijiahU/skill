"""Exercise Docker argument construction without touching Docker resources."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PATH=Path('/srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100/bin/docker')
loader=importlib.machinery.SourceFileLoader('qwen_guard',str(PATH))
spec=importlib.util.spec_from_loader(loader.name,loader)
guard=importlib.util.module_from_spec(spec);loader.exec_module(guard)

class ScopeTests(unittest.TestCase):
    def build(self,stage):
        captured=[]
        def bounded(args,**kwargs):captured.extend(args);return 0
        argv=['docker','run','-d','--name','skilldistill-oas-agent-unit-test',guard.IMAGE]
        with patch.object(sys,'argv',argv),patch.dict(os.environ,{'OAS_STAGE':stage,'LOCAL_HOST_IP':'private-host-8acf37a3a61d.invalid','HTTPS_PROXY':'http://secret:password@example.invalid:8888'}),patch.object(guard,'approved'),patch.object(guard,'inspect',return_value={'Id':guard.DIGEST}),patch.object(guard.socket,'gethostbyname',return_value='private-host-c2e41cada390.invalid'),patch.object(guard.runpy,'run_path',return_value={'run_bounded':bounded}):
            with self.assertRaises(SystemExit) as exc:guard.main()
            self.assertEqual(exc.exception.code,0)
        return captured
    def test_only_named_qwen_repair_uses_fixed_proxy(self):
        args=self.build('skills100-qwen-healthfix-20260913-r1-egressfix-smoke')
        self.assertIn('HTTPS_PROXY=http://private-host-fb6337b4cc5a.invalid:7899',args)
        self.assertFalse(any('secret:password' in a for a in args))
        bypass=next(a for a in args if a.startswith('NO_PROXY='))
        self.assertIn('private-host-8acf37a3a61d.invalid',bypass);self.assertIn('private-host-c2e41cada390.invalid',bypass)
    def test_other_stages_do_not_receive_proxy(self):
        for stage in ['skills100-qwen-repair4-w8','skills100-glm5-healthfix-20260913-r1-smoke']:
            self.assertFalse(any(a.startswith('HTTPS_PROXY=') for a in self.build(stage)))

if __name__=='__main__':unittest.main()
