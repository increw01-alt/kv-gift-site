import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_drafts import ROOT, KST
from board_editor import text_input, prior_titles, fresh_topic
from board_planner import choose_plan, PlanningHeld, planning_material
from board_profiles import PROFILES
from board_topic_pool import apply_pool_update, pending_plans, pool_update, POOL_LIMIT
from board_retry import retry_state, retry_guard
from board_usage import UsageLog
from run_board_publish import record_outcome
from test_board_drafts import fixture, DAY
from test_board_planner import candidate, CONTEXT
import test_board_publish as publish_cases
from test_board_publish import NOW


def screen(selected=0, rejected=None):
    return {'selected_index': selected, 'reason': '기존 글과 다른 구체적인 결정 상황과 결과물을 확인했습니다.',
            'rejections': [], 'rejected_indices': rejected or []}


class TopicSupplyTests(unittest.TestCase):
    def test_explicit_planning_rejects_are_not_retried_but_pending_plans_are_available(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            rejected=candidate('동일한 선물의 보관 장소만 바꿔 다시 안내하는 방법','')
            pending=candidate('여러 수신자의 사용 목적에 맞춰 금액을 배분하는 방법','')
            ledger=root/f'data/editorial_runs/{DAY}/1.json';ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({'status':'held','api_usage':{'context':{
                'rejected_topic_plans':[rejected]}}}),encoding='utf-8')
            apply_pool_update(root,pool_update('purchase',[pending]))
            titles=prior_titles(root)
            self.assertFalse(fresh_topic(rejected['topic'],titles))
            self.assertTrue(fresh_topic(pending['topic'],titles))

    def test_exhausted_prepared_catalog_replenishes_and_keeps_unselected_candidates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            tasks=json.loads((ROOT/'tools/board_reader_tasks.json').read_text(encoding='utf-8'))
            (root/'tools/board_reader_tasks.json').write_text(json.dumps(tasks),encoding='utf-8')
            ledger=root/f'data/editorial_runs/{DAY}/1.json';ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({'status':'held','review':{'issues':['주제 중복']},'api_usage':{'context':{
                'rejected_topic_plans':[{'task_id':t['id'],'topic':t['question']} for t in tasks]}}}),encoding='utf-8')
            material,_=planning_material(root,CONTEXT,'purchase',DAY)
            self.assertEqual(material['unused_reader_tasks'],[])
            plans=[candidate('사용 장소와 이동 동선을 대조하여 선물을 고르는 방법',''),
                   candidate('액면가가 다른 선택지에서 실제 지출을 비교하는 방법','')]
            api=Mock(side_effect=[{'candidates':plans},screen()]);updates=[]
            selected=choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',
                                 api,text_input,lambda *a:None,lambda t:True,on_pool=updates.append)
            prompt=json.loads(api.call_args_list[0].args[1][0]['text'])
            self.assertIn('new_problem_directions',prompt)
            self.assertEqual(selected['topic'],plans[0]['topic'])
            self.assertEqual(updates[-1]['pending'],[plans[1]])
            self.assertEqual(api.call_count,2)
            usage=UsageLog(root/'usage.json',{'topic_pool_update':updates[-1]});usage.save('completed')
            files,_=record_outcome(root,DAY,'2','purchase',plans[0]['topic'],'held',
                                   {'approved':False,'issues':['최종 본문 중복']},usage)
            self.assertIn('data/editorial_topic_pool.json',files)
            self.assertEqual(pending_plans(root,'purchase'),[plans[1]])
            saved=json.loads(ledger.read_text(encoding='utf-8'))
            self.assertEqual(len(saved['api_usage']['context']['rejected_topic_plans']),len(tasks))

    def test_saved_pool_skips_new_planning_request_and_removes_only_selected_and_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            plans=[candidate(t,'') for t in ['이동 동선을 고려해 선물의 사용 장소를 비교하는 방법',
                                            '예산과 추가 지출을 대조해 선택 기준을 세우는 방법',
                                            '사용할 계획과 보관 부담을 비교해 물건을 고르는 방법']]
            apply_pool_update(root,pool_update('purchase',plans));updates=[]
            api=Mock(return_value=screen(0,[1]))
            selected=choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',api,
                                 text_input,lambda *a:None,lambda t:True,on_pool=updates.append)
            self.assertEqual(api.call_count,1)
            self.assertEqual(api.call_args.args[3],'topic_novelty_screen')
            self.assertEqual(updates[-1]['pending'],[plans[2]])
            self.assertEqual(selected['screened_out_plans'],[plans[1]])

    def test_low_pool_replenishes_without_resetting_previous_outcomes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            old=candidate('액면가와 실제 결제할 금액을 비교해 보는 방법','')
            new=candidate('서로 다른 사용 장소의 이동 동선을 비교하는 방법','')
            apply_pool_update(root,pool_update('purchase',[old]));updates=[]
            api=Mock(side_effect=[{'candidates':[new]},screen()])
            choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',api,
                        text_input,lambda *a:None,lambda t:True,on_pool=updates.append)
            self.assertEqual(updates[-1]['pending'],[new])
            prompt=json.loads(api.call_args_list[0].args[1][0]['text'])
            self.assertEqual(prompt['pending_topics_to_avoid_repeating'],[old['topic']])

    def test_empty_and_rejected_batches_do_not_leave_retry_candidates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root);updates=[]
            with self.assertRaises(PlanningHeld):
                choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',
                            Mock(return_value={'candidates':[]}),text_input,lambda *a:None,lambda t:True,on_pool=updates.append)
            self.assertEqual(updates[-1]['pending'],[])
            plans=[candidate('서로 다른 안내 항목의 실제 용도를 비교하는 방법','')]
            api=Mock(side_effect=[{'candidates':plans},screen(-1,[0])])
            with self.assertRaises(PlanningHeld):
                choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',
                            api,text_input,lambda *a:None,lambda t:True,on_pool=updates.append)
            self.assertEqual(updates[-1]['pending'],[])

    def test_pool_is_bounded_and_keeps_only_public_planning_fields(self):
        plans=[{**candidate('서로 다른 독자 문제를 해결하는 비교 방법 '+str(n),''),'debug_secret':'never persist'}
               for n in range(30)]
        update=pool_update('purchase',plans)
        self.assertEqual(len(update['pending']),POOL_LIMIT)
        self.assertNotIn('debug_secret',str(update))


class RetryTests(unittest.TestCase):
    def add(self,root,number,instant,status='held',reason='주제 사전 검수 보류: 기존 글과 중복'):
        folder=root/'data/editorial_runs'/instant.date().isoformat();folder.mkdir(parents=True,exist_ok=True)
        (folder/f'{number}.json').write_text(json.dumps({'run_id':str(number),'status':status,
            'scheduled_at':instant.isoformat(),'review':{'issues':[reason]}}),encoding='utf-8')

    def test_cooldown_increases_and_resume_does_not_modify_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            at=dt.datetime(2026,10,20,9,17,tzinfo=KST)
            for number,expected in [(1,30),(2,60),(3,120),(4,120)]:
                self.add(root,number,at)
                state=retry_state(root,at.date())
                self.assertEqual(state['cooldownMinutes'],expected)
                self.assertIsNotNone(retry_guard(root,at.date(),at+dt.timedelta(minutes=5)))
                self.assertIsNone(retry_guard(root,at.date(),at+dt.timedelta(minutes=expected)))
                self.assertEqual(len(list((root/'data/editorial_runs'/at.date().isoformat()).glob('*.json'))),number)
                at+=dt.timedelta(minutes=expected)

    def test_success_and_new_day_reset_cooldown_without_erasing_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root);at=dt.datetime(2026,10,20,9,17,tzinfo=KST)
            self.add(root,1,at);self.add(root,2,at+dt.timedelta(minutes=31),status='published',reason='')
            self.assertEqual(retry_state(root,DAY)['consecutiveTopicHolds'],0)
            self.assertIsNone(retry_guard(root,DAY+dt.timedelta(days=1),at+dt.timedelta(days=1)))
            self.assertEqual(len(list((root/'data/editorial_runs'/DAY.isoformat()).glob('*.json'))),2)

    def test_malformed_or_naive_legacy_time_does_not_create_permanent_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            self.add(root,1,dt.datetime(2026,10,20,9,17))
            self.assertIsNone(retry_state(root,DAY)['retryAfter'])

    def test_waiting_run_never_calls_paid_functions_or_reserves_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'site';fixture(root)
            self.add(root,1,NOW-dt.timedelta(minutes=5))
            helper=publish_cases.PublishingTests()
            with patch('run_board_publish.select_topic',side_effect=AssertionError('no paid calls')):
                code,_=helper.run_case(root,Path(temp)/'out',now=NOW)
            self.assertEqual(code,0)
            self.assertFalse((root/f'data/editorial_runs/{NOW.date()}/123456.json').exists())

    def test_daily_caps_remain_enforced_before_cooldown(self):
        import run_board_publish as publish
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root);at=dt.datetime(2026,10,20,9,17,tzinfo=KST)
            for number in range(15):self.add(root,number,at+dt.timedelta(minutes=number))
            self.assertIn('15회',publish.guard(root,DAY,'new','1'))
            self.assertIn('재실행',publish.guard(root,DAY,'new','2'))


if __name__=='__main__':unittest.main()
