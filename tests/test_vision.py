import unittest
from unittest.mock import patch, Mock
import httpx
from doctor import validate, selected_provider
from vision import extract_namecard

class ProviderTests(unittest.TestCase):
    def test_openai_needs_no_claude_key(self):
        c = dict(TELEGRAM_TOKEN='123:token', OPENAI_API_KEY='test-key', ALLOWED_USER_IDS='123')
        self.assertEqual(selected_provider(c), 'openai')
        self.assertEqual(validate(c), [])
        c['VISION_PROVIDER'] = 'anthropic'
        self.assertTrue(any('ANTHROPIC_API_KEY' in x for x in validate(c)))
    def test_invalid_provider(self):
        self.assertTrue(any('VISION_PROVIDER' in x for x in validate({'VISION_PROVIDER':'invalid'})))
    @patch('vision.httpx.post')
    def test_openai_photo_and_result(self, post):
        post.return_value.json.return_value = {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"name":" Ada ","email":"ada@example.com"}'}]}]}
        result = extract_namecard(b'photo', provider='openai', api_key='test-key', model='gpt-4.1-mini')
        self.assertEqual(result['name'], 'Ada')
        self.assertEqual(result['phone'], '')
        request = post.call_args.kwargs['json']
        self.assertFalse(request['store'])
        self.assertEqual(request['input'][0]['content'][1]['image_url'], 'data:image/jpeg;base64,cGhvdG8=')
    @patch('vision.httpx.post')
    def test_openai_failure_propagates(self, post):
        post.return_value.raise_for_status.side_effect = httpx.HTTPError('Request failed')
        with self.assertRaises(httpx.HTTPError):
            extract_namecard(b'photo', provider='openai', api_key='test', model='gpt-4.1-mini')
    @patch('vision.httpx.post')
    def test_incomplete_response_rejected(self, post):
        post.return_value.json.return_value = {'status':'incomplete'}
        with self.assertRaises(ValueError):
            extract_namecard(b'photo', provider='openai', api_key='test', model='gpt-4.1-mini')
    @patch('vision.Anthropic')
    def test_claude_still_extracts(self, client):
        client.return_value.messages.create.return_value.content = [Mock(text='```json\n{"name":"Ada"}\n```')]
        result = extract_namecard(b'photo', provider='anthropic', api_key='test', model='claude-haiku-4-5-20251001')
        self.assertEqual(result['name'], 'Ada')
        self.assertEqual(client.return_value.messages.create.call_args.kwargs['messages'][0]['content'][0]['source']['data'], 'cGhvdG8=')
