import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_status import build_status


class StatusTests(unittest.TestCase):
    def test_verified_is_separate_from_main_and_unknown_cost_is_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            day = dt.date(2026, 10, 21)
            folder = root/'data/editorial_runs'/day.isoformat()
            folder.mkdir(parents=True)
            records = [
                {'run_id': '1', 'status': 'published', 'public_verified_at': '2026-10-21T01:00:00Z', 'api_usage': {'estimated_total_usd': .07}},
                {'run_id': '2', 'status': 'published', 'api_usage': {'estimated_total_usd': .08}},
                {'run_id': '3', 'status': 'held', 'api_usage': {'estimated_total_usd': .06}},
                {'run_id': '4', 'status': 'generating', 'api_usage': {'estimated_total_usd': 0}},
            ]
            for item in records:
                (folder/(item['run_id']+'.json')).write_text(json.dumps(item), encoding='utf-8')
            result = build_status(root, day)
            self.assertEqual((result['published'], result['verified'], result['attempts'], result['held']), (2, 1, 4, 1))
            self.assertIsNone(result['estimatedTotalUsd'])
            self.assertEqual(result['knownSubtotalUsd'], .21)
            self.assertIsNone(result['records'][-1]['estimatedUsd'])
            tomorrow = build_status(root, day+dt.timedelta(days=1))
            self.assertEqual((tomorrow['published'], tomorrow['attempts']), (0, 0))

    def test_partial_failed_usage_counts_without_claiming_complete_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            day = dt.date(2026, 10, 21)
            folder = root/'data/editorial_runs'/day.isoformat()
            folder.mkdir(parents=True)
            records = [
                {'run_id': '1', 'status': 'published', 'api_usage': {'estimated_total_usd': .07}},
                {'run_id': '2', 'status': 'error', 'api_usage': {'known_subtotal_usd': .001, 'estimated_total_usd': None}},
                {'run_id': '3', 'status': 'generating', 'api_usage': {'known_subtotal_usd': .002, 'estimated_total_usd': None}},
                {'run_id': '4', 'status': 'error', 'api_usage': {}},
            ]
            for item in records:
                (folder/(item['run_id']+'.json')).write_text(json.dumps(item), encoding='utf-8')
            result = build_status(root, day)
            self.assertEqual(result['knownSubtotalUsd'], .073)
            self.assertIsNone(result['estimatedTotalUsd'])
            self.assertEqual(result['records'][1]['knownSubtotalUsd'], .001)
            self.assertIsNone(result['records'][1]['estimatedUsd'])
            self.assertIsNone(result['records'][3]['knownSubtotalUsd'])
