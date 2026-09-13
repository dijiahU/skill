import json
from pathlib import Path
import tempfile
import unittest

from api_benchmarks.analysis.export_results import Redactor


class RedactionTests(unittest.TestCase):
    def test_risk_task_names_are_not_credentials(self):
        text = '/results/risk-comparison-test__abc1234567/result.json'
        self.assertEqual(Redactor().text(text), text)

    def test_nested_credentials_are_redacted_without_changing_scores(self):
        secret = 'sk-' + 'synthetic' * 4
        value = {'reward': 0, 'total_tokens': 123, 'error': None,
                 'config': {'api_key': secret}, 'events': [{'content': 'Bearer ' + secret}]}
        redacted = Redactor().object(value)
        self.assertNotIn(secret, json.dumps(redacted))
        self.assertEqual(redacted['reward'], 0)
        self.assertEqual(redacted['total_tokens'], 123)
        self.assertIsNone(redacted['error'])
        self.assertEqual(value['config']['api_key'], secret)

    def test_local_credential_file_is_parsed_as_literal_data(self):
        directory = Path(tempfile.mkdtemp(prefix='export-redaction-test-'))
        path = directory / 'keys.env'
        value = 'literal-value-$(should-not-execute)'
        path.write_text('export EXAMPLE_API_KEY=' + repr(value) + '\n')
        redactor = Redactor([path])
        self.assertNotIn(value, redactor.text('request failed: ' + value))
        self.assertEqual(path.read_text(), 'export EXAMPLE_API_KEY=' + repr(value) + '\n')


if __name__ == '__main__':
    unittest.main()
