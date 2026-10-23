import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_planner import choose_plan, PlanningHeld, planning_material, validate_candidates
from board_profiles import PROFILES
from board_sources import planned_source_context
from board_editor import text_input
from run_board_publish import record_outcome
from board_usage import UsageLog
from test_board_drafts import fixture, DAY, example
from board_drafts import render


def candidate(topic, source_id='card-performance'):
    return {'topic': topic, 'source_id': source_id,
            'reader_problem': '구매 안내에서 서로 다른 정보를 비교하려는 독자의 질문',
            'distinct_angle': '기존의 실적 조건과 달리 안내 문서의 비교 방법을 설명',
            'outline': ['비교할 안내 문서를 따로 준비하는 단계', '각각의 차이를 구분하여 읽어 보는 단계', '선택할 기준을 자기 상황에 맞게 정하는 단계']}


CONTEXT = {'kind': 'anonymized_question_signals', 'questions': [
    {'id': 'card-performance', 'question': '카드 실적과 이벤트 실적을 어떻게 구분할까요?', 'keywords': ['카드 실적']},
    {'id': 'gift-choice', 'question': '선물에 맞는 안내를 어떻게 고를까요?', 'keywords': ['선물']} ]}


class PlannerTests(unittest.TestCase):
    def test_selects_distinct_candidate_instead_of_first_title_and_reads_rejection_reasons(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            previous='카드 실적과 이벤트 실적의 차이는 어떻게 확인하나요?'
            render('gc_information',previous,example(),DAY,root)
            held=root/'data/editorial_runs/2026-10-20/100.json'
            held.parent.mkdir(parents=True)
            held.write_text(json.dumps({'status':'held','board':'purchase',
                'topic':'카드 실적 인정 범위를 확인하는 방법',
                'review':{'issues':['카드 실적과 이벤트 조건을 나눠 확인하는 해결 절차가 중복됩니다.']}}),encoding='utf-8')
            proposals=[candidate('카드 실적과 이벤트 실적을 구분하는 방법'),
                       candidate('선물 안내를 비교해 나에게 맞는 전달 방식을 고르는 방법','gift-choice')]
            api=Mock(side_effect=[{'candidates':proposals},
                {'selected_index':1,'reason':'둘째 후보는 다른 독자 문제를 해결합니다.','rejections':['첫째 후보는 중복']}])
            plan=choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',api,text_input,lambda *x:None,lambda t:True)
            self.assertEqual(plan['topic'],proposals[1]['topic'])
            first=json.loads(api.call_args_list[0].args[1][0]['text'])
            screen=json.loads(api.call_args_list[1].args[1][0]['text'])
            self.assertIn('해결 절차가 중복',first['recent_rejections'][0]['issues'][0])
            self.assertTrue(any(x['body'] for x in screen['existing_articles']))
            self.assertEqual(len({x['path'] for x in screen['existing_articles']}),len(screen['existing_articles']))
            self.assertIn(previous,str(screen))
            self.assertEqual(api.call_count,2)

    def test_all_rejected_retains_board_and_candidates_without_requesting_a_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            plans=[candidate('카드 실적과 이벤트 실적을 구분하는 방법')]
            api=Mock(side_effect=[{'candidates':plans},
                {'selected_index':-1,'reason':'기존 글과 해결 절차가 같습니다.','rejections':['같은 질문']}])
            with self.assertRaises(PlanningHeld) as error:
                choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',api,text_input,lambda *x:None,lambda t:True)
            self.assertEqual(error.exception.board,'purchase')
            self.assertEqual(error.exception.candidates,plans)
            self.assertEqual(api.call_count,2)

    def test_held_source_cooldown_crosses_boards_and_expires_without_deleting_costs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            plan=candidate('카드 실적과 이벤트 실적을 구분하는 방법')
            usage=UsageLog(root/'usage.json',{'topic_plan':plan})
            usage.record('topic','gpt-4.1-mini',{'input_tokens':100,'output_tokens':30})
            usage.save('completed')
            _, original=record_outcome(root,DAY,'100','purchase',plan['topic'],'held',
                                      {'approved':False,'issues':['본문 중복']},usage)
            material,_=planning_material(root,CONTEXT,'gc_information',DAY)
            self.assertEqual([q['id'] for q in material['reader_questions']['questions']],['gift-choice'])
            later,_=planning_material(root,CONTEXT,'gc_information',DAY+dt.timedelta(days=8))
            self.assertEqual(len(later['reader_questions']['questions']),2)
            saved=json.loads((root/f'data/editorial_runs/{DAY}/100.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['api_usage'],original['api_usage'])
            self.assertGreater(saved['api_usage']['estimated_total_usd'],0)

    def test_empty_candidate_batch_and_invalid_selection_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            for proposal, screen, exception in [({'candidates':[]},None,PlanningHeld),
                ({'candidates':[candidate('카드 실적과 이벤트 실적을 구분하는 방법')]},
                 {'selected_index':7,'reason':'선택 범위를 벗어났습니다.','rejections':[]},ValueError)]:
                api=Mock(side_effect=[proposal,screen])
                with self.assertRaises(exception):
                    choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',api,text_input,lambda *x:None,lambda t:True)
                self.assertEqual(api.call_count,1 if screen is None else 2)

    def test_only_selected_source_reaches_writing_and_ids_are_whitelisted(self):
        plan=candidate('카드 실적과 이벤트 실적을 구분하는 방법')
        self.assertEqual(len(planned_source_context(CONTEXT,plan)['questions']),1)
        plan['source_id']=''
        self.assertEqual(planned_source_context(CONTEXT,plan)['questions'],[])
        plan['source_id']='arbitrary-private-text'
        with self.assertRaises(ValueError):
            validate_candidates({'candidates':[plan]},{'card-performance'},lambda t:True)


if __name__=='__main__':unittest.main()
