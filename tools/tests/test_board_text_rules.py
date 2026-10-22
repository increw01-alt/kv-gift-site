"""Rejected text must stay blocked, and both API stages must receive prevention rules."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_drafts as draft
import board_editor as editor
from test_board_drafts import example


class TextRulesTests(unittest.TestCase):
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only'})
    def test_draft_and_edit_requests_both_receive_full_prevention_guidance(self):
        payloads = []

        def respond(request, **kwargs):
            payloads.append(json.loads(request.data))
            return io.BytesIO(json.dumps({'status': 'completed', 'usage': {},
                'output': [{'content': [{'type': 'output_text', 'text': json.dumps(example())}]}]}).encode())

        with patch('urllib.request.urlopen', side_effect=respond), \
             patch.object(editor, 'related_titles', return_value=[]):
            data = draft.generate('검토 주제', 'gpt-4.1-mini')
            editor.edit_article('sale', '검토 주제', data, None, 'gpt-4.1-mini', lambda *args: None)
        self.assertEqual(len(payloads), 2)
        for payload in payloads:
            self.assertEqual(payload['model'], 'gpt-4.1-mini')
            self.assertIn(draft.ARTICLE_TEXT_RULES, payload['instructions'])
            self.assertIn('모든 소제목', payload['instructions'])
            self.assertIn('전각 숫자', payload['instructions'])
            self.assertIn("'안전한 거래'", payload['instructions'])
            self.assertIn('출력 직전에', payload['instructions'])

    def test_incident_patterns_remain_blocked_in_every_output_field(self):
        for field in ('summary', 'heading', 'body', 'checks'):
            for token in ('2', '２', '안전한 거래', '안전한\n거래'):
                with self.subTest(field=field, token=token):
                    data = example()
                    if field == 'summary':
                        data['summary'] += ' ' + token
                    elif field == 'checks':
                        data['checks'][0] += ' ' + token
                    else:
                        data['sections'][0][field] += ' ' + token
                    with self.assertRaisesRegex(ValueError, '금지 표현'):
                        draft.validate(data)

    def test_concrete_date_and_transaction_checks_are_allowed(self):
        data = example()
        data['summary'] = '게시일과 마지막 수정일을 함께 살펴보고, 안내가 달라졌다면 현재 적용되는 조건을 발행사나 판매처에 확인해 주세요.'
        data['sections'][0]['heading'] = '거래 전에 무엇을 확인할까요?'
        data['sections'][0]['body'] = ('상대방의 사업자 정보와 문의 경로를 확인하고, 상품권 취급 여부와 전달 절차를 먼저 물어보세요.\n\n'
                                     '확인한 정보를 주문 내역과 함께 보관하고, 개인정보나 상품권 전체 번호를 공개 게시판에 올리지 마세요.')
        data['checks'][0] = '안내의 게시일과 마지막 수정일을 함께 확인해 주세요.'
        self.assertEqual(draft.validate(data), data)


if __name__ == '__main__':
    unittest.main()
