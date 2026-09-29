# -*- coding: utf-8 -*-
"""전체 페이지의 게시판 메뉴/더보기 링크를 내부 정적 게시판(/board/...)으로 교체
   원본 사이트와 동일한 매핑: 구매→purchase, 판매→sale, 자유→free, 일반상식→sense,
   상품권 정보→gc_information, TIP→gc_tip, 협회 소식→gc_word, 공지→general_notice
   (상품권카페→네이버카페, 상품권뉴스→vipvip 는 원본도 외부링크라 유지)"""
import glob
import io
import os
import re

os.chdir(os.path.join(os.path.dirname(__file__), ".."))

NAV_MAP = [
    ("상품권 구매게시판", "/board/purchase/"),
    ("상품권 판매게시판", "/board/sale/"),
    ("자유게시판", "/board/free/"),
    ("일반상식", "/board/sense/"),
    ("상품권 정보", "/board/gc_information/"),
    ("상품권TIP", "/board/gc_tip/"),
    ("한국상품권협회 소식", "/board/gc_word/"),
]

for path in sorted(glob.glob("*.html")):
    src = io.open(path, encoding="utf-8").read()
    orig = src

    # 메뉴 (span/li 공통): 라벨 기준으로 onclick 교체
    for label, url in NAV_MAP:
        src = re.sub(
            r'onclick="(?:window\.open|location\.href=)\(?\'[^\']*\'\)?;?"([^>]*)>' + re.escape(label) + r'<',
            f'onclick="location.href=\'{url}\';"\\1>{label}<', src)

    # 고객센터 > 공지사항 (메뉴)
    src = src.replace("onclick=\"location.href='/#notice';\">공지사항<",
                      "onclick=\"location.href='/board/general_notice/';\">공지사항<")

    if path == "index.html":
        # 메인 상단 공지 스트립
        src = src.replace("onclick=\"location.href='#notice';\">\n            <b>공지사항</b>",
                          "onclick=\"location.href='/board/general_notice/';\">\n            <b>공지사항</b>")
        # 게시판 요약 더보기: board1 left(구매)/right(판매)
        src = src.replace('<div class="flex" onclick="window.open(\'https://cafe.naver.com/koreagiftclub\');">\n\t\t\t\t\t\t\t\t<p>더보기</p>',
                          '<div class="flex" data-more="purchase">\n\t\t\t\t\t\t\t\t<p>더보기</p>', 1)
        src = src.replace('<div class="flex" onclick="window.open(\'https://cafe.naver.com/koreagiftclub\');">\n\t\t\t\t\t\t\t\t<p>더보기</p>',
                          '<div class="flex" data-more="sale">\n\t\t\t\t\t\t\t\t<p>더보기</p>', 1)
        # board2: 자유게시판/상품권Tip/공지 more 버튼
        src = src.replace('<div class="more_btn" onclick="window.open(\'https://cafe.naver.com/koreagiftclub\');">',
                          '<div class="more_btn" onclick="location.href=\'/board/free/\';">', 1)
        src = src.replace('<div class="more_btn" onclick="window.open(\'http://www.vipvip.or.kr\');">',
                          '<div class="more_btn" onclick="location.href=\'/board/gc_tip/\';">', 1)
        src = src.replace('<div class="more_btn" onclick="location.href=\'#notice\';">',
                          '<div class="more_btn" onclick="location.href=\'/board/general_notice/\';">', 1)

    if src != orig:
        io.open(path, "w", encoding="utf-8", newline="\n").write(src)
        print(f"{path}: 수정됨")
    else:
        print(f"{path}: 변경 없음")
