"""Validate the dated, unverified assignments against the real offline archive."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_drafts import ROOT, read_json
from board_editor import fresh_topic, text_input
from board_originality import grams, COPY_OVERLAP_THRESHOLD
from board_planner import planning_material, choose_plan, validate_candidates
from board_profiles import PROFILES
from board_topic_pool import LANES
from test_board_drafts import fixture, DAY

PREFIX = 'supply-20261101-'


def archive_titles(root, task_ids):
    # New tasks must be compared with prior work, but their later, proven own
    # publications must not make the next scheduled CI run fail forever.
    own_runs = set()
    for path in (root/'data/editorial_runs').glob('*/*.json'):
        record = read_json(path)
        task_id = ((record.get('api_usage') or {}).get('context') or {}).get('topic_plan', {}).get('task_id')
        if record.get('status') == 'published' and task_id in task_ids:
            own_runs.add(str(record.get('run_id')))
    own_posts = {(item['board'], str(item['id'])) for item in read_json(root/'data/editorial_history.json')
                 if str(item.get('run_id')) in own_runs and item.get('publication_mode') == 'automatic'}
    return [r['title'] for board in PROFILES for r in read_json(root/f'board/{board}/list.json')
            if (board, str(r['id'])) not in own_posts]


class CuratedSupplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = read_json(ROOT/'tools/board_reader_tasks.json')
        cls.added = [t for t in cls.tasks if t['id'].startswith(PREFIX)]
        cls.titles = archive_titles(ROOT, {t['id'] for t in cls.added})

    def test_later_own_publication_is_excluded_only_with_published_task_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            task_id = PREFIX+'regression-fixture'
            title = '[상품권팁] 추후 발행된 과제 자체와 최초 중복 근거를 구분하는 테스트'
            rows = read_json(root/'board/gc_tip/list.json')
            rows.append({'id': 99999, 'title': title})
            (root/'board/gc_tip/list.json').write_text(json.dumps(rows), encoding='utf-8')
            (root/'data/editorial_history.json').write_text(json.dumps([{
                'board': 'gc_tip', 'id': 99999, 'run_id': '99999', 'publication_mode': 'automatic'}]), encoding='utf-8')
            ledger = root/f'data/editorial_runs/{DAY}/99999.json'; ledger.parent.mkdir(parents=True)
            record = {'run_id': '99999', 'status': 'held', 'api_usage': {'context': {'topic_plan': {'task_id': task_id}}}}
            ledger.write_text(json.dumps(record), encoding='utf-8')
            self.assertIn(title, archive_titles(root, {task_id}))
            record['status'] = 'published'; ledger.write_text(json.dumps(record), encoding='utf-8')
            self.assertFalse(title in archive_titles(root, {task_id}))
            self.assertIn(title, archive_titles(root, {'unrelated-task'}))

    def test_each_non_news_board_has_five_new_decisions_and_deliverables(self):
        self.assertEqual(set(LANES), {b for b, p in PROFILES.items() if not p.get('requires_brief')})
        self.assertEqual(len({t['id'] for t in self.tasks}), len(self.tasks))
        for board in LANES:
            with self.subTest(board=board):
                tasks = [t for t in self.added if t['board'] == board]
                self.assertGreaterEqual(len(tasks), 5)
                for task in tasks:
                    for key in ('reader_situation', 'deliverable'):
                        self.assertTrue(12 <= len(task[key]) <= 180, (task['id'], key))

    @unittest.skipUnless(os.environ.get("BOARD_SUPPLY_CHECK") == "1", "과제 추가 때 수동 점검(BOARD_SUPPLY_CHECK=1). 운영 글 제목과 비교하므로 CI 게이트로 쓰지 않음")
    def test_new_tasks_pass_actual_plan_validator_and_current_title_gate(self):
        self.assertTrue(self.added, 'dated supply has not been added')
        for task in self.added:
            candidate = {'topic': task['question'], 'source_id': '', 'task_id': task['id'],
                         'reader_problem': task['reader_situation'], 'reader_situation': task['reader_situation'],
                         'deliverable': task['deliverable'], 'distinct_angle': task['deliverable'],
                         'outline': ['먼저 독자의 상황에서 판단 조건을 나누는 방법',
                                     '서로 충돌하는 선택지를 직접 대조하는 방법', '작성한 결과물로 다음 행동을 결정하는 방법']}
            with self.subTest(task=task['id']):
                self.assertEqual(validate_candidates({'candidates': [candidate]}, set(),
                                 lambda t: fresh_topic(t, self.titles), {task['id']}), [candidate])

    @unittest.skipUnless(os.environ.get("BOARD_SUPPLY_CHECK") == "1", "과제 추가 때 수동 점검(BOARD_SUPPLY_CHECK=1). 운영 글 제목과 비교하므로 CI 게이트로 쓰지 않음")
    def test_title_token_overlap_reuses_existing_originality_cutoff(self):
        # reject_copy uses candidate 5-gram coverage >= .72. Applied to titles here
        # as a lexical screen only; the semantic/body gates remain mandatory.
        self.assertEqual(COPY_OVERLAP_THRESHOLD, .72)
        self.assertTrue(self.added, 'dated supply has not been added')
        title_tokens = [(title, grams(title, 5)) for title in self.titles]
        for task in self.added:
            tokens = grams(task['question'], 5)
            nearest, overlap = max(((title, len(tokens & other)/len(tokens)) for title, other in title_tokens),
                                   key=lambda row: row[1])
            with self.subTest(task=task['id'], nearest=nearest):
                self.assertLess(overlap, COPY_OVERLAP_THRESHOLD)

    def test_new_assignments_reach_planning_after_old_catalog_is_consumed(self):
        self.assertTrue(self.added, 'dated supply has not been added')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            (root/'tools/board_reader_tasks.json').write_text(json.dumps(self.tasks, ensure_ascii=False), encoding='utf-8')
            old = [t for t in self.tasks if not t['id'].startswith(PREFIX)]
            folder = root/f'data/editorial_runs/{DAY}'; folder.mkdir(parents=True)
            (folder/'old.json').write_text(json.dumps({'status': 'held', 'api_usage': {'context': {
                'rejected_topic_plans': [{'task_id': t['id'], 'topic': t['question']} for t in old]}}}), encoding='utf-8')
            for board in LANES:
                with self.subTest(board=board):
                    material, _ = planning_material(root, None, board, DAY)
                    tasks = material['unused_reader_tasks']
                    self.assertGreaterEqual(len(tasks), 5)
                    self.assertTrue(all(t['id'].startswith(PREFIX) for t in tasks))
                    def ask(instructions, content, schema, name, *args):
                        if name == 'distinct_reader_problems':
                            anchors = json.loads(content[0]['text'])['unused_reader_tasks']
                            task = anchors[0]
                            return {'candidates': [{'topic': task['question'], 'task_id': task['id'], 'source_id': '',
                                'reader_problem': task['reader_situation'], 'reader_situation': task['reader_situation'],
                                'distinct_angle': task['deliverable'], 'deliverable': task['deliverable'],
                                'outline': ['독자가 선택해야 하는 조건을 나누는 방법', '대안을 비교하고 결과물을 작성하는 방법',
                                            '결과에 따라 다음 행동을 정하는 방법']}]}
                        from planner_fixtures import complete_report
                        return complete_report({'selected_index': 0, 'reason': '테스트용 독립 검수 통과 응답입니다.',
                                'rejections': [], 'rejected_indices': []}, content)
                    selected = choose_plan(board, PROFILES[board], None, [], DAY, root, 'draft', 'review',
                                           ask, text_input, lambda *a: None, lambda t: fresh_topic(t, self.titles))
                    self.assertTrue(selected['task_id'].startswith(PREFIX))


if __name__ == '__main__':
    unittest.main()
