import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

JOB=Path(__file__).resolve().parent
sys.path[:0]=[str(JOB/'adapter'),'/srv/benchmark/skills/jobs/eval-retry-20260913-r1/frozen/adapter']
from tb21_docker import TB21Docker, VerifierIntegrityError
from batch_docker import BatchDocker

class GuardTests(unittest.IsolatedAsyncioTestCase):
    def target(self):
        root=JOB/'test-artifacts';root.mkdir(exist_ok=True)
        path=Path(tempfile.mkdtemp(prefix='guard-',dir=root))
        obj=object.__new__(TB21Docker);obj.trial_paths=SimpleNamespace(verifier_dir=path)
        return obj,path

    async def test_verifier_download_failure_raises_despite_numeric_zero(self):
        obj,path=self.target()
        async def execute(**kwargs):
            (path/'reward.txt').write_text('0')
            (path/'test-stdout.txt').write_text('Failed to fetch pytest: DNS failure')
            return SimpleNamespace(return_code=0)
        with patch.object(BatchDocker,'exec',side_effect=execute):
            with self.assertRaises(VerifierIntegrityError):
                await obj.exec('(/tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1')

    async def test_real_zero_is_returned_and_stale_files_rejected(self):
        obj,path=self.target()
        async def execute(**kwargs):
            (path/'reward.txt').write_text('0')
            (path/'ctrf.json').write_text(json.dumps({'results':{'summary':{'tests':1,'passed':0,'failed':1},'tests':[{'status':'failed','raw_status':'call_failed'}]}}))
            return SimpleNamespace(return_code=0)
        with patch.object(BatchDocker,'exec',side_effect=execute) as call:
            await obj.exec('(/tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1')
            with self.assertRaises(VerifierIntegrityError):
                await obj.exec('(/tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1')
            self.assertEqual(call.call_count,1)

    async def test_task_command_and_chmod_not_treated_as_grading(self):
        obj,path=self.target()
        with patch.object(BatchDocker,'exec',new_callable=AsyncMock) as call:
            await obj.exec('ls /app')
            await obj.exec('chmod +x /tests/test.sh', user='root')
            self.assertEqual(call.call_count,2)

if __name__=='__main__':unittest.main()
