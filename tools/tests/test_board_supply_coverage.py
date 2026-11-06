"""Supply regressions: no API calls, no relaxing the independent review gate."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from planner_fixtures import PlannerMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_drafts import ROOT, read_json
from board_editor import fresh_topic, text_input
from board_planner import choose_plan, PlanningHeld, planning_material
from board_profiles import PROFILES
from board_topic_pool import pool_update, apply_pool_update, pending_plans, expansion_focus
from board_topic_supply import coverage_index, covered_examples, rank_distinct, same_problem, direction_options
from test_board_drafts import fixture, DAY
from test_board_planner import candidate, CONTEXT
from test_board_topic_supply import screen


def task(n, question):
    return {'id': f'task-{n}', 'board': 'purchase', 'question': question,
            'reader_situation': '선물 구입 과정에서 서로 다른 선택 조건이 충돌하는 구체적인 상황',
            'deliverable': question+'에 필요한 고유한 판단 결과와 실행 순서'}


def save_record(root, number, plan, status='published'):
    path = root/f'data/editorial_runs/{DAY}/{number}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'run_id': str(number), 'status': status,
        'api_usage': {'context': {'topic_plan': plan}}}), encoding='utf-8')


class SupplyCoverageTests(unittest.TestCase):
    def test_recent_cross_board_published_problem_removes_renamed_pending_before_paid_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            old = {**candidate('거리와 시간을 함께 고려하는 생활 동선 계획 만들기', ''),
                   'reader_situation': '여러 장소를 방문하는 순서를 이동 거리와 소요 시간을 함께 비교하여 결정하려는 상황',
                   'deliverable': '거리와 시간을 대조하여 방문 순서와 이동 경로를 정하는 계획표'}
            save_record(root, 1, old)
            renamed = {**old, 'topic': '일정과 이동 시간을 묶어 생활 경로를 최적화하는 방법'}
            apply_pool_update(root, pool_update('purchase', [renamed]))
            new = candidate('선물 봉투의 펼침 구조와 내용물 배치를 미리 시험하는 방법', '')
            api = PlannerMock(side_effect=[{'candidates': [new]}, screen()]); updates = []
            selected = choose_plan('purchase', PROFILES['purchase'], None, [], DAY, root, 'draft', 'review',
                api, text_input, lambda *a: None, lambda t: True, on_pool=updates.append)
            reviewed = json.loads(api.call_args_list[1].args[1][0]['text'])['comparisons']
            self.assertNotIn(renamed['topic'], str(reviewed))
            self.assertEqual(selected['topic'], new['topic'])
            self.assertEqual(updates[-1]['supply']['stalePendingRemoved'], 1)
            self.assertEqual(api.call_count, 2)

    def test_valid_pending_assignment_outside_four_new_anchors_is_preserved_and_reviewed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            tasks = [task(i, q) for i, q in enumerate([
                '선물 포장을 제거한 뒤에도 안내가 남도록 배치하는 방법',
                '서로 충돌하는 구입 조건을 결정 나무로 좁혀 가는 방법',
                '미확인 범위를 제외하고 같은 전제에서 후보를 대조하는 방법',
                '주문 준비 작업의 선후 관계를 역순으로 연결하는 방법',
                '겉포장과 인사말을 함께 준비하는 선물 전달 순서 정하기'])]
            (root/'tools/board_reader_tasks.json').write_text(json.dumps(tasks), encoding='utf-8')
            queued = [{**candidate(t['question'], ''), 'task_id': t['id']} for t in tasks[-2:]]
            apply_pool_update(root, pool_update('purchase', queued))
            api = PlannerMock(return_value=screen(1)); updates=[]
            result = choose_plan('purchase', PROFILES['purchase'], None, [], DAY, root, 'draft', 'review',
                api, text_input, lambda *a: None, lambda t: True, on_pool=updates.append)
            self.assertEqual(result['task_id'], tasks[-1]['id'])
            self.assertEqual(api.call_count, 1)
            self.assertEqual(updates[-1]['pending'], queued[:1])
            self.assertEqual(json.loads(api.call_args.args[1][0]['text'])['comparisons'][1]['unpublished_assignment'], tasks[-1])

    def test_old_relevant_rejection_is_retrieved_beyond_previous_ninety_record_window(self):
        old = {**candidate('여러 수신자의 용도에 맞춰 상품권 금액을 배분하는 방법', ''),
               'deliverable': '여러 수신자의 용도에 맞춰 상품권 금액을 배분하는 방법', 'status': 'held'}
        recent = [{'topic': '주방 서랍의 도구 배치와 식기 수납 방법 '+str(n), 'status': 'published'} for n in range(110)]
        plans = [old, *recent]
        examples = covered_examples(plans, [old['topic']])
        self.assertIn(old['topic'], str(examples))
        self.assertEqual(next(p['status'] for p in examples if p['topic']==old['topic']), 'held')
        self.assertLessEqual(len(examples), 24)
        self.assertIn(recent[-1]['topic'], str(examples))

    def test_new_assignments_do_not_erase_pending_plans_with_available_source_signals(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            assignment=task(1,'선물 포장을 없애도 안내가 남도록 전달 구성을 시험하는 방법')
            (root/'tools/board_reader_tasks.json').write_text(json.dumps([assignment]),encoding='utf-8')
            queued=[candidate('주문 화면에서 서로 다른 조건의 설명을 논리적으로 읽는 방법'),
                    candidate('선물 전달 시 묻고 싶은 내용과 남길 선택권을 나누는 방법','gift-choice')]
            apply_pool_update(root,pool_update('purchase',queued));updates=[]
            api=PlannerMock(return_value=screen())
            selected=choose_plan('purchase',PROFILES['purchase'],CONTEXT,[],DAY,root,'draft','review',
                api,text_input,lambda *a:None,lambda t:True,on_pool=updates.append)
            self.assertEqual(selected['source_id'],'card-performance')
            self.assertEqual(api.call_count,1)
            self.assertEqual(updates[-1]['pending'],queued[1:])

    def test_direction_selection_uses_all_board_coverage_not_calendar_rotation(self):
        used = '이동 거리와 이용 시간을 함께 생각하는 생활 계획'
        new = '읽기 순서가 복잡한 표에서 행과 열을 함께 읽는 접근성 연습'
        plans = [{'topic': used, 'deliverable': used, 'status': 'published'}]
        dirs = direction_options([used, new], 'sense', plans, coverage_index(plans, []), limit=1)
        self.assertEqual(dirs[0]['brief'], new)
        recent = [{'topic': new, 'direction_id': dirs[0]['id'], 'status': 'held'}]
        self.assertEqual(direction_options([used, new], 'sense', recent, [], limit=1)[0]['brief'], used)

    def test_same_subject_with_different_action_is_not_removed_locally_and_still_needs_review(self):
        previous = {'topic': '선물 준비의 여러 조건을 비교하여 선택하는 방법',
                    'reader_situation': '서로 충돌하는 필수 조건 때문에 선택할 후보를 좁히기 어려운 상황',
                    'deliverable': '필수 조건과 선호 조건을 구분해 가능한 후보만 남기는 결정 나무'}
        distinct = {**candidate('선물 준비 작업의 선후 관계를 역순으로 연결하는 방법', ''),
                    'task_id': '',
                    'reader_situation': '상품 변경으로 포장을 다시 준비하지 않도록 작업 순서를 정하는 상황',
                    'deliverable': '수신 방식과 상품 선택에 의존하는 작업을 묶은 준비 순서도'}
        self.assertFalse(same_problem(distinct, previous))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); fixture(root); save_record(root, 1, previous)
            api=PlannerMock(side_effect=[{'candidates':[distinct]}, screen(-1,[0])])
            with self.assertRaises(PlanningHeld):
                choose_plan('purchase', PROFILES['purchase'], None, [], DAY, root, 'draft', 'review',
                    api, text_input, lambda *a: None, lambda t: True)
            self.assertEqual(api.call_count, 2)
            self.assertEqual(api.call_args.args[3], 'topic_novelty_screen')

    def test_new_stock_survives_exhaustion_of_old_catalog_and_has_no_news_inventions(self):
        tasks=read_json(ROOT/'tools/board_reader_tasks.json')
        added=[t for t in tasks if t['id'].startswith('supply-20261106-')]
        self.assertEqual(len(added), 42)
        self.assertEqual(len({t['id'] for t in tasks}), len(tasks))
        self.assertFalse(any(t['board']=='gc_word' for t in added))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); fixture(root)
            (root/'tools/board_reader_tasks.json').write_text(json.dumps(tasks), encoding='utf-8')
            old=[t for t in tasks if t not in added]
            for n,t in enumerate(old): save_record(root, n, {'task_id':t['id'], 'topic':t['question']}, 'held')
            for board in set(t['board'] for t in added):
                material,_=planning_material(root,None,board,DAY)
                self.assertEqual(len(material['unused_reader_tasks']),6)
            for t in added:
                self.assertTrue(12 <= len(t['question']) <=100)
                self.assertTrue(12 <= len(t['reader_situation']) <=180)
                self.assertTrue(12 <= len(t['deliverable']) <=180)

    def test_proposed_directions_are_diverse_and_pool_keeps_direction_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            def respond(instructions, content, schema, name, *args):
                if name=='distinct_reader_problems':
                    material=json.loads(content[0]['text'])
                    dirs=material['new_problem_directions']['directions']
                    self.assertEqual(len({d['id'] for d in dirs}),4)
                    return {'candidates': [{**candidate('선물 선택 조건이 충돌할 때 우선 조건을 결정하는 방법',''), 'direction_id':dirs[0]['id']},
                                           {**candidate('선물 구매 조건의 충돌을 결정 나무로 풀어 보는 방법',''), 'direction_id':dirs[0]['id']},
                                           {**candidate('포장 제거 후에도 안내가 남는 선물 구성 시험 방법',''), 'direction_id':dirs[1]['id']}]}
                from planner_fixtures import complete_report
                self.assertEqual(len(json.loads(content[0]['text'])['comparisons']),2)
                return complete_report(screen(),content)
            api=PlannerMock(side_effect=respond); updates=[]
            selected=choose_plan('purchase',PROFILES['purchase'],None,[],DAY,root,'draft','review',
                api,text_input,lambda *a:None,lambda t:True,on_pool=updates.append)
            apply_pool_update(root,updates[-1])
            self.assertTrue(selected['direction_id'])
            self.assertEqual(len(pending_plans(root,'purchase')),1)
            self.assertNotEqual(pending_plans(root,'purchase')[0]['direction_id'],selected['direction_id'])
            self.assertEqual(api.call_count,2)


if __name__=='__main__':unittest.main()
