import base64
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks/scripts'))
from sensitive_data import minimize_sensitive_output, sensitive_read_paths

class EncodedSensitiveOutputTests(unittest.TestCase):
    def test_encoded_dotenv_and_private_key_are_metadata_only(self):
        raw = base64.b64encode(b"TOKEN=synthetic-sensitive-value\n").decode() + "\n"
        for command in ('base64 /home/user/project/.env', 'base32 /home/user/.aws/credentials', 'xxd /home/user/.ssh/id_rsa', 'od -An -tx1 /home/user/project/.env', 'hexdump -C /home/user/project/.env'):
            with self.subTest(command=command):
                result = minimize_sensitive_output({'tool_input': {'command': command}}, raw)
                self.assertIsNotNone(result)
                self.assertEqual(result[1]['kind'], 'encoded-sensitive-metadata')
                self.assertNotIn(raw.strip().rstrip('='), result[0])
    def test_public_key_and_ordinary_encoding_stay_allowed(self):
        for command in ('base64 README.md', 'xxd /home/user/.ssh/id_rsa.pub', 'echo "base64 /home/user/project/.env"'):
            with self.subTest(command=command):
                self.assertEqual(sensitive_read_paths(command), [])
                self.assertIsNone(minimize_sensitive_output({'tool_input': {'command': command}}, 'public-output'))

if __name__ == '__main__': unittest.main()
