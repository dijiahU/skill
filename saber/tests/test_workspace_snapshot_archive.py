import concurrent.futures
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from harness_adapters.workspace_snapshot_archive import archive_snapshot, restore_snapshot
from harness_adapters.codex_native_adapter import CodexNativeHarnessAdapter

class SnapshotArchiveTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='snapshot-archive-test-'))
        self.payload = {'schema_version':2, 'authoritative':True, 'snapshot_status':'ready',
                        'cwd':'/home/user/project', 'file_contents':{'/home/user/project/x':'synthetic-secret-α'},
                        'policy_file_contents':{'/home/user/project/x':'synthetic-secret-α'}, 'observation_index':1}

    def test_roundtrip_dedup_and_private_permissions(self):
        ref=archive_snapshot(self.root,self.payload)
        self.assertNotIn('synthetic-secret',json.dumps(ref))
        self.assertEqual(restore_snapshot(self.root,ref['manifest_sha256']),self.payload)
        self.assertEqual(archive_snapshot(self.root,self.payload),ref)
        self.assertEqual(len(list((self.root/'blobs').glob('*.gz'))),1)
        changed=dict(self.payload,file_contents={'/home/user/project/x':'updated'},observation_index=2)
        later=archive_snapshot(self.root,changed)
        self.assertEqual(restore_snapshot(self.root,later['manifest_sha256']),changed)
        self.assertEqual(restore_snapshot(self.root,ref['manifest_sha256']),self.payload)
        for p in self.root.rglob('*.gz'): self.assertEqual(p.stat().st_mode & 0o777,0o600)

    def test_concurrent_writers(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            refs=list(pool.map(lambda _:archive_snapshot(self.root,self.payload),range(24)))
        self.assertEqual(len({r['manifest_sha256'] for r in refs}),1)
        self.assertEqual(restore_snapshot(self.root,refs[0]['manifest_sha256']),self.payload)

    def test_corruption_and_invalid_digest(self):
        ref=archive_snapshot(self.root,self.payload)
        next((self.root/'blobs').glob('*.gz')).write_bytes(gzip.compress(b'changed'))
        with self.assertRaises(ValueError):restore_snapshot(self.root,ref['manifest_sha256'])
        with self.assertRaises(ValueError):archive_snapshot(self.root,self.payload)
        with self.assertRaises(ValueError):restore_snapshot(self.root,'../invalid')
        with self.assertRaises(ValueError):archive_snapshot(Path('relative'),self.payload)

    def test_real_observer_archives_state_and_policy(self):
        adapter=CodexNativeHarnessAdapter(skill_mode='safety-orchestrator');snapshot=self.root/'live.json'
        adapter._write_workspace_snapshot(snapshot,dict(self.payload,policy_initialized=True))
        class Runtime:
            def snapshot_workspace(self,cwd,paths):
                return {'complete':True,'file_contents':{'/home/user/project/x':'current-content'}}
        adapter._refresh_workspace_snapshot(Runtime(),'/home/user/project',{
            'SAFETY_ORCH_WORKSPACE_SNAPSHOT':str(snapshot),'SABER_WORKSPACE_SNAPSHOT_ARCHIVE':str(self.root/'archive')})
        meta=adapter.last_run_meta['workspace_observations'][-1];ref=meta['archive']
        self.assertEqual(restore_snapshot(Path(ref['root']),ref['manifest_sha256']),json.loads(snapshot.read_text()))
        self.assertNotIn('current-content',json.dumps(meta))

    def test_archive_failure_stops_observation(self):
        adapter=CodexNativeHarnessAdapter(skill_mode='safety-orchestrator')
        snapshot=self.root/'live.json'
        adapter._write_workspace_snapshot(snapshot,dict(self.payload,policy_initialized=True))
        blocked_root=self.root/'not-a-directory'
        blocked_root.write_text('existing test fixture')
        class Runtime:
            def snapshot_workspace(self,cwd,paths):
                return {'complete':True,'file_contents':{'/home/user/project/x':'current'}}
        with self.assertRaisesRegex(RuntimeError,'observation failed|observation|snapshot'):
            adapter._refresh_workspace_snapshot(Runtime(),'/home/user/project',{
                'SAFETY_ORCH_WORKSPACE_SNAPSHOT':str(snapshot),
                'SABER_WORKSPACE_SNAPSHOT_ARCHIVE':str(blocked_root)})
        self.assertEqual(blocked_root.read_text(),'existing test fixture')
        self.assertNotIn('archive',adapter.last_run_meta['workspace_observations'][-1])

if __name__=='__main__':unittest.main()
