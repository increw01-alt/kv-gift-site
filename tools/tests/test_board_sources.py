import datetime as dt
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_drafts import ROOT, NoTopic, render
from board_sources import validate_source, source_context
from board_originality import reject_copy, preflight, related_articles, validate_plan
from update_editorial_sources import apply_update
import board_editor
from test_board_drafts import fixture, example, DAY


def signals():
    return {'schema_version':1, 'source':'kakao_drive', 'checked_at':'2026-10-23T01:00:00Z',
            'source_modified_at':'2026-10-19T02:36:21.075Z', 'source_sha256':'a'*64,
            'message_count':100, 'signals':[{'id':'card-performance','count':10}]}


def plan():
    return {'unique':True, 'issues':[], 'search_intent':'카드 실적과 이벤트 조건의 차이를 구분하는 방법',
            'image_scene':'상품권 옆에 놓인 서로 다른 확인 목록을 비교하는 손을 표현한다.',
            'image_alt':'상품권과 두 가지 확인 목록을 나란히 비교하는 손', 'related_paths':[]}


class SourcesTests(unittest.TestCase):
    def test_raw_messages_extra_fields_and_unknown_ids_never_import(self):
        for key, value in [('text','비밀 대화'), ('signals',[{'id':'unknown','count':1}]),
                           ('signals',[{'id':'card-performance','count':101}]),
                           ('message_count',True), ('schema_version',True), ('source_sha256','private message')]:
            data=signals();data[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_source(data)
        validate_source(signals())

    def test_idempotent_source_import_and_board_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            shutil.copyfile(ROOT/'tools/editorial_source_catalog.json',root/'tools/editorial_source_catalog.json')
            self.assertTrue(apply_update(root,signals()))
            self.assertFalse(apply_update(root,signals()))
            self.assertIsNone(source_context('gc_word',root))
            self.assertEqual(source_context('purchase',root)['questions'][0]['id'],'card-performance')
            older=signals();older['checked_at']='2026-10-22T01:00:00Z'
            self.assertFalse(apply_update(root,older))

    def test_source_guided_topics_take_priority_over_generic_pool(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            shutil.copyfile(ROOT/'tools/editorial_source_catalog.json',root/'tools/editorial_source_catalog.json')
            apply_update(root,signals())
            title='상품권 구입 전 카드 실적 제외 안내를 어떻게 따로 확인할까요?'
            proposed={'candidates':[{'topic':title,'source_id':'card-performance',
                       'reader_problem':'상품권 구매 전 카드 조건을 구분하고 싶은 독자',
                       'distinct_angle':'카드 상품설명서의 제외 항목을 비교하는 과정',
                       'outline':['카드 상품설명서를 준비하는 단계','실적 제외 항목을 구분하는 단계','행사 안내와 별도로 비교하는 단계']}]}
            screen={'selected_index':0,'reason':'기존 안내와 구분되는 질문과 절차입니다.','rejections':[]}
            with patch.object(board_editor,'ask_json',side_effect=[proposed,screen]) as api:
                self.assertEqual(board_editor.select_topic('purchase',DAY,'model',lambda *x:None,root)[1],title)
            self.assertEqual(api.call_count,2)
            self.assertIn('reader_questions', api.call_args_list[0].args[1][0]['text'])
            self.assertIn('comparisons', api.call_args_list[1].args[1][0]['text'])

    def test_near_copy_is_held_before_any_image_or_review_request(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            render('purchase','상품권 구입에 필요한 주문 정보를 먼저 정리하려면 어떻게 할까요?',example(),DAY,root)
            self.assertIsNotNone(reject_copy(example(),root))
            with patch.object(board_editor,'ask_json') as api, self.assertRaises(NoTopic):
                preflight('purchase','표현만 바꾼 다른 제목',example(),'model',lambda *x:None,root)
            api.assert_not_called()

    def test_semantic_rejection_and_invalid_links_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            rejected=plan();rejected.update(unique=False,issues=['기존 글과 같은 질문'])
            with patch.object(board_editor,'ask_json',return_value=rejected), self.assertRaises(NoTopic):
                preflight('purchase','새 제목으로 만든 기존 질문',example(),'model',lambda *x:None,root)
        invalid=plan();invalid['related_paths']=['https://evil.example/']
        with self.assertRaises(ValueError):validate_plan(invalid,[])

    def test_generated_page_has_unique_metadata_descriptive_alt_and_image_sitemap(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            value=plan();value['related_paths']=['/board/general_notice/43']
            topic='상품권 구입 전 카드 실적 제외 안내를 어떻게 구분할까요?'
            render('purchase',topic,example(),DAY,root,'board-img/purchase/card-performance-123.png',plan=value)
            latest=json.loads((root/'board/purchase/list.json').read_text(encoding='utf-8'))[0]
            page=(root/f'board/purchase/{latest["id"]}.html').read_text(encoding='utf-8')
            self.assertEqual(page.count('<h1>'),1)
            self.assertIn(value['image_alt'],page)
            self.assertIn('함께 읽으면 좋은 글',page)
            self.assertIn('rel="canonical"',page)
            sitemap=ET.fromstring((root/'sitemap-boards.xml').read_text(encoding='utf-8'))
            self.assertTrue(sitemap.findall('.//{http://www.google.com/schemas/sitemap-image/1.1}loc'))


if __name__ == '__main__':unittest.main()
