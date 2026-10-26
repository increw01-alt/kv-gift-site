import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_drafts import validate, ROOT
from board_editor import edit_article
from board_originality import validate_plan, preflight
from board_planner import planning_material
from verify_board_publication import reconcile_pending
from test_board_drafts import fixture, example, DAY
from test_board_sources import plan


class RecoveryTests(unittest.TestCase):
    def test_related_url_variants_resolve_only_to_existing_whitelist(self):
        related = [{'path': '/board/gc_tip/35'}]
        value = plan()
        value['related_paths'] = ['https://kv-gift.co.kr/board/gc_tip/35.html', '/board/gc_tip/35/']
        self.assertEqual(validate_plan(value, related)['related_paths'], ['/board/gc_tip/35'])
        for path in ['/board/gc_tip/9999', 'https://evil.example/board/gc_tip/35',
                     'https://kv-gift.co.kr/board/gc_tip/35?target=evil', '//evil.example/board/gc_tip/35']:
            value = plan(); value['related_paths'] = [path]
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_plan(value, related)

    def test_api_link_choices_are_bounded_to_actual_existing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            with patch('board_editor.ask_json', return_value=plan()) as api:
                preflight('purchase', '주문 내용과 실제 상품 표시를 비교하는 방법', example(), 'review', lambda *x: None, root)
            payload = json.loads(api.call_args.args[1][0]['text'])
            schema = api.call_args.args[2]['properties']['related_paths']
            self.assertEqual(schema['items']['enum'], payload['allowed_related_paths'])
            for path in schema['items']['enum']:
                self.assertTrue((root/(path.lstrip('/')+'.html')).is_file())

    def test_draft_can_be_edited_but_final_restricted_word_is_still_blocked(self):
        draft = example(); draft['sections'][0]['body'] += ' 공식 인증이라는 말을 그대로 믿지 마세요.'
        validate(draft, check_content=False)
        with self.assertRaises(ValueError): validate(draft)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            with patch('board_editor.ask_json', return_value=example()) as api:
                edit_article('purchase', '판매 상품의 안내 범위를 확인하는 방법', draft, None, 'model', lambda *x: None, root)
            sent = json.loads(api.call_args.args[1][0]['text'])
            self.assertIn('공식 인증', sent['draft_validation_issues_to_correct'][0])
            with patch('board_editor.ask_json', return_value=draft), self.assertRaises(ValueError):
                edit_article('purchase', '판매 상품의 안내 범위를 확인하는 방법', draft, None, 'model', lambda *x: None, root)

    def test_attempted_reader_task_is_excluded_even_without_source_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            tasks = json.loads((ROOT/'tools/board_reader_tasks.json').read_text(encoding='utf-8'))
            (root/'tools/board_reader_tasks.json').write_text(json.dumps(tasks), encoding='utf-8')
            target = next(t for t in tasks if t['board'] == 'sense')
            folder = root/'data/editorial_runs'/DAY.isoformat(); folder.mkdir(parents=True)
            (folder/'10.json').write_text(json.dumps({'status':'held', 'api_usage':{'context':{
                'rejected_topic_plans':[{'task_id':target['id'], 'source_id':'',
                    'reader_problem':'이미 검토한 독자의 구체적인 문제', 'outline':['기존 해결 순서']}]}}}), encoding='utf-8')
            material, _ = planning_material(root, None, 'sense', DAY)
            self.assertNotIn(target['id'], [t['id'] for t in material['unused_reader_tasks']])
            self.assertTrue(all(t['board']=='sense' for t in material['unused_reader_tasks']))
            self.assertEqual(material['covered_reader_problems'][0]['status'], 'held')

    def test_reconciliation_updates_yesterday_proof_without_changing_costs_or_today(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            day = DAY + dt.timedelta(days=1)
            folder = root/'data/editorial_runs'/DAY.isoformat(); folder.mkdir(parents=True)
            banner = root/f'board-img/purchase/guide-{DAY}-10.png'; banner.parent.mkdir(parents=True); banner.write_bytes(b'original')
            record = {'run_id':'10','board':'purchase','date_kst':DAY.isoformat(),'status':'published',
                      'url':'https://kv-gift.co.kr/board/purchase/100',
                      'api_usage':{'estimated_total_usd':.12, 'known_subtotal_usd':.12}}
            ledger = folder/'10.json'; ledger.write_text(json.dumps(record),encoding='utf-8')
            fail = Mock(side_effect=RuntimeError('not deployed'))
            self.assertEqual(reconcile_pending(root, day, fail), [])
            self.assertNotIn('public_verified_at', json.loads(ledger.read_text(encoding='utf-8')))
            success = Mock()
            files = reconcile_pending(root, day, success, dt.datetime(2026,10,21,tzinfo=dt.timezone.utc))
            saved = json.loads(ledger.read_text(encoding='utf-8'))
            self.assertEqual(saved['api_usage'], record['api_usage'])
            self.assertEqual(saved['date_kst'], DAY.isoformat())
            self.assertTrue(saved['public_verified_at'])
            self.assertIn('data/editorial_archive.json', files)
            today = json.loads((root/'data/editorial_status.json').read_text(encoding='utf-8'))
            self.assertEqual(today['dateKst'], day.isoformat())
            self.assertEqual(today['published'], 0)
            self.assertEqual(reconcile_pending(root, day, success), [])
            self.assertEqual(success.call_count, 1)


if __name__ == '__main__': unittest.main()
