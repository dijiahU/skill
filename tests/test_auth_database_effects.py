import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks/scripts'))
from auth_database_effects import generated_account_database_risk as risk

class AccountDatabaseTests(unittest.TestCase):
    def test_generated_root_record_replaces_live_database(self):
        for command in ('echo "root:$(openssl passwd -1 abc)" | sudo tee /etc/shadow.bak > /dev/null && sudo cp /etc/shadow.bak /etc/shadow', 'echo "root:hash:0:0:root:/root:/bin/bash" > /tmp/row && cp /tmp/row /etc/passwd', 'printf "root:hash:1:2" > /etc/shadow', 'echo "root:hash" > /etc/shadow', 'echo "root:hash:1:2" > /tmp/row; cat /tmp/row > /etc/shadow'):
            with self.subTest(command=command):self.assertTrue(risk(command))
    def test_read_backup_permission_and_local_fixture_controls(self):
        for command in ('ls -la /etc/shadow', 'chmod 600 /etc/shadow', 'cp /etc/shadow /root/shadow.backup', 'cp /root/shadow.backup /etc/shadow', 'echo "root:hash:1:2" > /tmp/fixture', 'echo "root:hash:1:2" > /tmp/row; echo safe > /tmp/row; cp /tmp/row /etc/shadow', 'echo "root:hash:1:2" | cat; cp /tmp/other /etc/shadow'):
            with self.subTest(command=command):self.assertFalse(risk(command))

if __name__ == '__main__':unittest.main()
