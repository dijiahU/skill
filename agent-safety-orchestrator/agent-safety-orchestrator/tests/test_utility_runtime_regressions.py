import importlib.util, json, os, pathlib, sys, tempfile, threading, time, unittest
from unittest.mock import patch
BUNDLE=pathlib.Path(os.environ.get('REPAIR_TEST_BUNDLE', str(pathlib.Path(__file__).resolve().parents[1])))
os.environ['SAFETY_ORCH_STATUS_DIR']=tempfile.mkdtemp(prefix='tb21-repair-state-',dir='/tmp')
os.environ['SAFETY_ORCH_CACHE_DIR']=tempfile.mkdtemp(prefix='tb21-repair-cache-',dir='/tmp')
sys.path[:0]=[str(BUNDLE),str(BUNDLE/'hooks/scripts')]
from helpers import health_status, cache_snapshot
import matcher_pretool_generic as generic
spec=importlib.util.spec_from_file_location('repair_codex_hook', BUNDLE/'adapters/codex/codex_hook.py')
bridge=importlib.util.module_from_spec(spec);sys.modules[spec.name]=bridge;spec.loader.exec_module(bridge)
class RepairTests(unittest.TestCase):
    def test_registry_outage_is_actionable_not_helper_crash(self):
        with patch.object(generic,'_query_package_metadata',return_value=cache_snapshot.NETWORK_ERROR),patch.object(generic,'log_audit') as audit,patch.dict(os.environ,{'SAFETY_ORCH_ACCEPT_DEGRADED':'0'}):
            verdicts=generic._check_supply_chain({'tool_input':{'command':'pip install toml'}})
        text=json.dumps(verdicts)
        self.assertNotIn('helper failed',text)
        self.assertIn('cannot resolve version',text)
        self.assertNotIn('helper-error',str(audit.call_args_list))
        self.assertTrue(any(v.get('verdict')=='block' for v in verdicts),verdicts)
    def test_pinned_version_still_checked_during_registry_outage(self):
        with patch.object(generic,'_query_package_metadata',return_value=cache_snapshot.NETWORK_ERROR),patch.object(cache_snapshot,'query_osv',return_value=cache_snapshot.NETWORK_ERROR) as osv:
            verdicts=generic._check_supply_chain({'tool_input':{'command':'pip install toml==0.10.2'}})
        osv.assert_called_once_with([('PyPI','toml','0.10.2')])
        self.assertIn('CVE check cannot complete',json.dumps(verdicts))
    def test_dns_hang_cannot_block_health_startup(self):
        released=threading.Event()
        def blocked_dns(*args,**kwargs):
            released.wait(0.8)
            raise OSError('simulated unavailable DNS')
        start=time.monotonic()
        with patch.object(health_status.socket,'gethostbyname',side_effect=blocked_dns):
            ok,reason=health_status._ping('https://example.invalid',timeout=0.04)
        elapsed=time.monotonic()-start;released.set()
        self.assertFalse(ok)
        self.assertLess(elapsed,0.25)
    def test_shared_health_endpoints_are_probed_once(self):
        with patch.object(health_status,'_ping',return_value=(False,'offline')) as ping:
            banner=health_status.init_banner(str(BUNDLE/'atoms.json'))
        enabled={url for atom,url in health_status.NETWORK_ATOMS.items() if atom not in health_status.API_KEY_GATED or os.environ.get(health_status.API_KEY_GATED[atom])}
        self.assertEqual(ping.call_count,len(enabled))
        self.assertIn('degraded',banner)
    def test_real_recovery_diagnostics_allowed(self):
        for command in ['which qemu-system-x86_64','python3 --version','R --version 2>&1 | head -5','pip list | grep -i toml','ps aux | grep nginx | head -5','pip show numpy scipy']:
            with self.subTest(command=command):self.assertTrue(bridge._bash_recovery_profile(command,'/app')[0])
    def test_recovery_cannot_execute_code_or_mutate(self):
        for command in ['python3 -c "open(\"/app/x\",\"w\")"','pip install toml','pip --python ./evil list','which bash; touch /app/marker','ps aux > /app/out','R --version; rm -rf /app','which $(touch /app/x)','pip show --files toml','python3 script.py --version','which python3 & touch /app/x']:
            with self.subTest(command=command):self.assertFalse(bridge._bash_recovery_profile(command,'/app')[0])
if __name__=='__main__': unittest.main(verbosity=2)
