import datetime as dt
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_drafts as draft


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

    def test_both_boards_render_without_losing_other_posts(self):
        for board in draft.BOARDS:
            with self.subTest(board=board), tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                sample=draft.BOARDS[board][1]
                files=[f'board/{board}/{sample}.html',f'board/{board}/index.html',f'board/{board}/list.json','data/latest_posts.json','sitemap-boards.xml','tools/board_topics.json']
                for name in files:
                    dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(draft.ROOT/name,dest)
                old=draft.read_json(root/f'board/{board}/list.json')
                topic=draft.pick_topic(board,root)
                title,review,changed=draft.render(board,topic,example(),dt.date(2026,10,19),root)
                rows=draft.read_json(root/f'board/{board}/list.json')
                self.assertEqual(rows[1:],old)
                self.assertEqual(rows[0]['author'],draft.AUTHOR)
                self.assertNotEqual(draft.pick_topic(board,root),topic)
                page=(root/f'board/{board}/{rows[0]["id"]}.html').read_text(encoding='utf-8')
                self.assertIn('실제 고객 후기나 접수된 문의가 아닙니다.',page)
                self.assertIn(draft.CHAT,page)
                self.assertEqual(page.count('<h1 '),1)
                self.assertIn(title,review)
                self.assertIn('Merge pull request',review)
                self.assertEqual(draft.read_json(root/'data/latest_posts.json')[board][0]['id'],rows[0]['id'])
                ET.fromstring((root/'sitemap-boards.xml').read_text(encoding='utf-8'))
                index=(root/f'board/{board}/index.html').read_text(encoding='utf-8')
                self.assertIn(f'/{rows[0]["id"]}.html',index)
                self.assertIn(f'총 {len(rows)}건.',index)


if __name__=='__main__': unittest.main()
