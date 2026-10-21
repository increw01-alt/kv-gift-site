import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_usage import UsageLog, estimate
import run_board_draft as runner
from test_board_drafts import example


class UsageTests(unittest.TestCase):
    def test_cached_text_and_image_costs(self):
        self.assertAlmostEqual(estimate('text', 'gpt-4.1-mini', {
            'input_tokens': 2000, 'output_tokens': 1000,
            'input_tokens_details': {'cached_tokens': 1000}}), .0021)
        self.assertAlmostEqual(estimate('image', 'gpt-image-2', {
            'input_tokens': 1000, 'output_tokens': 1400,
            'input_tokens_details': {'text_tokens': 800, 'image_tokens': 200}}), .0476)

    def test_unknown_is_not_zero(self):
        self.assertIsNone(estimate('text', 'new-model', {'input_tokens': 10, 'output_tokens': 10}))
        self.assertIsNone(estimate('image', 'gpt-image-2', {}))
        self.assertIsNone(estimate('image', 'gpt-image-2', {'input_tokens': 10, 'output_tokens': 10}))

    def test_review_cost_includes_cached_input_and_reasoning_output_tokens(self):
        self.assertAlmostEqual(estimate('review','gpt-5.4-mini',{
            'input_tokens':1000,'output_tokens':1000,
            'input_tokens_details':{'cached_tokens':200},
            'output_tokens_details':{'reasoning_tokens':800}}),.005115)

    def test_failure_keeps_text_cost_without_complete_total(self):
        with tempfile.TemporaryDirectory() as temp:
            def generated(topic, model, on_usage, **kwargs):
                on_usage('text', model, {'input_tokens': 1000, 'output_tokens': 1000})
                return example()
            with patch.dict('os.environ', {'RUNNER_TEMP': temp, 'GITHUB_STEP_SUMMARY': '', 'OPENAI_MODEL': 'gpt-4.1-mini'}), \
                 patch.object(runner, 'run', side_effect=['[]', '']), \
                 patch.object(runner, 'select_board', return_value=('purchase','topic')), \
                 patch.object(runner, 'generate', side_effect=generated), \
                 patch.object(runner, 'generate_banner', side_effect=RuntimeError('failed')), \
                 patch.object(runner, 'render') as render:
                with self.assertRaises(RuntimeError):
                    runner.main()
                render.assert_not_called()
            log = json.loads((Path(temp) / 'board-api-usage.json').read_text(encoding='utf-8'))
            self.assertEqual(log['status'], 'failed')
            self.assertEqual(log['known_subtotal_usd'], .002)
            self.assertIsNone(log['estimated_total_usd'])

    def test_success_record_contains_rates_and_raw_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            log = UsageLog(Path(temp) / 'usage.json')
            usage = {'input_tokens': 1000, 'output_tokens': 1000}
            log.record('text', 'gpt-4.1-mini', usage)
            log.save('completed')
            saved = json.loads(log.path.read_text(encoding='utf-8'))
            self.assertEqual(saved['records'][0]['usage'], usage)
            self.assertEqual(saved['estimated_total_usd'], .002)
            self.assertIn('price_checked_on', saved['records'][0])
