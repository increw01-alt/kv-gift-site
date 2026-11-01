"""Remove approved legacy <li> items from #general_tail without reserializing HTML.

Run from the repository root. The default is a read-only dry run; --apply writes
only changed files. UTF-8 bytes (including a BOM) and existing line endings outside
the removed <li> lines are preserved.
"""

import argparse
from dataclasses import dataclass, field
from html.parser import HTMLParser
import os
from pathlib import Path
import re


LEGACY_TITLES = frozenset((
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
))
EXCLUDED_DIRS = frozenset(('node_modules', 'output', 'img'))


@dataclass
class _Item:
    start: int
    text: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)


class _FooterItems(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.line_starts = [0] + [match.end() for match in re.finditer('\n', source)]
        self.footer_depth = 0
        self.items: list[_Item] = []
        self.captures: list[tuple[str, _Item, list[str]]] = []
        self.removals: list[tuple[int, int]] = []

    def _source_offset(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == 'footer':
            if self.footer_depth or dict(attrs).get('id') == 'general_tail':
                self.footer_depth += 1
        if not self.footer_depth:
            return
        if tag == 'li':
            self.items.append(_Item(self._source_offset()))
        elif tag in ('p', 'a') and self.items:
            self.captures.append((tag, self.items[-1], []))

    def handle_data(self, data):
        if self.items:
            self.items[-1].text.append(data)
        for _, _, parts in self.captures:
            parts.append(data)

    def handle_endtag(self, tag):
        if not self.footer_depth:
            return
        if tag in ('p', 'a'):
            for index in range(len(self.captures) - 1, -1, -1):
                if self.captures[index][0] == tag:
                    _, item, parts = self.captures.pop(index)
                    item.titles.append(''.join(parts).strip())
                    break
        elif tag == 'li' and self.items:
            item = self.items.pop()
            item.titles.append(''.join(item.text).strip())
            self.captures = [capture for capture in self.captures if capture[1] is not item]
            if any(title in LEGACY_TITLES for title in item.titles):
                end = self.source.index('>', self._source_offset()) + 1
                self.removals.append((item.start, end))
        elif tag == 'footer':
            self.footer_depth -= 1
            if not self.footer_depth:
                self.items.clear()
                self.captures.clear()


def strip_html(source: str) -> tuple[str, int]:
    """Return HTML and number of removed items; leave all other characters intact."""
    if not any(title in source for title in LEGACY_TITLES):
        return source, 0
    parser = _FooterItems(source)
    parser.feed(source)
    parser.close()
    parts = []
    cursor = 0
    count = 0
    spans = []
    for start, end in parser.removals:
        line_start = source.rfind('\n', 0, start) + 1
        line_end = source.find('\n', end)
        if line_end == -1:
            line_end = len(source)
        if (not source[line_start:start].strip(' \t\r')
                and not source[end:line_end].strip(' \t\r')):
            start = line_start
            end = min(line_end + 1, len(source))
        spans.append((start, end))
    for start, end in sorted(spans):
        if start < cursor:
            continue
        parts.append(source[cursor:start])
        cursor = end
        count += 1
    parts.append(source[cursor:])
    return ''.join(parts), count


def _html_files(root: Path) -> list[Path]:
    paths = set(root.glob('*.html'))
    paths.update((root / 'tools' / 'templates').glob('*.html'))
    paths.update((root / 'price').glob('*.html'))
    for folder in ('board', 'payment'):
        for current, dirs, files in os.walk(root / folder, followlinks=False):
            dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS
                       and not (Path(current) / name).is_symlink()]
            paths.update(Path(current) / name for name in files if name.endswith('.html'))
    return sorted(path for path in paths if path.is_file() and not path.is_symlink())


def strip_files(root: Path, *, apply: bool = False) -> tuple[int, int]:
    """Return (changed file count, removed item count), without writing by default."""
    changed_files = removed_items = 0
    for path in _html_files(Path(root)):
        original = path.read_bytes()
        cleaned, count = strip_html(original.decode('utf-8'))
        if count:
            changed_files += 1
            removed_items += count
            if apply:
                path.write_bytes(cleaned.encode('utf-8'))
    return changed_files, removed_items


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='report only (default)')
    mode.add_argument('--apply', action='store_true', help='write the cleaned HTML files')
    args = parser.parse_args()
    files, items = strip_files(Path.cwd(), apply=args.apply)
    print(f'{"apply" if args.apply else "dry-run"}: files={files} items={items}')


if __name__ == '__main__':
    main()
