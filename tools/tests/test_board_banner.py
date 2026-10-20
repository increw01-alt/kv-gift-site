import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_banner as banner
import run_board_draft as runner
from test_board_drafts import example


class BannerTests(unittest.TestCase):
    def test_valid_image_and_corruption(self):
        raw = (runner.ROOT/'board-img/purchase/buying-checklist-20261019.png').read_bytes()
        self.assertEqual(banner.validate_png(raw),(1536,1024))
        for invalid in (b'not an image',raw[:-20],raw[:100]+b'wrong'+raw[105:]):
            with self.assertRaises(ValueError): banner.validate_png(invalid)

    @patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','OPENAI_IMAGE_MODEL':'gpt-image-2','OPENAI_IMAGE_QUALITY':'medium'})
    def test_one_image_request_and_content(self):
        raw = (runner.ROOT/'board-img/purchase/buying-checklist-20261019.png').read_bytes()
        reply = io.BytesIO(json.dumps({'data':[{'b64_json':base64.b64encode(raw).decode()}]}).encode())
        with patch.object(banner.urllib.request,'urlopen',return_value=reply) as call:
            result, info = banner.generate_banner('선물용 상품권 선택',example())
        self.assertEqual(result,raw)
        self.assertEqual(call.call_count,1)
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/images/edits')
        payload = json.loads(request.data)
        self.assertEqual(payload['n'],1)
        self.assertIn('선물용 상품권 선택',payload['prompt'])
        self.assertIn(example()['summary'],payload['prompt'])
        self.assertEqual(payload['output_format'],'png')
        self.assertNotIn('input_fidelity', payload)
        self.assertEqual(len(payload['images']), 2)
        for item, name in zip(payload['images'], banner.REFERENCE_FILES):
            prefix, encoded = item['image_url'].split(',', 1)
            self.assertEqual(prefix, 'data:image/png;base64')
            self.assertEqual(base64.b64decode(encoded), (banner.REFERENCE_DIR/name).read_bytes())
        self.assertEqual(info['references'], list(banner.REFERENCE_FILES))

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'})
    def test_missing_references_never_calls_api(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(banner, 'REFERENCE_DIR', Path(temp)), \
             patch.object(banner.urllib.request, 'urlopen') as call:
            with self.assertRaises(FileNotFoundError):
                banner.generate_banner('topic', example())
            call.assert_not_called()

    def test_image_failure_never_renders_or_pushes(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.dict(os.environ, {'RUNNER_TEMP': temp, 'GITHUB_STEP_SUMMARY': ''}), \
             patch.object(runner,'run',side_effect=['[]','']) as command, \
             patch.object(runner,'select_board',return_value=('purchase','topic')), \
             patch.object(runner,'generate',return_value=example()), \
             patch.object(runner,'generate_banner',side_effect=RuntimeError('image unavailable')), \
             patch.object(runner,'render') as render:
            with self.assertRaises(RuntimeError): runner.main()
            render.assert_not_called()
            self.assertEqual(command.call_count,2)

    def test_pending_review_does_not_call_either_api(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': str(Path(temp)/'summary.md')}), \
             patch.object(runner,'run',return_value='[{"headRefName":"auto/board-test","url":"https://example.test/review/3"}]'), \
             patch.object(runner,'generate') as text_api, patch.object(runner,'generate_banner') as image_api:
            runner.main()
            text_api.assert_not_called()
            image_api.assert_not_called()
            summary = (Path(temp)/'summary.md').read_text(encoding='utf-8')
            self.assertIn('https://example.test/review/3', summary)
            self.assertIn('API를 호출하지 않았습니다', summary)

    def test_manual_preview_never_runs_git_or_changes_site(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.dict(os.environ, {'RUNNER_TEMP':temp,'GITHUB_STEP_SUMMARY':'',
                                    'PREVIEW_ONLY':'true','GITHUB_EVENT_NAME':'workflow_dispatch'}), \
             patch.object(runner,'run') as command, \
             patch.object(runner,'select_board',return_value=('gc_tip','topic')), \
             patch.object(runner,'generate',return_value=example()), \
             patch.object(runner,'generate_banner',return_value=(b'image',{})), \
             patch.object(runner,'save_preview',side_effect=lambda folder,*args: folder.mkdir()), \
             patch.object(runner,'render') as render:
            runner.main()
            command.assert_not_called()
            render.assert_not_called()
            self.assertTrue((Path(temp)/'board-review/board-api-usage.json').exists())

    def test_no_topic_does_not_call_apis(self):
        with patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':'','PREVIEW_ONLY':'false'}), \
             patch.object(runner,'run',return_value='[]'), \
             patch.object(runner,'select_board',side_effect=runner.NoTopic('주제 소진')), \
             patch.object(runner,'generate') as text_api, \
             patch.object(runner,'generate_banner') as image_api:
            runner.main()
            text_api.assert_not_called()
            image_api.assert_not_called()
