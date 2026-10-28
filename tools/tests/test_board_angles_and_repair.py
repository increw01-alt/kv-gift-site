import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_drafts import ROOT, ContentValidationError, validate
from board_editor import edit_article, fresh_topic, text_input
from board_planner import choose_plan, validate_candidates, PlanningHeld
from board_profiles import PROFILES
from board_usage import UsageLog
from test_board_drafts import fixture, example, DAY
from test_board_planner import candidate, CONTEXT


class AnglesAndRepairTests(unittest.TestCase):
    def bad_article(self):
        value = example()
        value['summary'] += ' 안전한 거래를 보장해요.'
        value['sections'][1]['body'] += ' 공식 인증이라는 주장도 확인해요.'
        value['checks'][2] += ' 다음 3가지 내용을 확인해요.'
        return value

    def test_every_field_is_checked_without_weakening_the_original_guard(self):
        value = self.bad_article()
        with self.assertRaises(ContentValidationError) as error:
            validate(value)
        self.assertEqual({v['field'] for v in error.exception.violations},
                         {'summary', 'sections[1].body', 'checks[2]'})
        validate(value, check_content=False)

    def test_wording_repair_is_bounded_metered_and_full_validation_runs_again(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            usage = UsageLog(root/'repair-usage.json')
            events = []
            answers = iter([self.bad_article(), example()])
            def api(*args):
                usage.begin_request(args[4], args[5])
                args[6](args[4], args[5], {'input_tokens':100,'output_tokens':20})
                return next(answers)
            with patch('board_editor.ask_json', side_effect=api) as call:
                value = edit_article('purchase','상품권 안내의 문구와 조건을 읽는 방법',example(),None,
                    'gpt-4.1-mini',usage.record,root,on_repair=lambda event: events.append(copy.deepcopy(event)))
            validate(value)
            self.assertEqual(call.call_count, 2)
            self.assertEqual([e['status'] for e in events], ['started','passed'])
            self.assertEqual(call.call_args.args[3], 'corrected_board_wording')
            self.assertIn('주장 자체를 제거', call.call_args.args[0])
            usage.save('completed')
            saved=json.loads(usage.path.read_text(encoding='utf-8'))
            self.assertEqual(len(saved['requests']),2)
            self.assertEqual(saved['accounting_status'],'complete')
            self.assertGreater(saved['estimated_total_usd'],0)

    def test_failed_repair_does_not_loop_or_silently_strip_prohibited_words(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root);events=[]
            with patch('board_editor.ask_json',return_value=self.bad_article()) as call:
                with self.assertRaises(ContentValidationError):
                    edit_article('purchase','상품권 안내 문구를 구분하는 방법',example(),None,
                        'model',lambda *x:None,root,on_repair=lambda event:events.append(copy.deepcopy(event)))
            self.assertEqual(call.call_count,2)
            self.assertEqual(events[-1]['status'],'failed')

    def test_valid_edit_and_structural_errors_do_not_request_extra_paid_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            bad=example();bad['sections']=bad['sections'][:2]
            for answer, fails in ((example(),False),(bad,True)):
                with self.subTest(fails=fails), patch('board_editor.ask_json',return_value=answer) as call:
                    if fails:
                        with self.assertRaises(ValueError):
                            edit_article('purchase','상품권 안내를 확인하는 방법',example(),None,'model',lambda *x:None,root)
                    else:
                        validate(edit_article('purchase','상품권 안내를 확인하는 방법',example(),None,'model',lambda *x:None,root))
                    self.assertEqual(call.call_count,1)

    def test_same_family_has_explicit_different_situation_and_result_but_still_needs_review(self):
        value=candidate('공동 선물을 준비할 때 참여 의견을 조율하는 방법','gift-choice')
        value.update(task_id='',reader_situation='선물 받을 사람 대신 함께 준비하는 사람들의 의견을 조율할 때',
                     deliverable='참여 여부와 공동 구매 기준을 합의할 질문 목록을 완성하기')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            for selected in (0,-1):
                api=Mock(side_effect=[{'candidates':[value]},
                    {'selected_index':selected,'reason':'기존 글의 독자 질문과 실제 해결 단계를 비교했습니다.','rejections':[]}])
                args=('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',api,text_input,lambda *x:None,lambda t:True)
                if selected < 0:
                    with self.assertRaises(PlanningHeld):choose_plan(*args)
                else:
                    self.assertEqual(choose_plan(*args)['deliverable'],value['deliverable'])
                self.assertEqual(api.call_count,2)
                self.assertIn('실제 해결 단계',api.call_args.args[0])
            broken={**value};broken.pop('deliverable')
            with self.assertRaises(ValueError):validate_candidates({'candidates':[broken]},{'gift-choice'},lambda t:True)

    def test_catalog_has_distinct_ids_and_board_specific_questions_without_news_claims(self):
        tasks=json.loads((ROOT/'tools/board_reader_tasks.json').read_text(encoding='utf-8'))
        self.assertEqual(len(tasks),len({t['id'] for t in tasks}))
        self.assertEqual(len(tasks),len({t['question'] for t in tasks}))
        self.assertNotIn('gc_word',{t['board'] for t in tasks})
        for board in ('purchase','sale','gc_tip','gc_information','general_notice','sense','free'):
            self.assertGreaterEqual(sum(t['board']==board for t in tasks),14)
        for task in tasks:
            self.assertGreater(len(task['deliverable']),20)
            self.assertTrue(fresh_topic(task['question'],[]),task['id'])


if __name__=='__main__':unittest.main()
