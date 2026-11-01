"""Common-footer cleanup must remove only the approved legacy list items."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strip_legacy_footer import LEGACY_TITLES, _html_files, strip_files, strip_html


TITLES = (
    '백화점상품권 할부 구매 방법 친절히 알려주셔서 잘 처리했습니다',
    '백화점 상품권 할부구매 깔끔하게 해결',
    '상품권 카드 할부로 비상금 해결했습니다.. 급할 때 진짜 유용하네요 한국상품권협회 이용후기',
    '급하게 돈 나갈 때 생겨서 상품권 할부 구매 문의해봤네요 (비상금 해결 후기)',
    '신용카드 할부 상품권, 한국상품권협회 상담 후기 나눠요 💬',
    '안 쓰는 모바일상품권, 한국상품권협회에서 완전 깔끔하게 매입해 주네요!',
    '다른 곳에서 계속 소액결제 정책으로 안 되던 거 협회에서 해결했어요!!! 흐아앙ㅠ,ㅠ',
    '롯데, 컬쳐, 배민 등 가지고 있던 모바일 상품권 한 번에 싹 정리했습니다!',
    '보관해둔 모바일 상품권 정리 후기 (한국상품권협회 매입 이용)',
    '한국상품권협회 모바일 상품권 판매 후기: 당일 입금 빠르고 안전하네요 📱',
    '신용카드 할부 상품권, 한국상품권협회 이용으로 현명하게 해결한 후기',
    '컬쳐랜드 컬쳐캐쉬 제휴 OPEN [플러스존] 91.5% 현금화',
)


def footer(items):
    return '<footer id="general_tail"><ul>' + items + '</ul></footer>'


class StripLegacyFooterTests(unittest.TestCase):
    def test_removes_all_twelve_exact_titles_with_links_and_whitespace(self):
        self.assertEqual(set(LEGACY_TITLES), set(TITLES))
        self.assertEqual(len(LEGACY_TITLES), 12)
        for title in TITLES:
            for content in (title, '<a href="/old.html">\n ' + title + ' \t</a>',
                            '<p>분류</p><p> ' + title + ' </p><p>작성자</p>'):
                with self.subTest(title=title, content=content):
                    self.assertEqual(strip_html(footer('<li class="flex">' + content + '</li>')),
                                     (footer(''), 1))

    def test_preserves_other_items_and_footer_details_byte_for_byte(self):
        kept = ('<li><a href="/redpin">상품권 할부 구입 쇼핑몰 레드핀</a></li>\r\n'
                '<li><p>문화상품권 할부 구입 -한국상품권협회-</p></li>')
        details = ('<div>고객센터 1800-2434</div>\r\n'
                   '<span>평일 09:00 ~ 18:00 (점심시간 12:00 ~ 13:00)</span>'
                   '<b>한국상품권거래소</b><div id="recent_business_list">최근등록업체</div>'
                   '<a href="/business.html">인증업체</a>')
        before = footer('<li><p>' + TITLES[0] + '</p></li>' + kept).replace(
            '</footer>', details + '</footer>')
        expected = footer(kept).replace('</footer>', details + '</footer>')
        self.assertEqual(strip_html(before), (expected, 1))

    def test_is_idempotent(self):
        cleaned, count = strip_html(footer(''.join('<li>' + t + '</li>' for t in TITLES)))
        self.assertEqual(count, 12)
        self.assertEqual(strip_html(cleaned), (cleaned, 0))

    def test_standalone_item_removes_its_indented_lines(self):
        for newline in ('\n', '\r\n'):
            with self.subTest(newline=newline):
                before = ('<footer id="general_tail">' + newline + '<ul>' + newline
                          + '\t\t<li><p>' + TITLES[0] + '</p>' + newline + '\t</li>'
                          + newline + '\t<li>유지할 안내</li>' + newline + '</ul></footer>')
                expected = ('<footer id="general_tail">' + newline + '<ul>' + newline
                            + '\t<li>유지할 안내</li>' + newline + '</ul></footer>')
                self.assertEqual(strip_html(before), (expected, 1))

    def test_only_common_footer_exact_titles_are_removed(self):
        outside = '<main><ul><li><p>' + TITLES[0] + '</p></li></ul></main>'
        other_footer = '<footer id="other"><li>' + TITLES[0] + '</li></footer>'
        partial = '<li><p>' + TITLES[0] + ' 추가 안내</p></li>'
        comment = '<!-- <li>' + TITLES[0] + '</li> -->'
        script = '<script>var sample = "<li>' + TITLES[0] + '</li>";</script>'
        kept = outside + other_footer + footer(partial + comment + script)
        self.assertEqual(strip_html(kept), (kept, 0))

    def test_unchanged_file_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'faq.html'
            original = b'\xef\xbb\xbf' + footer('<li>상품권 안내</li>\r\n').encode('utf-8')
            path.write_bytes(original)
            before = path.stat()
            self.assertEqual(strip_files(root, apply=True), (0, 0))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)

    def test_file_counts_dry_run_scope_and_encoding_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ('faq.html', 'board/general_notice/42.html',
                     'payment/nested/page.html', 'tools/templates/page.html')
            expected = {}
            for index, name in enumerate(paths):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                newline = '\r\n' if index % 2 else '\n'
                prefix = '\ufeff' if index % 2 else ''
                kept = newline + '<li>상품권 할부 구입 쇼핑몰 레드핀</li>' + newline
                removed = '<li>\n<a href="/old"> ' + TITLES[index] + ' </a>\n</li>'
                removed = removed.replace('\n', newline)
                original = (prefix + footer(removed + kept)).encode('utf-8')
                path.write_bytes(original)
                expected[path] = (original, (prefix + footer(kept)).encode('utf-8'))
            excluded = ('node_modules/page.html', 'output/page.html', 'img/page.html',
                        'img/biz/page.html', 'data/page.html', 'price/nested/page.html',
                        'tools/templates/nested/page.html', 'board/img/page.html',
                        'board/output/page.html', 'payment/node_modules/page.html')
            for name in excluded:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                original = footer('<li>' + TITLES[0] + '</li>').encode('utf-8')
                path.write_bytes(original)
                expected[path] = (original, original)
            self.assertEqual(strip_files(root), (4, 4))
            for path, (original, _) in expected.items():
                self.assertEqual(path.read_bytes(), original)
            self.assertEqual(strip_files(root, apply=True), (4, 4))
            for path, (_, cleaned) in expected.items():
                self.assertEqual(path.read_bytes(), cleaned)
            self.assertEqual(strip_files(root, apply=True), (0, 0))

    def test_collects_all_six_price_pages_without_recursing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ('ak', 'galleria', 'hyundai', 'index', 'lotte', 'shinsegae')
            expected = {root / 'price' / (name + '.html') for name in names}
            excluded = root / 'price' / 'nested' / 'page.html'
            for path in (*expected, excluded):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(footer('<li>' + TITLES[-1] + '</li>'), encoding='utf-8')
            self.assertEqual(set(_html_files(root)), expected)
            self.assertEqual(strip_files(root), (6, 6))
            self.assertEqual(strip_files(root, apply=True), (6, 6))
            for path in expected:
                self.assertEqual(path.read_bytes(), footer('').encode('utf-8'))
            self.assertEqual(excluded.read_bytes(),
                             footer('<li>' + TITLES[-1] + '</li>').encode('utf-8'))

    def test_preserves_board_article_bodies_and_index_titles_outside_footer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            articles = ('board/gc_tip/24.html', 'board/sale/3682.html',
                        'board/purchase/2552.html', 'board/sale/3687.html',
                        'board/purchase/2560.html')
            expected = {}
            listings = {}
            for name, title in zip(articles, (TITLES[-1], *TITLES[:4])):
                path = root / name
                body = '<main><h1>' + title + '</h1><article>' + title + '</article></main>\r\n'
                expected[path] = body
                listings.setdefault(path.parent / 'index.html', []).append(
                    '<li><a href="' + path.name + '">' + title + '</a></li>')
            for path, items in listings.items():
                expected[path] = '<main><ul>' + ''.join(items) + '</ul></main>\r\n'
            originals = {}
            for path, body in expected.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                originals[path] = (body + footer('<li>' + TITLES[-1] + '</li>')).encode('utf-8')
                path.write_bytes(originals[path])
            self.assertEqual(strip_files(root), (8, 8))
            for path, original in originals.items():
                self.assertEqual(path.read_bytes(), original)
            self.assertEqual(strip_files(root, apply=True), (8, 8))
            for path, body in expected.items():
                self.assertEqual(path.read_bytes(), (body + footer('')).encode('utf-8'))
            self.assertEqual(strip_files(root, apply=True), (0, 0))

    def test_cli_defaults_to_dry_run_and_apply_is_explicit(self):
        script = Path(__file__).resolve().parents[1] / 'strip_legacy_footer.py'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'faq.html'
            original = footer('<li>' + TITLES[0] + '</li>').encode('utf-8')
            path.write_bytes(original)
            for args in ([], ['--dry-run']):
                result = subprocess.run([sys.executable, '-X', 'utf8', str(script), *args],
                                        cwd=directory, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('files=1 items=1', result.stdout)
                self.assertEqual(path.read_bytes(), original)
            result = subprocess.run([sys.executable, '-X', 'utf8', str(script), '--apply'],
                                    cwd=directory, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('files=1 items=1', result.stdout)
            self.assertEqual(path.read_bytes(), footer('').encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
