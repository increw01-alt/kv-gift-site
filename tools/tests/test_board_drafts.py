import datetime as dt
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_drafts as draft
from board_profiles import PROFILES, ROTATION
from board_render import ASSOCIATION, save_preview

DAY = dt.date(2026, 10, 20)


def fixture(root):
    files = [draft.TEMPLATE, 'board/general_notice/43.html', 'board/general_notice/50.html',
             'data/latest_posts.json', 'data/editorial_history.json', 'sitemap-boards.xml',
             'tools/board_topics.json', 'tools/board_news_briefs.json', 'index.html',
             'css/board/approved-tip.css']
    for board in PROFILES:
        files.extend([f'board/{board}/index.html', f'board/{board}/list.json'])
    for name in files:
        dest = root/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(draft.ROOT/name, dest)
    # 운영 글이 늘어나거나 준비 주제가 소진되어도 CI 테스트 자료는 소진되지 않습니다.
    from editorial_settings import DEFAULT
    (root/'data/editorial_settings.json').write_text(json.dumps(DEFAULT),encoding='utf-8')
    topics = {board: [
        f'{profile["name"]}의 검증용 원문과 목록을 함께 연결하려면 무엇을 살펴볼까요?',
        f'보관해 둔 이전 글을 지키는 테스트 절차를 {profile["name"]}에서 어떻게 확인할까요?',
    ] for board, profile in PROFILES.items()}
    (root/'tools/board_topics.json').write_text(json.dumps(topics,ensure_ascii=False),encoding='utf-8')
    briefs=[{'topic':'검증용 운영 안내 자료를 정리한 소식을 함께 확인해 보세요',
             'verified_on':'2026-10-20','expires_on':'2026-11-20',
             'facts':['문의 준비 안내 문서가 있다.'],
             'sources':[{'title':'문의 준비 안내','url':'https://kv-gift.co.kr/board/general_notice/43'}]}]
    (root/'tools/board_news_briefs.json').write_text(json.dumps(briefs,ensure_ascii=False),encoding='utf-8')
    (root/'data/editorial_history.json').write_text(json.dumps([
        {'board':'purchase','id':1,'topic':'이미 정리한 검증용 안내 자료','drafted_at':'2026-10-01'}
    ],ensure_ascii=False),encoding='utf-8')


def example():
    return {'summary':'상품권을 구입하기 전에 판매처와 이용 조건을 확인하면 필요한 질문을 정리하는 데 도움이 됩니다.',
            'sections':[{'heading':x,'body':'상품권의 정확한 이름과 사용할 곳을 먼저 확인해 주세요. 비슷한 이름의 상품권도 사용 방법이 다를 수 있으므로 판매처에 상품명과 이용 안내를 요청하는 것이 좋습니다. 답변받은 내용을 주문 내역과 함께 보관하면 나중에 문의할 때 참고할 수 있습니다.'} for x in ['상품명 확인','판매처 확인','상담 준비']],
            'checks':['상품권의 정확한 이름을 확인했는지 점검해 주세요.','판매처의 문의 방법을 확인해 주세요.','주문 내역을 보관할 방법을 준비해 주세요.']}


class DraftTests(unittest.TestCase):
    def test_reject_markup_and_unverified_rate(self):
        for text in ['<img src=x onerror=alert(1)>','매입률은 95%입니다.','제가 이용한 실제 고객 후기입니다.']:
            data=example();data['sections'][0]['body']+=text
            with self.assertRaises(ValueError): draft.validate(data)

    def test_incomplete_content_rejected(self):
        data=example();data['sections']=[]
        with self.assertRaises(ValueError): draft.validate(data)

    def test_payment_words_are_not_first_person_testimonials(self):
        data=example();data['sections'][0]['body']+=' 결제가 진행되기 전 문제가 있는지 확인하세요.'
        draft.validate(data)

    def test_all_boards_preserve_posts_lists_metadata_and_homepage(self):
        for board in draft.BOARDS:
            with self.subTest(board=board), tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                fixture(root)
                old=draft.read_json(root/f'board/{board}/list.json')
                old_latest=draft.read_json(root/'data/latest_posts.json')
                old_history=draft.read_json(root/'data/editorial_history.json')
                old_sitemap=ET.fromstring((root/'sitemap-boards.xml').read_text(encoding='utf-8'))
                topic=draft.pick_topic(board,root,DAY)
                banner=f'board-img/{board}/guide-test.png'
                title,review,changed=draft.render(board,topic,example(),DAY,root,banner=banner)
                rows=draft.read_json(root/f'board/{board}/list.json')
                self.assertEqual(rows[1:],old)
                self.assertEqual(rows[0]['author'],draft.AUTHOR)
                if board == 'gc_word':
                    with self.assertRaises(draft.NoTopic): draft.pick_topic(board,root,DAY)
                else:
                    self.assertNotEqual(draft.pick_topic(board,root,DAY),topic)
                page=(root/f'board/{board}/{rows[0]["id"]}.html').read_text(encoding='utf-8')
                self.assertIn('실제 고객 후기나 접수된 문의가 아닙니다.',page)
                if board in ('sense','free'):
                    self.assertNotIn('class="cta"',page)
                else:
                    self.assertIn('href="'+ASSOCIATION+'"',page)
                self.assertIn('src="/'+banner+'"',page)
                self.assertIn('width="1536" height="1024"',page)
                self.assertIn(f'<meta property="og:image" content="{draft.DOMAIN}/{banner}">',page)
                self.assertIn(f'<meta name="twitter:image" content="{draft.DOMAIN}/{banner}">',page)
                self.assertIn('"image": "'+draft.DOMAIN+'/'+banner+'"',page)
                self.assertEqual(len(re.findall(r'<h1[ >]',page)),1)
                self.assertIn(f'href="/board/{board}/"',page)
                self.assertIn(title,review)
                self.assertIn('Merge pull request',review)
                latest=draft.read_json(root/'data/latest_posts.json')
                self.assertEqual(latest[board][0]['id'],rows[0]['id'])
                for other in old_latest:
                    if other != board: self.assertEqual(latest[other],old_latest[other])
                history=draft.read_json(root/'data/editorial_history.json')
                self.assertEqual(history[:-1],old_history)
                self.assertTrue(history[-1]['automation'])
                sitemap=ET.fromstring((root/'sitemap-boards.xml').read_text(encoding='utf-8'))
                self.assertEqual(len(sitemap),len(old_sitemap)+1)
                index=(root/f'board/{board}/index.html').read_text(encoding='utf-8')
                self.assertIn(f'/board/{board}/{rows[0]["id"]}',index)
                self.assertIn(f'총 {len(rows)}건.',index)
                if PROFILES[board]['list'] == 'table':
                    tbody=re.search(r'<tbody[^>]*>.*?</tbody>',index,re.S).group()
                    self.assertIn('id="board_rows"',tbody)
                    first=re.search(r'<tr.*?</tr>',tbody,re.S).group()
                    self.assertEqual(first.count('<td'),6 if PROFILES[board].get('category') else 5)
                else:
                    cards=re.search(r'<div id="card_rows">(.*?)</div>',index,re.S).group(1)
                    self.assertEqual(cards.count('<a '),len(rows))
                if board == 'free': self.assertGreater(rows[0]['id'],465)
                if board in ('purchase','sale','free','gc_tip','general_notice'):
                    self.assertIn('index.html',changed)
                    self.assertIn(title,(root/'index.html').read_text(encoding='utf-8'))
                if board == 'gc_word': self.assertIn('확인 자료',page)

    def test_rotation_ignores_manual_posts_and_deduplicates_across_boards(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            path=root/'data/editorial_history.json'
            path.write_text('[]',encoding='utf-8')
            board,topic=draft.select_board('auto',root,DAY)
            self.assertEqual(board,ROTATION[0])
            history=[{'board':'free','topic':topic,'automation':False}]
            path.write_text(json.dumps(history),encoding='utf-8')
            self.assertNotEqual(draft.pick_topic(board,root,DAY),topic)
            self.assertEqual(draft.select_board('auto',root,DAY)[0],board)
            history.append({'board':board,'topic':topic,'automation':True})
            path.write_text(json.dumps(history),encoding='utf-8')
            self.assertEqual(draft.select_board('auto',root,DAY)[0],ROTATION[1])

    def test_missing_or_expired_news_skips_to_another_board(self):
        for expired in (False,True):
            with self.subTest(expired=expired),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);fixture(root)
                path=root/'tools/board_news_briefs.json'
                briefs=draft.read_json(path)
                if expired: briefs[0]['expires_on']='2026-10-19'
                else: briefs=[]
                path.write_text(json.dumps(briefs),encoding='utf-8')
                with self.assertRaises(draft.NoTopic): draft.pick_topic('gc_word',root,DAY)
                (root/'data/editorial_history.json').write_text(
                    json.dumps([{'board':'free','topic':'used','automation':True}]),encoding='utf-8')
                self.assertEqual(draft.select_board('auto',root,DAY)[0],'gc_tip')

    def test_invalid_template_or_banner_does_not_partially_write_lists(self):
        for invalid in ('banner','template'):
            with self.subTest(invalid=invalid),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);fixture(root)
                path=root/'board/gc_tip/list.json'
                before=path.read_bytes()
                banner='board-img/gc_tip/test.png'
                if invalid == 'banner': banner='board-img/sale/test.png'
                else: (root/draft.TEMPLATE).write_text('<html></html>',encoding='utf-8')
                with self.assertRaises(ValueError):
                    draft.render('gc_tip','검토 주제',example(),DAY,root,banner)
                self.assertEqual(path.read_bytes(),before)

    @patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'})
    def test_requests_include_selected_board_editorial_direction(self):
        for board in ('gc_tip','free','sense'):
            response={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(example())}]}]}
            with self.subTest(board=board),patch.object(draft.urllib.request,'urlopen',
                    return_value=io.BytesIO(json.dumps(response).encode())) as api:
                draft.generate('검토 주제','gpt-4.1-mini',board=board)
                payload=json.loads(api.call_args.args[0].data)
                self.assertIn(PROFILES[board]['purpose'],payload['instructions'])
                self.assertIn(PROFILES[board]['outline'],payload['instructions'])

    def test_standalone_preview_is_unpublished_and_does_not_edit_site(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            path=root/'board/gc_tip/list.json'
            before=path.read_bytes()
            save_preview(root/'review','gc_tip','검토 주제',example(),DAY,b'image',root)
            page=(root/'review/index.html').read_text(encoding='utf-8')
            self.assertIn('noindex,nofollow',page)
            self.assertIn('src="banner.png"',page)
            self.assertFalse(draft.read_json(root/'review/draft.json')['published'])
            self.assertEqual(path.read_bytes(),before)


if __name__=='__main__': unittest.main()
