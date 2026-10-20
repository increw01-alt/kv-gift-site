import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_editor as editor
import run_board_publish as publish
from board_drafts import ROOT, KST, NoTopic, read_json
from board_usage import estimate
from test_board_drafts import fixture, example, DAY

NOW = dt.datetime(2026, 10, 21, 10, tzinfo=KST)


def approved():
    return {'approved': True, 'checks': {key: True for key in editor.CHECKS}, 'issues': []}


def response(value):
    return io.BytesIO(json.dumps({'status': 'completed', 'usage': {'input_tokens': 10, 'output_tokens': 20},
        'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}).encode())


class EditorialTests(unittest.TestCase):
    def test_duplicate_topic_across_boards_and_unsafe_title_rejected(self):
        titles=['[생활상식] 여러 앱에 흩어진 상품권을 한눈에 정리하려면 어떻게 할까요?']
        self.assertFalse(editor.fresh_topic('여러 앱에 흩어진 상품권을 한눈에 정리하려면 어떻게 할까요?', titles))
        self.assertFalse(editor.fresh_topic('상품권을 95%에 무조건 판매하는 방법을 알아볼까요?', []))

    def test_exhausted_pool_gets_new_topics_without_repeating_published_ones(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            topics=read_json(root/'tools/board_topics.json');topics['purchase']=[]
            publish.write_json(root/'tools/board_topics.json',topics)
            used=read_json(root/'board/purchase/list.json')[0]['title']
            candidate='지인과 함께 고를 선물의 취향 질문을 정리하는 방법은 무엇인가요?'
            with patch.object(editor,'ask_json',return_value={'topics':[used,candidate]}) as call:
                board,topic,brief=editor.select_topic('purchase',DAY,'gpt-4.1-mini',lambda *a:None,root)
            self.assertEqual((board,topic,brief),('purchase',candidate,None))
            self.assertEqual(call.call_count,1)

    def test_unverified_news_never_calls_api(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            publish.write_json(root/'tools/board_news_briefs.json',[])
            with patch.object(editor,'ask_json') as call:
                with self.assertRaises(NoTopic):
                    editor.select_topic('gc_word',DAY,'gpt-4.1-mini',lambda *a:None,root)
                call.assert_not_called()

    @patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'})
    def test_image_review_fails_closed_and_sends_image_inputs(self):
        for missing in (False, True):
            result=approved()
            if missing: result['checks'].pop('image_matches')
            else: result['checks']['logo_matches']=False
            with self.subTest(missing=missing), \
                 patch.object(editor.urllib.request,'urlopen',return_value=response(result)) as api, \
                 patch.object(editor,'related_titles',return_value=[]):
                if missing:
                    with self.assertRaises(ValueError):
                        editor.review_article('gc_tip','샘플 주제',example(),b'image',None,'gpt-4.1-mini',lambda *a:None)
                else:
                    report=editor.review_article('gc_tip','샘플 주제',example(),b'image',None,'gpt-4.1-mini',lambda *a:None)
                    self.assertFalse(report['approved'])
                payload=json.loads(api.call_args.args[0].data)
                images=[x for x in payload['input'][0]['content'] if x['type']=='input_image']
                self.assertEqual(len(images),2)
                self.assertTrue(payload['text']['format']['strict'])

    def test_editor_and_review_usage_is_charged_at_text_model_rates(self):
        for kind in ('topic','editing','review'):
            self.assertEqual(estimate(kind,'gpt-4.1-mini',{'input_tokens':1000,'output_tokens':1000}),.002)


class PublishingTests(unittest.TestCase):
    def run_case(self, root, output, review=None, image_error=False, preview=False, push_error=False):
        topic='지인과 함께 고를 선물의 취향 질문을 정리하는 방법은 무엇인가요?'
        calls=[]
        def command(*args):
            calls.append(args)
            if args == ('git','branch','--show-current'): return 'main'
            if args[:2] == ('git','push') and push_error: raise RuntimeError('push rejected')
            return ''
        def text(topic,model,on_usage,**kwargs):
            on_usage('text',model,{'input_tokens':1000,'output_tokens':1000})
            return example()
        raw=(ROOT/'board-img/gc_tip/organize-vouchers-20261020.png').read_bytes()
        env={'GITHUB_ACTIONS':'true','GITHUB_REF':'refs/heads/main','GITHUB_RUN_ID':'123456',
             'GITHUB_RUN_ATTEMPT':'1','GITHUB_EVENT_NAME':'workflow_dispatch',
             'RUNNER_TEMP':str(output),'GITHUB_STEP_SUMMARY':'','GITHUB_OUTPUT':'',
             'PREVIEW_ONLY':str(preview).lower(),'REQUESTED_BOARD':'auto'}
        with patch.dict(os.environ,env), \
             patch.object(publish,'select_topic',return_value=('purchase',topic,None)), \
             patch.object(publish,'generate',side_effect=text), \
             patch.object(publish,'edit_article',return_value=example()), \
             patch.object(publish,'generate_banner',side_effect=RuntimeError('image failure') if image_error else None,
                          return_value=(raw,{'model':'gpt-image-2'})), \
             patch.object(publish,'review_article',return_value=review or approved()):
            code=publish.main(root,command,NOW)
        return code,calls

    def test_success_updates_site_and_persists_audit_before_regular_push(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'repo';fixture(root)
            old=read_json(root/'board/purchase/list.json')
            code,calls=self.run_case(root,Path(temp)/'out')
            rows=read_json(root/'board/purchase/list.json')
            self.assertEqual(code,0)
            self.assertEqual(rows[1:],old)
            history=read_json(root/'data/editorial_history.json')
            self.assertEqual(history[-1]['publication_mode'],'automatic')
            self.assertEqual(history[-1]['run_id'],'123456')
            self.assertEqual(read_json(root/history[-1]['usage_file'])['status'],'published')
            self.assertEqual(calls[-1],('git','push','origin','HEAD:refs/heads/main'))
            self.assertFalse(any('--force' in command for command in calls))

    def test_rejected_text_or_image_never_changes_public_posts(self):
        for failure in ('review','image'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/'repo';fixture(root)
                old=(root/'board/purchase/list.json').read_bytes()
                report=approved();report.update({'approved':False,'issues':['image mismatch']})
                code,calls=self.run_case(root,Path(temp)/'out',report,image_error=failure=='image')
                self.assertEqual((root/'board/purchase/list.json').read_bytes(),old)
                self.assertEqual(code,1 if failure=='image' else 0)
                ledger=read_json(root/'data/editorial_runs/2026-10-21/123456.json')
                self.assertIsNone(ledger['url'])
                self.assertEqual(ledger['api_usage']['known_subtotal_usd'],.002)
                added=next(call for call in calls if call[:2]==('git','add'))
                self.assertFalse(any(path.startswith('board/') or path.startswith('board-img/') for path in added[3:]))

    def test_preview_never_calls_git_or_changes_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'repo';fixture(root)
            old=(root/'data/editorial_history.json').read_bytes()
            code,calls=self.run_case(root,Path(temp)/'out',preview=True)
            self.assertEqual(code,0);self.assertEqual(calls,[])
            self.assertEqual((root/'data/editorial_history.json').read_bytes(),old)

    def test_daily_quota_and_rerun_guard_before_api(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'repo';fixture(root)
            day=NOW.date()
            self.assertIsNotNone(publish.guard(root,day,'100','2'))
            for index in range(10):
                publish.write_json(root/f'data/editorial_runs/{day}/{index}.json',{'status':'held'})
            self.assertIsNotNone(publish.guard(root,day,'100','1'))
            with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REF':'refs/heads/main',
                 'GITHUB_RUN_ID':'100','GITHUB_RUN_ATTEMPT':'1','PREVIEW_ONLY':'false','GITHUB_STEP_SUMMARY':''}), \
                 patch.object(publish,'sync_main'),patch.object(publish,'select_topic') as api:
                self.assertEqual(publish.main(root,lambda *a:'',NOW),0)
                api.assert_not_called()

    def test_push_failure_is_not_reported_as_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'repo';fixture(root)
            output=Path(temp)/'out'
            with self.assertRaises(RuntimeError):
                self.run_case(root,output,push_error=True)
            self.assertEqual(read_json(output/'board-review/result.json')['status'],'push_failed')


if __name__ == '__main__':
    unittest.main()
