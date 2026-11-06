import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_drafts import generate, NoTopic
from board_editor import edit_article, text_input
from board_hold_reasons import BODY_DUPLICATE
from board_originality import preflight
from board_planner import choose_plan
from board_profiles import PROFILES
from board_writing_brief import validate_brief
from planner_fixtures import writing_brief
from test_board_drafts import fixture, example, DAY
from test_board_planner import candidate
from test_board_publish import response


class WritingBriefTests(unittest.TestCase):
    def test_bad_or_invented_implementation_cannot_approve_planning(self):
        valid = writing_brief(['/board/purchase/1'])
        bad = [None, {}, {**valid, 'compared_paths': []},
               {**valid, 'compared_paths': ['/board/purchase/999']},
               {**valid, 'section_actions': valid['section_actions'][:2]},
               {**valid, 'section_actions': [valid['section_actions'][0]] * 3},
               {**valid, 'example': '가격이 1000원이라고 가정하고 계산하는 가상의 예시입니다.'}]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_brief(item, {'/board/purchase/1'}, True)
        self.assertEqual(validate_brief(valid, {'/board/purchase/1'}, True), valid)
        self.assertIsNone(validate_brief(None, set(), False))
        with self.assertRaises(ValueError):
            validate_brief(valid, {'/board/purchase/1'}, False)

    def test_planner_missing_brief_fails_before_any_draft_or_extra_request(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            api = Mock(side_effect=[{'candidates': [candidate('공동 선물 준비자의 의견을 조율하는 방법', '')]},
                {'selected_index': 0, 'reason': '기존 글과 다른 결정을 설명합니다.', 'rejections': [], 'rejected_indices': []}])
            with self.assertRaises(ValueError):
                choose_plan('purchase', PROFILES['purchase'], None, [], DAY, root, 'draft', 'review',
                            api, text_input, Mock(), lambda t: True)
            self.assertEqual(api.call_count, 2)

    def test_early_review_reads_twelve_bodies_and_carries_approved_implementation(self):
        rows = [{'path': f'/board/purchase/{i}', 'title': f'공동 선물을 준비하는 다른 기존 글 {i}',
                 'body': '기존 운영팀 글에서 이미 설명한 판단과 실제 해결 순서입니다. ' * 90} for i in range(15)]
        rows.append({'path': '/board/free/100', 'title': '예전 이용자 글 제목', 'body': ''})
        calls = []
        expected = {}
        def ask(instructions, content, schema, name, *args):
            calls.append(name)
            if name == 'distinct_reader_problems':
                self.assertIn('아라비아 숫자', instructions)
                return {'candidates': [candidate('공동 선물 준비자의 의견을 조율하는 방법', '')]}
            evidence = json.loads(content[0]['text'])
            self.assertEqual(len(evidence['existing_articles']), 12)
            self.assertTrue(all(0 < len(x['body']) <= 1800 for x in evidence['existing_articles']))
            self.assertNotIn('/board/free/100', evidence['comparisons'][0]['compare_paths'])
            expected.update(writing_brief([evidence['comparisons'][0]['compare_paths'][-1]]))
            return {'selected_index': 0, 'reason': '참여자가 합의할 범위를 정하는 판단이 새롭습니다.',
                    'rejections': [], 'rejected_indices': [], 'writing_brief': expected}
        with tempfile.TemporaryDirectory() as temp, patch('board_planner.existing_articles', return_value=rows):
            root = Path(temp); fixture(root)
            plan = choose_plan('purchase', PROFILES['purchase'], None, [], DAY, root, 'draft', 'review',
                               ask, text_input, Mock(), lambda t: True)
        self.assertEqual(plan['writing_brief'], expected)
        self.assertEqual(calls, ['distinct_reader_problems', 'topic_novelty_screen'])

    def test_drafting_and_editing_receive_the_same_brief_with_no_extra_call(self):
        plan = {**candidate('공동 선물 준비자의 의견을 조율하는 방법', ''), 'writing_brief': writing_brief()}
        original = copy.deepcopy(plan)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'}), \
                    patch('board_drafts.urllib.request.urlopen', return_value=response(example())) as api:
                data = generate(plan['topic'], 'draft', Mock(), root=root, day=DAY, topic_plan=plan)
                payload = json.loads(api.call_args.args[0].data)
                self.assertEqual(json.loads(payload['input'])['topic_plan']['writing_brief'], original['writing_brief'])
                self.assertIn('section_actions', payload['instructions'])
                self.assertEqual(api.call_count, 1)
            with patch('board_editor.ask_json', return_value=example()) as api:
                edit_article('purchase', plan['topic'], data, None, 'draft', Mock(), root, topic_plan=plan)
                payload = json.loads(api.call_args.args[1][0]['text'])
                self.assertEqual(payload['topic_plan']['writing_brief'], original['writing_brief'])
                self.assertEqual(api.call_count, 1)
        self.assertEqual(plan, original)

    def test_approved_brief_never_overrides_independent_body_rejection(self):
        report = {'unique': False, 'holdReason': BODY_DUPLICATE,
                  'issues': ['합의 행동을 구현하지 않고 일반적인 확인만 반복해 기존 본문과 같습니다.'],
                  'search_intent': '공동 준비에서 합의할 범위를 정하는 구체적인 질문',
                  'image_scene': '서로 다른 선물 준비 항목을 두 사람이 나누어 정하는 장면',
                  'image_alt': '함께 정할 준비와 각자 고를 준비를 구분하는 모습', 'related_paths': []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            with patch('board_originality.reject_copy', return_value=None), \
                    patch('board_originality.related_articles', return_value=[]), \
                    patch('board_editor.ask_json', return_value=report) as api:
                with self.assertRaises(NoTopic) as error:
                    preflight('purchase', '공동 선물 준비자의 의견을 조율하는 방법', example(), 'review', Mock(), root,
                              topic_plan={'writing_brief': writing_brief()})
                self.assertEqual(error.exception.hold_reason, BODY_DUPLICATE)
                self.assertEqual(api.call_count, 1)


if __name__ == '__main__':
    unittest.main()
