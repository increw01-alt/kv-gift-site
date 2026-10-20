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
        payload = json.loads(call.call_args.args[0].data)
        self.assertEqual(payload['n'],1)
        self.assertIn('선물용 상품권 선택',payload['prompt'])
        self.assertIn(example()['summary'],payload['prompt'])
        self.assertEqual(payload['output_format'],'png')

    def test_image_failure_never_renders_or_pushes(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.dict(os.environ, {'RUNNER_TEMP': temp, 'GITHUB_STEP_SUMMARY': ''}), \
             patch.object(runner,'run',side_effect=['[]','']) as command, \
             patch.object(runner,'pick_topic',return_value='topic'), \
             patch.object(runner,'generate',return_value=example()), \
             patch.object(runner,'generate_banner',side_effect=RuntimeError('image unavailable')), \
             patch.object(runner,'render') as render:
            with self.assertRaises(RuntimeError): runner.main()
            render.assert_not_called()
            self.assertEqual(command.call_count,2)

    def test_pending_review_does_not_call_either_api(self):
        with patch.object(runner,'run',return_value='[{"headRefName":"auto/board-test","url":"test"}]'), \
             patch.object(runner,'generate') as text_api, patch.object(runner,'generate_banner') as image_api:
            runner.main()
            text_api.assert_not_called()
            image_api.assert_not_called()
