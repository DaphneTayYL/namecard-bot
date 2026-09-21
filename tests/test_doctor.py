import tempfile
import unittest
from pathlib import Path
from doctor import validate

class ConfigTests(unittest.TestCase):
    def config(self, **changes):
        return dict(TELEGRAM_TOKEN='123:token', ANTHROPIC_API_KEY='sk-ant-test', ALLOWED_USER_IDS='123', **changes)
    def test_preview_needs_no_destinations(self):
        self.assertEqual(validate(self.config()), [])
    def test_empty_required_values(self):
        self.assertEqual(len(validate({})), 3)
    def test_placeholders_and_bad_ids(self):
        c = self.config()
        c.update(TELEGRAM_TOKEN='123:your-token', ALLOWED_USER_IDS='123,abc')
        self.assertEqual(len(validate(c)), 2)
    def test_sheet_requires_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(validate(self.config(GOOGLE_SHEET_ID='sheet'), Path(temp)))
    def test_non_object_json_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'google-creds.json').write_text('[]')
            self.assertTrue(validate(self.config(GOOGLE_SHEET_ID='sheet'), Path(temp)))
    def test_multiple_ids(self):
        c = self.config()
        c['ALLOWED_USER_IDS'] = '123, 456'
        self.assertEqual(validate(c), [])

if __name__ == '__main__':
    unittest.main()
