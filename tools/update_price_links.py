# -*- coding: utf-8 -*-
"""상품권 시세 메뉴를 새 시세 페이지(/price/)로 연결 + 메인 시세 섹션에 전체시세 링크"""
import glob
import io
import os

os.chdir(os.path.join(os.path.dirname(__file__), ".."))

for path in sorted(glob.glob("*.html")):
    src = io.open(path, encoding="utf-8").read()
    orig = src

    # 메뉴: 지류/모바일 → 시세 페이지의 해당 표 앵커로
    src = src.replace("onclick=\"location.href='/#price';\">지류(종이) 상품권<",
                      "onclick=\"location.href='/price/#paper';\">지류(종이) 상품권<")
    src = src.replace("onclick=\"location.href='/#price';\">모바일상품권<",
                      "onclick=\"location.href='/price/#mobile';\">모바일상품권<")
    src = src.replace("onclick=\"location.href='/#price';\">모바일 상품권<",
                      "onclick=\"location.href='/price/#mobile';\">모바일 상품권<")

    if path == "index.html":
        # 메인 시세표 제목 → 시세 페이지로 이동 + "전체 시세" 안내
        src = src.replace(
            '<b  style="cursor:pointer;">지류(종이) 상품권 시세</b>',
            '<b style="cursor:pointer;" onclick="location.href=\'/price/#paper\';">지류(종이) 상품권 시세 <span style="font-size:12px;color:var(--color-orange);font-weight:normal">실시간 전체시세 ›</span></b>')
        src = src.replace(
            '<b  style="cursor:pointer;">모바일 상품권 시세</b>',
            '<b style="cursor:pointer;" onclick="location.href=\'/price/#mobile\';">모바일 상품권 시세 <span style="font-size:12px;color:var(--color-orange);font-weight:normal">실시간 전체시세 ›</span></b>')
        # 브라우저 캐시 무효화 (실시간 반영 스크립트 즉시 적용)
        src = src.replace('src="/js/main.js"', 'src="/js/main.js?v=20260930"')

    if src != orig:
        io.open(path, "w", encoding="utf-8", newline="\n").write(src)
        print(f"{path}: 수정됨")
