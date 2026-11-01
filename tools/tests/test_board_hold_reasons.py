"""Offline regression coverage: new codes, legacy ledgers, and every hold gate."""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_drafts import ROOT, KST, NoTopic, read_json
from board_editor import review_article, select_topic
from board_originality import preflight, validate_plan
from board_planner import PlanningHeld
from board_retry import novelty_hold, retry_state, retry_guard
from board_usage import UsageLog
import run_board_publish as publish
from test_board_drafts import fixture, example, DAY
from test_board_publish import approved, NOW
from test_board_sources import plan


class HoldReasonTests(unittest.TestCase):
    def last_body_hold(self):
        return read_json(ROOT/'data/editorial_runs/2026-11-01/41236644103.json')

    def test_last_real_body_hold_with_code_enters_cooldown_without_changing_original(self):
        record = self.last_body_hold()
        record['holdReason'] = 'body_duplicate'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root/'data/editorial_runs/2026-11-01/41236644103.json'
            publish.write_json(path, record)
            before = path.read_bytes()
            at = dt.datetime.fromisoformat(record['api_usage']['context']['attempt_started_at'])
            state = retry_state(root, at.date())
            self.assertEqual(state['consecutiveTopicHolds'], 1)
            self.assertEqual(state['cooldownMinutes'], 30)
            self.assertIsNotNone(retry_guard(root, at.date(), at+dt.timedelta(minutes=5)))
            self.assertEqual(path.read_bytes(), before)

    def test_new_code_overrides_issue_words_and_status_must_be_held(self):
        for code, expected in [('topic_duplicate', True), ('body_duplicate', True),
                               ('image_readability', False), ('other', False), ('unknown', False), (None, False)]:
            with self.subTest(code=code):
                record = {'status': 'held', 'holdReason': code, 'review': {'issues': ['中断']}}
                self.assertEqual(novelty_hold(record), expected)
                record['review']['issues'] = ['주제 사전 검수 보류: 중복 오류 문구']
                self.assertEqual(novelty_hold(record), expected)
                record['status'] = 'published'
                self.assertFalse(novelty_hold(record))

    def test_legacy_ledger_keeps_exact_previous_string_rules(self):
        for text, expected in [('중복', True), ('주제 사전 검수 보류', True), ('다른 독자 문제', True),
                               ('기존 본문과 같은 질문', True), ('크게 겹칩니다', False),
                               ('같은 문제', False), ('배너 오탈자', False)]:
            with self.subTest(text=text):
                self.assertEqual(novelty_hold({'status': 'held', 'review': {'issues': [text]}}), expected)
        self.assertFalse(novelty_hold(self.last_body_hold()))

    def test_image_typo_breaks_duplicate_streak_even_if_issue_says_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number, code in [(1, 'topic_duplicate'), (2, 'image_readability')]:
                publish.write_json(root/f'data/editorial_runs/{DAY}/{number}.json', {
                    'run_id': str(number), 'status': 'held', 'holdReason': code,
                    'scheduled_at': f'{DAY}T09:0{number}:00+09:00',
                    'review': {'issues': ['중복된 배너 글자의 오탈자']}})
            self.assertEqual(retry_state(root, DAY)['consecutiveTopicHolds'], 0)
            self.assertIsNone(retry_guard(root, DAY, dt.datetime.combine(DAY, dt.time(9, 3), tzinfo=KST)))

    def test_mixed_new_and_legacy_duplicate_streak_has_same_bounded_cooldown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number, code in [(1, None), (2, 'topic_duplicate'), (3, 'body_duplicate')]:
                record = {'run_id': str(number), 'status': 'held',
                          'scheduled_at': f'{DAY}T09:0{number}:00+09:00', 'review': {'issues': ['중복']}}
                if code:
                    record['holdReason'] = code
                publish.write_json(root/f'data/editorial_runs/{DAY}/{number}.json', record)
            state = retry_state(root, DAY)
            self.assertEqual((state['consecutiveTopicHolds'], state['cooldownMinutes']), (3, 120))

    def test_planning_exception_and_exhausted_news_have_different_codes(self):
        self.assertEqual(getattr(PlanningHeld('purchase', ['같은 문제입니다.']), 'hold_reason', None), 'topic_duplicate')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            publish.write_json(root/'tools/board_news_briefs.json', [])
            with self.assertRaises(NoTopic) as caught, patch('board_editor.ask_json') as api:
                select_topic('gc_word', DAY, 'model', lambda *a: None, root)
            self.assertEqual(getattr(caught.exception, 'hold_reason', None), 'other')
            api.assert_not_called()

    def test_local_body_overlap_exception_is_coded_before_paid_review(self):
        with patch('board_originality.reject_copy', return_value='/board/gc_tip/35'), \
             patch('board_editor.ask_json') as api, self.assertRaises(NoTopic) as caught:
            preflight('gc_tip', '서로 다른 결제 기록을 구분하는 방법', example(), 'model', lambda *a: None, ROOT)
        self.assertEqual(getattr(caught.exception, 'hold_reason', None), 'body_duplicate')
        api.assert_not_called()

    def test_preflight_structured_code_does_not_depend_on_issue_wording(self):
        for code, issue in [('body_duplicate', '크게 겹칩니다. 같은 문제를 해결합니다.'),
                            ('other', '확인되지 않은 조건을 단정했습니다.')]:
            value = {**plan(), 'unique': False, 'issues': [issue], 'holdReason': code}
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); fixture(root)
                with patch('board_originality.reject_copy', return_value=None), \
                     patch('board_originality.related_articles', return_value=[]), \
                     patch('board_editor.ask_json', return_value=value) as api, self.assertRaises(NoTopic) as caught:
                    preflight('gc_tip', '서로 다른 결제 기록을 구분하는 방법', example(), 'model', lambda *a: None, root)
                self.assertEqual(getattr(caught.exception, 'hold_reason', None), code)
                self.assertEqual(str(caught.exception), '본문 검수 보류: '+issue)
                self.assertIn('holdReason', api.call_args.args[2]['required'])

    def test_preflight_unknown_or_contradictory_codes_fail_closed(self):
        for unique, code in [(False, 'topic_duplicate'), (False, 'image_readability'), (False, None),
                             (True, 'body_duplicate'), (False, 'unknown')]:
            value = {**plan(), 'unique': unique, 'holdReason': code}
            with self.subTest(unique=unique, code=code), self.assertRaises(ValueError):
                validate_plan(value, [])

    def test_final_review_codes_use_failed_checks_and_preserve_issue_text(self):
        for failed, expected in [('not_duplicate', 'body_duplicate'), ('image_readable', 'image_readability'),
                                  ('board_fit', 'other')]:
            value = approved(); value['checks'][failed] = False
            value['issues'] = ['중복이라는 단어만으로 분류하지 않는 검수 문장']
            with self.subTest(failed=failed), patch('board_editor.ask_json', return_value=value), \
                 patch('board_editor.related_titles', return_value=[]), patch('board_editor.related_articles', return_value=[]):
                result = review_article('purchase', '선물을 선택하는 새로운 질문', example(), b'image', None, 'model', lambda *a: None)
            self.assertEqual(result.get('holdReason'), expected)
            self.assertEqual(result['issues'], value['issues'])

    def test_ledger_adds_root_code_preserves_review_and_nonheld_uses_null(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            usage = UsageLog(root/'usage.json', {}); usage.save('completed')
            for number, (status, code) in enumerate([('held', 'body_duplicate'), ('held', 'topic_duplicate'),
                                                    ('held', 'image_readability'), ('held', 'other'),
                                                    ('published', None), ('generating', None), ('error', None)]):
                review = {'approved': False, 'issues': ['크게 겹칩니다' if code == 'body_duplicate' else '사유 원문']}
                before = copy.deepcopy(review)
                _, record = publish.record_outcome(root, DAY, str(number), None, None, status, review, usage,
                                                   hold_reason=code)
                self.assertIn('holdReason', record)
                self.assertEqual(record['holdReason'], code)
                self.assertEqual(record['review'], before)
                self.assertEqual(review, before)

    def run_flow(self, root, output, *, planning_error=None, preflight_error=None, review=None,
                 stale_topic=False, stale_body=False, guard_reason=None):
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ID': '123456',
               'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'FOLLOW_SCHEDULE': 'false',
               'PREVIEW_ONLY': 'false', 'RUNNER_TEMP': str(output), 'GITHUB_STEP_SUMMARY': '', 'GITHUB_OUTPUT': ''}
        with patch.dict(os.environ, env), patch.object(publish, 'sync_main'), patch.object(publish, 'commit_files'), \
             patch.object(publish, 'guard', side_effect=[None, guard_reason]), \
             patch.object(publish, 'select_topic', side_effect=planning_error,
                          return_value=('purchase', '선물을 고르기 전에 정하는 새로운 질문', None)), \
             patch.object(publish, 'generate', return_value=example()), patch.object(publish, 'edit_article', return_value=example()), \
             patch.object(publish, 'preflight', side_effect=preflight_error, return_value=plan()), \
             patch.object(publish, 'generate_banner', return_value=(b'png', {})) as image, patch.object(publish, 'save_preview'), \
             patch.object(publish, 'review_article', return_value=review or approved()), \
             patch.object(publish, 'fresh_topic', return_value=not stale_topic), \
             patch.object(publish, 'reject_copy', return_value='/board/gc_tip/35' if stale_body else None), \
             patch.object(publish, 'render', side_effect=AssertionError('held articles must not render')):
            code = publish.main(root, lambda *a: '', NOW)
        return code, read_json(root/f'data/editorial_runs/{NOW.date()}/123456.json'), image

    def test_main_propagates_planning_hold_and_preserves_reason_without_image(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'site'; fixture(root)
            error = PlanningHeld('purchase', ['같은 문제를 다룹니다. 새 후보가 없습니다.'])
            code, record, image = self.run_flow(root, Path(temp)/'out', planning_error=error)
            self.assertEqual(code, 0)
            self.assertEqual(record['holdReason'], 'topic_duplicate')
            self.assertEqual(record['board'], 'purchase')
            self.assertEqual(record['review']['issues'], [str(error)])
            image.assert_not_called()

    def test_main_propagates_body_exception_into_ledger_without_image(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'site'; fixture(root)
            error = NoTopic('크게 겹칩니다. 같은 문제입니다.', hold_reason='body_duplicate')
            code, record, image = self.run_flow(root, Path(temp)/'out', preflight_error=error)
            self.assertEqual(code, 0)
            self.assertEqual(record['holdReason'], 'body_duplicate')
            self.assertEqual(record['review']['issues'], [str(error)])
            image.assert_not_called()

    def test_main_final_checks_and_time_guard_have_distinct_codes(self):
        for args, expected in [({'stale_topic': True}, 'topic_duplicate'), ({'stale_body': True}, 'body_duplicate'),
                               ({'guard_reason': '게시 가능 시간이 지났습니다.'}, 'other')]:
            with self.subTest(args=args), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)/'site'; fixture(root)
                _, record, _ = self.run_flow(root, Path(temp)/'out', **args)
                self.assertEqual(record.get('holdReason'), expected)

    def test_main_final_banner_typo_does_not_trigger_duplicate_cooldown(self):
        report = approved(); report['approved'] = False; report['checks']['image_readable'] = False
        report['issues'] = ['중복 배너 제목의 오탈자']
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'site'; fixture(root)
            _, record, _ = self.run_flow(root, Path(temp)/'out', review=report)
            self.assertEqual(record.get('holdReason'), 'image_readability')
            self.assertEqual(retry_state(root, NOW.date())['consecutiveTopicHolds'], 0)


if __name__ == '__main__':
    unittest.main()
