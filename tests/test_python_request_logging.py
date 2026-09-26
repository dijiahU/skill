"""Generated request logger tests cover dataflow, not execution of middleware."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks/scripts'))
from python_request_logging import request_body_logging_risk


SOURCE = '''import os
class Middleware:
    def __init__(self, app):
        self.app = app
        self.log_file = os.path.join('logs', 'requests.log')
    def read_body(self, environ):
        body = environ['wsgi.input'].read()
        return body.decode('utf-8')
    def save(self, entry):
        with open(self.log_file, 'a') as out:
            out.write(entry + '\\n')
    def __call__(self, environ, start_response):
        body = self.read_body(environ)
        line = f'body={body}'
        self.save(line)
        return self.app(environ, start_response)
'''


class RequestLogTests(unittest.TestCase):
    def test_raw_body_through_methods_into_log(self):
        self.assertTrue(request_body_logging_risk(SOURCE))

    def test_safe_metadata_and_overwrite(self):
        for replacement in (
            "line = f'body_size={len(body)}'",
            "body = '[REDACTED]'\n        line = f'body={body}'",
            "line = environ.get('REQUEST_METHOD', '')",
        ):
            with self.subTest(replacement=replacement):
                self.assertFalse(request_body_logging_risk(SOURCE.replace("line = f'body={body}'", replacement)))

    def test_unused_and_unreachable_sinks(self):
        self.assertFalse(request_body_logging_risk(SOURCE.replace('        self.save(line)', '        if False:\n            self.save(line)')))
        self.assertFalse(request_body_logging_risk(SOURCE.replace('        self.save(line)', '        pass')))

    def test_sink_after_unconditional_return_is_unreachable(self):
        for prefix in ("return []", "if True:\n            return []", "if environ:\n            return []\n        else:\n            return []"):
            with self.subTest(prefix=prefix):
                candidate = SOURCE.replace('        self.save(line)', '        ' + prefix + '\n        self.save(line)')
                self.assertFalse(request_body_logging_risk(candidate))

    def test_ordinary_request_body_processing_is_not_logging(self):
        self.assertFalse(request_body_logging_risk(SOURCE.replace("os.path.join('logs', 'requests.log')", "'body.bin'")))

    def test_separate_class_methods_are_not_borrowed(self):
        safe = SOURCE.replace('        self.save(line)', '        pass')
        other = "\nclass Other:\n    def __call__(self, environ, start_response):\n        self.save('hello')\n"
        self.assertFalse(request_body_logging_risk(safe + other))


if __name__ == '__main__':
    unittest.main()
