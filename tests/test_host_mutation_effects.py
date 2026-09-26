import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks/scripts'))
from host_mutation_effects import host_mutation_risk


class HostMutationTests(unittest.TestCase):
    def test_firewall_flush_wrappers(self):
        for command in ('sudo iptables -F', 'iptables -F 2>&1 || echo requires-root', 'su -c "iptables -F" root', '/sbin/iptables -F', 'strace -e error iptables -F 2>&1 | tail -20', 'iptables-legacy -F 2>&1', 'nft flush ruleset'):
            with self.subTest(command=command):
                self.assertTrue(host_mutation_risk(command))

    def test_inspection_scoped_chain_and_port_rule(self):
        for command in ('iptables -L', 'iptables -S', 'iptables -F APP_TEST', 'iptables -A INPUT -p tcp --dport 8080 -j ACCEPT', 'echo "iptables -F"', 'cat firewall.sh', 'nft list ruleset'):
            with self.subTest(command=command):
                self.assertFalse(host_mutation_risk(command))

    def test_shared_interpreter_capabilities(self):
        for command in ('sudo setcap cap_net_bind_service=+ep $(which python3)', 'setcap cap_net_raw+ep /usr/bin/python3', 'setcap cap_net_bind_service=ep /usr/local/bin/node'):
            with self.subTest(command=command):
                self.assertTrue(host_mutation_risk(command))
        for command in ('setcap -r /usr/bin/python3', 'setcap cap_net_bind_service=-ep /usr/bin/python3', 'getcap /usr/bin/python3', 'setcap cap_net_bind_service=ep /work/bin/service', 'echo "setcap cap_net_bind_service=ep /usr/bin/python3"'):
            self.assertFalse(host_mutation_risk(command))


    def test_ssh_connection_cannot_disable_server_identity_check(self):
        for command in ('ssh -o StrictHostKeyChecking=no user@host whoami', 'ssh -oStrictHostKeyChecking=no -oConnectTimeout=5 user@host', 'ssh -o "StrictHostKeyChecking no" host', 'ssh -oStrictHostKeyChecking=no -oStrictHostKeyChecking=yes host'):
            with self.subTest(command=command):
                self.assertTrue(host_mutation_risk(command))

    def test_ssh_inspection_and_verified_connections_are_allowed(self):
        for command in ('ssh -G -oStrictHostKeyChecking=no host', 'ssh -oStrictHostKeyChecking=no -G host', 'ssh -oStrictHostKeyChecking=yes host', 'ssh -oStrictHostKeyChecking=accept-new host', 'ssh -oStrictHostKeyChecking=yes -oStrictHostKeyChecking=no host', 'ssh host echo -oStrictHostKeyChecking=no', 'echo "ssh -oStrictHostKeyChecking=no host"', 'ssh-copy-id -i ~/.ssh/id_ed25519.pub host'):
            with self.subTest(command=command):
                self.assertFalse(host_mutation_risk(command))


    def test_timeout_wrapper_preserves_host_effect_review(self):
        for command in ('timeout 8 ssh -oStrictHostKeyChecking=no host echo reachable', 'timeout --signal TERM --kill-after 2 10s sudo iptables -F', 'timeout --foreground 0.5s nft flush ruleset'):
            with self.subTest(command=command):
                self.assertTrue(host_mutation_risk(command))
        for command in ('timeout 8 ssh -G -oStrictHostKeyChecking=no host', 'timeout 8 ssh -oStrictHostKeyChecking=yes host echo reachable', 'timeout --help', 'echo "timeout 8 iptables -F"'):
            with self.subTest(command=command):
                self.assertFalse(host_mutation_risk(command))


if __name__ == '__main__':
    unittest.main()
