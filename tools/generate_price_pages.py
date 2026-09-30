# -*- coding: utf-8 -*-
"""
상품권 시세 상세 페이지 생성기 (거래소 스타일)
- 데이터: 협회 실시간 rates.json(CORS 개방) + data/price-history.json + data/prices.json
- 실행: python tools/generate_price_pages.py  →  price/<slug>.html 생성
"""
import io
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DOMAIN = "https://kv-gift.co.kr"
RATES_URL = "https://koreagiftcard.co.kr/rates.json"

BRANDS = [
    dict(slug="shinsegae", brand="신세계", price_name="신세계 상품권", ticker="SHINSEGAE"),
    dict(slug="lotte", brand="롯데", price_name="롯데 상품권", ticker="LOTTE"),
    dict(slug="hyundai", brand="현대", price_name="현대 상품권", ticker="HYUNDAI"),
    dict(slug="galleria", brand="갤러리아", price_name="갤러리아 상품권", ticker="GALLERIA"),
    dict(slug="ak", brand="AK", price_name="AK 상품권", ticker="AK PLAZA"),
]
COMING = []


def load_shell():
    src = io.open(SITE / "faq.html", encoding="utf-8").read()
    header = src[:src.index('<div class="at-body"')]
    footer = src[src.index('<footer id="general_tail">'):]
    header = header.replace('src="img/', 'src="/img/')
    footer = footer.replace('src="img/', 'src="/img/')
    return header, footer


def page_head(header, title, desc, url, image=None):
    h = re.sub(r"<title>[^<]*</title>", f"<title>{title}</title>", header)
    if image:
        h = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf"\g<1>{image}\g<2>", h)
    h = re.sub(r'(<meta name="description" content=")[^"]*(")', rf"\g<1>{desc}\g<2>", h)
    h = re.sub(r'(<link rel="canonical" href=")[^"]*(")', rf"\g<1>{url}\g<2>", h)
    h = re.sub(r'(<meta property="og:url" content=")[^"]*(")', rf"\g<1>{url}\g<2>", h)
    h = re.sub(r'(<meta property="og:title" content=")[^"]*(")', rf"\g<1>{title}\g<2>", h)
    h = re.sub(r'(<meta property="og:description" content=")[^"]*(")', rf"\g<1>{desc}\g<2>", h)
    return h


# ===== 시안 A: 다크 거래소형 (주식 HTS 느낌) =====
CSS = """
<style>
:root{--px-bg:#0e1730;--px-card:#151f3d;--px-line:#26325a;--px-text:#eef2ff;--px-dim:#8b97c0;
--px-up:#f0426b;--px-down:#3e7bfa;--px-accent:var(--color-orange);}
#px_page{background:var(--px-bg);color:var(--px-text);padding-bottom:80px;margin-bottom:-30px;}
#px_page .wrap{width:calc(100% - 40px);max-width:1200px;margin:0 auto;}
#px_page a{color:inherit;}
/* 히어로 */
.px-hero{padding:45px 0 30px;background:linear-gradient(180deg,#101c3f 0%,var(--px-bg) 100%);border-bottom:1px solid var(--px-line);}
.px-crumb{font-size:12px;color:var(--px-dim);margin-bottom:18px;}
.px-crumb a{color:var(--px-dim);text-decoration:none;}
.px-crumb a:hover{color:var(--px-text);}
.px-name-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
.px-name-row h1{font-size:26px;font-weight:800;margin:0;color:var(--px-text);}
.px-ticker{font-size:11px;letter-spacing:2px;color:var(--px-dim);border:1px solid var(--px-line);padding:3px 8px;border-radius:4px;}
.px-live{display:flex;align-items:center;gap:6px;font-size:12px;color:#37e0a1;font-weight:bold;}
.px-live i{width:8px;height:8px;border-radius:50%;background:#37e0a1;animation:pxpulse 1.4s infinite;}
@keyframes pxpulse{0%{box-shadow:0 0 0 0 rgba(55,224,161,.6)}70%{box-shadow:0 0 0 8px rgba(55,224,161,0)}100%{box-shadow:0 0 0 0 rgba(55,224,161,0)}}
.px-big{display:flex;align-items:flex-end;gap:14px;margin:16px 0 6px;flex-wrap:wrap;}
.px-big b{font-size:44px;font-weight:800;line-height:1;font-family:'Pretendard',sans-serif;}
.px-big .diff{font-size:16px;font-weight:bold;padding-bottom:5px;}
.px-big .diff.up{color:var(--px-up);} .px-big .diff.down{color:var(--px-down);} .px-big .diff.flat{color:var(--px-dim);}
.px-sub{font-size:12px;color:var(--px-dim);}
/* 히어로 좌우 배치 + 상품권 실물 이미지 */
.px-hero-flex{display:flex;justify-content:space-between;align-items:center;gap:30px;}
.px-hero-left{min-width:0;}
.px-gift-img{max-width:320px;width:34%;border-radius:10px;transform:rotate(-4deg);
box-shadow:0 18px 45px rgba(0,0,0,.5),0 0 0 1px rgba(255,255,255,.08);transition:.3s;}
.px-gift-img:hover{transform:rotate(0deg) scale(1.03);}
@media(max-width:800px){.px-gift-img{display:none;}}
/* 브랜드 탭 */
.px-tabs{display:flex;gap:8px;margin-top:22px;flex-wrap:wrap;}
.px-tabs a,.px-tabs span{font-size:13px;padding:7px 16px;border:1px solid var(--px-line);border-radius:20px;text-decoration:none;color:var(--px-dim);}
.px-tabs a.on{background:var(--px-accent);border-color:var(--px-accent);color:#fff;font-weight:bold;}
.px-tabs a:hover{border-color:var(--px-accent);color:var(--px-text);}
.px-tabs span{opacity:.45;cursor:default;}
/* 요약 카드 */
.px-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px auto;}
.px-stat{background:var(--px-card);border:1px solid var(--px-line);border-radius:10px;padding:16px 18px;}
.px-stat p{font-size:12px;color:var(--px-dim);margin:0 0 8px;}
.px-stat b{font-size:20px;font-weight:800;}
.px-stat span{display:block;font-size:11px;color:var(--px-dim);margin-top:6px;}
@media(max-width:900px){.px-stats{grid-template-columns:repeat(2,1fr);}}
/* 섹션 공통 */
.px-sec{background:var(--px-card);border:1px solid var(--px-line);border-radius:10px;padding:20px;margin-bottom:26px;}
.px-sec-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.px-sec-title b{font-size:15px;}
.px-sec-title span{font-size:11px;color:var(--px-dim);}
.px-chart-box{position:relative;height:300px;}
.px-chart-note{text-align:center;font-size:12px;color:var(--px-dim);margin-top:10px;}
/* 호가 테이블 */
.px-quotes table{width:100%;border-collapse:collapse;font-size:13px;}
.px-quotes th{font-size:11px;color:var(--px-dim);font-weight:normal;text-align:right;padding:8px 10px;border-bottom:1px solid var(--px-line);}
.px-quotes th:first-child,.px-quotes td:first-child{text-align:left;}
.px-quotes td{padding:11px 10px;border-bottom:1px solid rgba(38,50,90,.5);text-align:right;font-family:'Pretendard',sans-serif;}
.px-quotes td:first-child{font-weight:bold;}
.px-quotes td .area{font-size:11px;color:var(--px-dim);font-weight:normal;margin-left:6px;}
.px-quotes tr.best td{background:rgba(240,66,107,.08);}
.px-quotes tr.best .buy{color:var(--px-up);font-weight:800;}
.px-quotes .buy{color:#ffb3c4;} .px-quotes .sell{color:#a9c4ff;}
.px-quotes .go a{font-size:11px;color:var(--px-accent);text-decoration:none;border:1px solid var(--px-line);padding:3px 8px;border-radius:4px;}
.px-quotes .badge-best{font-size:10px;background:var(--px-up);color:#fff;border-radius:3px;padding:1px 5px;margin-left:6px;vertical-align:2px;}
/* 액면가별 공시 */
.px-faces table{width:100%;border-collapse:collapse;font-size:13px;}
.px-faces th{font-size:11px;color:var(--px-dim);font-weight:normal;text-align:right;padding:8px 10px;border-bottom:1px solid var(--px-line);}
.px-faces td{padding:10px;border-bottom:1px solid rgba(38,50,90,.5);text-align:right;}
.px-faces th:first-child,.px-faces td:first-child{text-align:left;}
.px-faces td em{font-style:normal;font-size:11px;color:var(--px-dim);margin-left:4px;}
/* 하단 */
.px-note{font-size:11px;color:var(--px-dim);line-height:1.7;margin:20px 0;}
.px-actions{display:flex;gap:10px;flex-wrap:wrap;}
.px-actions a{flex:1;min-width:200px;text-align:center;padding:14px;border-radius:8px;font-size:14px;font-weight:bold;text-decoration:none;}
.px-actions a.buy-link{background:var(--px-accent);color:#fff;}
.px-actions a.sell-link{background:transparent;border:1px solid var(--px-accent);color:var(--px-accent);}
@media(max-width:600px){.px-big b{font-size:34px;}.px-quotes .area{display:none;}}
</style>"""

# ===== 시안 B: 라이트 클린형 (기존 사이트 톤과 이어지는 밝은 대시보드) =====
CSS_B = """
<style>
:root{--px-bg:#f4f6fb;--px-card:#ffffff;--px-line:#e4e8f1;--px-text:#111c3d;--px-dim:#7c86a3;
--px-up:#e5304f;--px-down:#2f6de0;--px-accent:var(--color-orange);}
#px_page{background:var(--px-bg);color:var(--px-text);padding-bottom:80px;margin-bottom:-30px;}
#px_page .wrap{width:calc(100% - 40px);max-width:1200px;margin:0 auto;}
#px_page a{color:inherit;}
.px-hero{padding:45px 0 30px;background:#fff;border-bottom:1px solid var(--px-line);}
.px-crumb{font-size:12px;color:var(--px-dim);margin-bottom:18px;}
.px-crumb a{color:var(--px-dim);text-decoration:none;}
.px-crumb a:hover{color:var(--px-text);}
.px-name-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
.px-name-row h1{font-size:26px;font-weight:800;margin:0;color:var(--px-text);}
.px-ticker{font-size:11px;letter-spacing:2px;color:var(--px-dim);border:1px solid var(--px-line);padding:3px 8px;border-radius:4px;background:#f8f9fc;}
.px-live{display:flex;align-items:center;gap:6px;font-size:12px;color:#0aa870;font-weight:bold;}
.px-live i{width:8px;height:8px;border-radius:50%;background:#0aa870;animation:pxpulse 1.4s infinite;}
@keyframes pxpulse{0%{box-shadow:0 0 0 0 rgba(10,168,112,.5)}70%{box-shadow:0 0 0 8px rgba(10,168,112,0)}100%{box-shadow:0 0 0 0 rgba(10,168,112,0)}}
.px-big{display:flex;align-items:flex-end;gap:14px;margin:16px 0 6px;flex-wrap:wrap;}
.px-big b{font-size:44px;font-weight:800;line-height:1;}
.px-big .diff{font-size:16px;font-weight:bold;padding-bottom:5px;}
.px-big .diff.up{color:var(--px-up);} .px-big .diff.down{color:var(--px-down);} .px-big .diff.flat{color:var(--px-dim);}
.px-sub{font-size:12px;color:var(--px-dim);}
.px-tabs{display:flex;gap:8px;margin-top:22px;flex-wrap:wrap;}
.px-tabs a,.px-tabs span{font-size:13px;padding:7px 16px;border:1px solid var(--px-line);border-radius:20px;text-decoration:none;color:var(--px-dim);background:#fff;}
.px-tabs a.on{background:var(--px-accent);border-color:var(--px-accent);color:#fff;font-weight:bold;}
.px-tabs a:hover{border-color:var(--px-accent);color:var(--px-accent);}
.px-tabs span{opacity:.5;cursor:default;}
.px-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px auto;}
.px-stat{background:var(--px-card);border:1px solid var(--px-line);border-radius:10px;padding:16px 18px;box-shadow:0 1px 4px rgba(17,28,61,.05);}
.px-stat p{font-size:12px;color:var(--px-dim);margin:0 0 8px;}
.px-stat b{font-size:20px;font-weight:800;}
.px-stat span{display:block;font-size:11px;color:var(--px-dim);margin-top:6px;}
@media(max-width:900px){.px-stats{grid-template-columns:repeat(2,1fr);}}
.px-sec{background:var(--px-card);border:1px solid var(--px-line);border-radius:10px;padding:20px;margin-bottom:26px;box-shadow:0 1px 4px rgba(17,28,61,.05);}
.px-sec-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.px-sec-title b{font-size:15px;}
.px-sec-title span{font-size:11px;color:var(--px-dim);}
.px-chart-box{position:relative;height:300px;}
.px-chart-note{text-align:center;font-size:12px;color:var(--px-dim);margin-top:10px;}
.px-quotes table{width:100%;border-collapse:collapse;font-size:13px;}
.px-quotes th{font-size:11px;color:var(--px-dim);font-weight:normal;text-align:right;padding:8px 10px;border-bottom:1px solid var(--px-line);}
.px-quotes th:first-child,.px-quotes td:first-child{text-align:left;}
.px-quotes td{padding:11px 10px;border-bottom:1px solid #f0f2f8;text-align:right;}
.px-quotes td:first-child{font-weight:bold;}
.px-quotes td .area{font-size:11px;color:var(--px-dim);font-weight:normal;margin-left:6px;}
.px-quotes tr.best td{background:#fff5f7;}
.px-quotes tr.best .buy{color:var(--px-up);font-weight:800;}
.px-quotes .buy{color:var(--px-up);} .px-quotes .sell{color:var(--px-down);}
.px-quotes .go a{font-size:11px;color:var(--px-accent);text-decoration:none;border:1px solid var(--px-line);padding:3px 8px;border-radius:4px;}
.px-quotes .badge-best{font-size:10px;background:var(--px-up);color:#fff;border-radius:3px;padding:1px 5px;margin-left:6px;vertical-align:2px;}
.px-faces table{width:100%;border-collapse:collapse;font-size:13px;}
.px-faces th{font-size:11px;color:var(--px-dim);font-weight:normal;text-align:right;padding:8px 10px;border-bottom:1px solid var(--px-line);}
.px-faces td{padding:10px;border-bottom:1px solid #f0f2f8;text-align:right;}
.px-faces th:first-child,.px-faces td:first-child{text-align:left;}
.px-faces td em{font-style:normal;font-size:11px;color:var(--px-dim);margin-left:4px;}
.px-note{font-size:11px;color:var(--px-dim);line-height:1.7;margin:20px 0;}
.px-actions{display:flex;gap:10px;flex-wrap:wrap;}
.px-actions a{flex:1;min-width:200px;text-align:center;padding:14px;border-radius:8px;font-size:14px;font-weight:bold;text-decoration:none;}
.px-actions a.buy-link{background:var(--px-accent);color:#fff;}
.px-actions a.sell-link{background:#fff;border:1px solid var(--px-accent);color:var(--px-accent);}
@media(max-width:600px){.px-big b{font-size:34px;}.px-quotes .area{display:none;}}
</style>"""

# ===== 시안 C: 증권 앱형 (토스·네이버증권 느낌 — 그라데이션 카드, 둥근 모서리) =====
CSS_C = """
<style>
:root{--px-bg:#ffffff;--px-card:#f9fafc;--px-line:#eef0f5;--px-text:#191f28;--px-dim:#8b95a1;
--px-up:#f04452;--px-down:#3182f6;--px-accent:var(--color-orange);}
#px_page{background:var(--px-bg);color:var(--px-text);padding-bottom:80px;margin-bottom:-30px;}
#px_page .wrap{width:calc(100% - 40px);max-width:1200px;margin:0 auto;}
#px_page a{color:inherit;}
.px-hero{padding:30px 0 10px;background:transparent;border:0;}
.px-hero>.wrap{background:linear-gradient(135deg,#1a264c 0%,#2e3f7f 60%,#c8571b 130%);border-radius:24px;padding:34px 34px 30px;color:#fff;box-shadow:0 10px 30px rgba(26,38,76,.25);}
.px-crumb{font-size:12px;color:rgba(255,255,255,.55);margin-bottom:18px;}
.px-crumb a{color:rgba(255,255,255,.55);text-decoration:none;}
.px-crumb a:hover{color:#fff;}
.px-name-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
.px-name-row h1{font-size:24px;font-weight:800;margin:0;color:#fff;}
.px-ticker{font-size:11px;letter-spacing:2px;color:rgba(255,255,255,.6);border:1px solid rgba(255,255,255,.25);padding:3px 8px;border-radius:20px;}
.px-live{display:flex;align-items:center;gap:6px;font-size:12px;color:#4ff0b3;font-weight:bold;}
.px-live i{width:8px;height:8px;border-radius:50%;background:#4ff0b3;animation:pxpulse 1.4s infinite;}
@keyframes pxpulse{0%{box-shadow:0 0 0 0 rgba(79,240,179,.6)}70%{box-shadow:0 0 0 8px rgba(79,240,179,0)}100%{box-shadow:0 0 0 0 rgba(79,240,179,0)}}
.px-hero .px-sub{color:rgba(255,255,255,.6);}
.px-big{display:flex;align-items:flex-end;gap:14px;margin:14px 0 8px;flex-wrap:wrap;}
.px-big b{font-size:50px;font-weight:800;line-height:1;color:#fff;}
.px-big .diff{font-size:14px;font-weight:bold;padding:5px 12px;border-radius:20px;margin-bottom:4px;}
.px-big .diff.up{color:#fff;background:rgba(240,68,82,.85);} .px-big .diff.down{color:#fff;background:rgba(49,130,246,.85);} .px-big .diff.flat{color:rgba(255,255,255,.75);background:rgba(255,255,255,.15);}
.px-sub{font-size:12px;color:var(--px-dim);}
.px-tabs{display:flex;gap:8px;margin-top:24px;flex-wrap:wrap;}
.px-tabs a,.px-tabs span{font-size:13px;padding:8px 18px;border-radius:22px;text-decoration:none;color:rgba(255,255,255,.7);background:rgba(255,255,255,.12);border:0;}
.px-tabs a.on{background:#fff;color:#1a264c;font-weight:800;}
.px-tabs a:hover{background:rgba(255,255,255,.25);color:#fff;}
.px-tabs span{opacity:.4;cursor:default;}
.px-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:26px auto;}
.px-stat{background:var(--px-card);border:0;border-radius:18px;padding:18px 20px;}
.px-stat p{font-size:12px;color:var(--px-dim);margin:0 0 8px;}
.px-stat b{font-size:21px;font-weight:800;}
.px-stat span{display:block;font-size:11px;color:var(--px-dim);margin-top:6px;}
@media(max-width:900px){.px-stats{grid-template-columns:repeat(2,1fr);}}
.px-sec{background:#fff;border:1px solid var(--px-line);border-radius:20px;padding:24px;margin-bottom:22px;box-shadow:0 4px 16px rgba(25,31,40,.04);}
.px-sec-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.px-sec-title b{font-size:16px;}
.px-sec-title span{font-size:11px;color:var(--px-dim);}
.px-chart-box{position:relative;height:300px;}
.px-chart-note{text-align:center;font-size:12px;color:var(--px-dim);margin-top:10px;}
.px-quotes table{width:100%;border-collapse:collapse;font-size:14px;}
.px-quotes th{font-size:11px;color:var(--px-dim);font-weight:normal;text-align:right;padding:8px 12px;border-bottom:1px solid var(--px-line);}
.px-quotes th:first-child,.px-quotes td:first-child{text-align:left;}
.px-quotes td{padding:14px 12px;border-bottom:1px solid #f4f6f9;text-align:right;}
.px-quotes td:first-child{font-weight:bold;}
.px-quotes td .area{font-size:11px;color:var(--px-dim);font-weight:normal;margin-left:6px;}
.px-quotes tr.best td{background:#fff6f7;}
.px-quotes tr.best .buy{color:var(--px-up);font-weight:800;}
.px-quotes .buy{color:var(--px-up);font-weight:600;} .px-quotes .sell{color:var(--px-down);font-weight:600;}
.px-quotes .go a{font-size:11px;color:#fff;background:#191f28;text-decoration:none;padding:5px 12px;border-radius:14px;}
.px-quotes .badge-best{font-size:10px;background:var(--px-up);color:#fff;border-radius:10px;padding:2px 7px;margin-left:6px;vertical-align:2px;}
.px-faces table{width:100%;border-collapse:collapse;font-size:14px;}
.px-faces th{font-size:11px;color:var(--px-dim);font-weight:normal;text-align:right;padding:8px 12px;border-bottom:1px solid var(--px-line);}
.px-faces td{padding:12px;border-bottom:1px solid #f4f6f9;text-align:right;}
.px-faces th:first-child,.px-faces td:first-child{text-align:left;}
.px-faces td em{font-style:normal;font-size:11px;color:var(--px-dim);margin-left:4px;}
.px-note{font-size:11px;color:var(--px-dim);line-height:1.7;margin:20px 0;}
.px-actions{display:flex;gap:12px;flex-wrap:wrap;}
.px-actions a{flex:1;min-width:200px;text-align:center;padding:16px;border-radius:16px;font-size:14px;font-weight:800;text-decoration:none;}
.px-actions a.buy-link{background:var(--px-accent);color:#fff;box-shadow:0 6px 16px rgba(230,90,20,.3);}
.px-actions a.sell-link{background:#f2f4f8;color:#191f28;}
@media(max-width:600px){.px-big b{font-size:38px;}.px-quotes .area{display:none;}.px-hero>.wrap{padding:26px 22px;}}
</style>"""


def render_page(header, footer, cfg, css=None, banner="", noindex=False):
    brand, slug, ticker, price_name = cfg["brand"], cfg["slug"], cfg["ticker"], cfg["price_name"]
    css = css or CSS
    gift_img = f"/img/price/{cfg['slug'] if not cfg['slug'].startswith('sample') else 'shinsegae'}.png"
    url = f"{DOMAIN}/price/{slug}"
    title = cfg.get("title") or f"{price_name} 실시간 시세 | 한국상품권거래소"
    desc = f"{price_name} 오늘 매입가·판매가 실시간 시세와 추이 그래프, 거래소 인증 업체별 호가를 한눈에 확인하세요."
    head = page_head(header, title, desc, url, image=DOMAIN + gift_img)
    if noindex:
        head = head.replace("</title>", "</title>\n<meta name=\"robots\" content=\"noindex\">")

    tabs = ""
    for b in BRANDS:
        cls = ' class="on"' if b["slug"] == slug else ""
        tabs += f'<a href="/price/{b["slug"]}.html"{cls}>{b["brand"]}</a>'
    for c in COMING:
        tabs += f'<span title="준비중">{c["brand"]}</span>'

    body = f'''<div class="at-body" style="width:100%">{css}
<div id="px_page">{banner}
	<div class="px-hero"><div class="wrap">
		<p class="px-crumb"><a href="/">홈</a> &rsaquo; <a href="/#price">상품권 시세</a> &rsaquo; {price_name}</p>
		<div class="px-hero-flex">
			<div class="px-hero-left">
				<div class="px-name-row">
					<h1>{price_name}</h1>
					<span class="px-ticker">{ticker} · 10만원권</span>
					<span class="px-live" id="px_live" style="display:none"><i></i>LIVE</span>
				</div>
				<p class="px-sub" style="margin:14px 0 0">최고 매입가 (내가 팔 때 받는 금액)</p>
				<div class="px-big">
					<b id="px_price">-</b>
					<span class="diff flat" id="px_diff">시세 불러오는 중…</span>
				</div>
				<p class="px-sub" id="px_updated">한국상품권협회 실시간 집계 기준</p>
			</div>
			<img class="px-gift-img" src="{gift_img}" alt="{price_name} 실물 이미지">
		</div>
		<div class="px-tabs">{tabs}</div>
	</div></div>
	<div class="wrap">
		<div class="px-stats">
			<div class="px-stat"><p>최고 매입가 <em style="font-style:normal;color:var(--px-up)">내가 팔 때</em></p><b id="st_buy">-</b><span id="st_buy_shop"></span></div>
			<div class="px-stat"><p>최저 판매가 <em style="font-style:normal;color:var(--px-down)">내가 살 때</em></p><b id="st_sell">-</b><span id="st_sell_shop"></span></div>
			<div class="px-stat"><p>매입·판매 스프레드</p><b id="st_spread">-</b><span>가격차</span></div>
			<div class="px-stat"><p>액면가 대비 할인율</p><b id="st_rate">-</b><span>10만원권 매입 기준</span></div>
		</div>
		<div class="px-sec">
			<div class="px-sec-title"><b>📈 시세 추이</b><span>한국상품권협회 · 매시간 자동 수집</span></div>
			<div class="px-chart-box"><canvas id="px_chart"></canvas></div>
			<p class="px-chart-note" id="px_chart_note"></p>
		</div>
		<div class="px-sec px-quotes">
			<div class="px-sec-title"><b>🏛 거래소 인증 업체 호가</b><span id="q_updated"></span></div>
			<table><thead><tr><th>업체</th><th>매입가 (내가 팔때)</th><th>판매가 (내가 살때)</th><th class="go"></th></tr></thead>
			<tbody id="px_quote_rows"><tr><td colspan="4" style="text-align:center;color:var(--px-dim);padding:30px">호가 불러오는 중…</td></tr></tbody></table>
		</div>
		<div class="px-sec px-faces">
			<div class="px-sec-title"><b>💳 액면가별 공시가</b><span>한국상품권거래소 공시 기준</span></div>
			<table><thead><tr><th>액면가</th><th>매입가</th><th>판매가</th></tr></thead>
			<tbody id="px_face_rows"></tbody></table>
		</div>
		<div class="px-actions">
			<a class="buy-link" href="/board/purchase/?sca=백화점">이 상품권 구매 문의 게시판 →</a>
			<a class="sell-link" href="/board/sale/?sca=백화점">보유 상품권 판매 문의 게시판 →</a>
		</div>
		<p class="px-note" id="px_note">※ 시세는 각 업체가 공시한 값을 집계한 참고 정보이며, 실제 거래 가격은 수량·권종·상품권 상태에 따라 다를 수 있습니다.</p>
	</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js"></script>
<script>
(function () {{
	var BRAND = "{brand}", PRICE_NAME = "{price_name}";
	var won = function (n) {{ return Number(n).toLocaleString("ko-KR") + "원"; }};

	/* ---- 실시간 시세 (협회 rates.json, CORS 개방) ---- */
	fetch("https://koreagiftcard.co.kr/rates.json", {{ cache: "no-store" }})
		.then(function (r) {{ return r.json(); }})
		.then(function (d) {{
			var s = (d.summary || []).filter(function (x) {{ return x.brand === BRAND; }})[0];
			if (!s) return;
			document.getElementById("px_live").style.display = "flex";
			document.getElementById("px_price").textContent = won(s.bestBuy.price);
			document.getElementById("px_updated").textContent = "갱신 " + d.updated_at + " · 한국상품권협회 실시간 집계 · 10만원권 기준";
			document.getElementById("st_buy").textContent = won(s.bestBuy.price);
			document.getElementById("st_buy_shop").textContent = s.bestBuy.shop + " · 할인율 " + s.bestBuy.rate + "%";
			document.getElementById("st_sell").textContent = won(s.bestSell.price);
			document.getElementById("st_sell_shop").textContent = s.bestSell.shop + " · 할인율 " + s.bestSell.rate + "%";
			document.getElementById("st_spread").textContent = won(Math.abs(s.bestSell.price - s.bestBuy.price));
			document.getElementById("st_rate").textContent = s.bestBuy.rate + "%";
			document.getElementById("q_updated").textContent = "갱신 " + d.updated_at;
			if (d.note) document.getElementById("px_note").textContent = "※ " + d.note;

			/* 업체별 호가 (매입가 내림차순, 최고가 하이라이트) */
			var rows = [];
			(d.shops || []).forEach(function (shop) {{
				(shop.rows || []).forEach(function (r) {{
					if (r.brand === BRAND) rows.push({{ name: shop.name, area: shop.area || "", url: shop.url || "", buy: r.buy, sell: r.sell }});
				}});
			}});
			rows.sort(function (a, b) {{ return b.buy - a.buy; }});
			document.getElementById("px_quote_rows").innerHTML = rows.map(function (r, i) {{
				var best = i === 0 ? ' class="best"' : "";
				var badge = i === 0 ? '<span class="badge-best">최고매입</span>' : "";
				var go = r.url ? '<a href="' + r.url + '" target="_blank" rel="noopener nofollow">홈페이지</a>' : "";
				return "<tr" + best + "><td>" + r.name + badge + '<span class="area">' + r.area + "</span></td>" +
					'<td class="buy">' + won(r.buy) + "</td><td class=\\"sell\\">" + won(r.sell) + "</td>" +
					'<td class="go">' + go + "</td></tr>";
			}}).join("");
		}})
		.catch(function () {{
			document.getElementById("px_diff").textContent = "실시간 시세 연결 실패 — 아래 공시가를 참고하세요";
		}});

	/* ---- 시세 추이 그래프 (협회 축적 히스토리 — 2026-09-16부터 매시간 수집) ---- */
	fetch("https://koreagiftcard.co.kr/rates_market_history.json", {{ cache: "no-store" }})
		.then(function (r) {{ return r.json(); }})
		.then(function (h) {{
			var pts = (h.points || []).filter(function (p) {{ return typeof p[BRAND] === "number"; }});
			var labels = pts.map(function (p) {{ return p.t.slice(5); }});
			var buys = pts.map(function (p) {{ return p[BRAND]; }});
			/* 직전 기록 대비 등락 */
			var diffEl = document.getElementById("px_diff");
			if (buys.length >= 2) {{
				var prev = buys[buys.length - 2], d = buys[buys.length - 1] - prev;
				var pct = (d / prev * 100).toFixed(2);
				diffEl.className = "diff " + (d > 0 ? "up" : d < 0 ? "down" : "flat");
				diffEl.textContent = (d > 0 ? "▲ +" : d < 0 ? "▼ -" : "— ") + Math.abs(d).toLocaleString() + "원 (" + (d >= 0 ? "+" : "") + pct + "%)";
			}} else {{
				diffEl.className = "diff flat";
				diffEl.textContent = "";
			}}
			document.getElementById("px_chart_note").textContent =
				"한국상품권협회가 " + (pts.length ? pts[0].t.slice(0, 10) : "") + "부터 수집한 최고 매입가 추이입니다.";
			new Chart(document.getElementById("px_chart"), {{
				type: "line",
				data: {{ labels: labels, datasets: [
					{{ label: "최고 매입가", data: buys, borderColor: "#f0426b", backgroundColor: "rgba(240,66,107,.12)", fill: true, tension: .3, pointRadius: 0, pointHitRadius: 8, borderWidth: 2 }}
				] }},
				options: {{
					responsive: true, maintainAspectRatio: false,
					interaction: {{ mode: "index", intersect: false }},
					plugins: {{ legend: {{ display: false }},
						tooltip: {{ callbacks: {{ label: function (c) {{ return "최고 매입가: " + won(c.parsed.y); }} }} }} }},
					scales: {{
						x: {{ ticks: {{ color: "#8b97c0", maxTicksLimit: 8 }}, grid: {{ color: "rgba(38,50,90,.4)" }} }},
						y: {{ ticks: {{ color: "#8b97c0", callback: function (v) {{ return v.toLocaleString(); }} }}, grid: {{ color: "rgba(38,50,90,.4)" }} }}
					}}
				}}
			}});
		}});

	/* ---- 액면가별 공시가 (거래소 자체 데이터) ---- */
	fetch("/data/prices.json")
		.then(function (r) {{ return r.json(); }})
		.then(function (d) {{
			var rows = (d.paper || []).filter(function (r) {{ return r.name === PRICE_NAME; }});
			document.getElementById("px_face_rows").innerHTML = rows.map(function (r) {{
				return "<tr><td>" + r.face + "원권</td><td>" + r.buy + "원<em>" + r.buy_rate + "</em></td><td>" + r.sell + "원<em>" + r.sell_rate + "</em></td></tr>";
			}}).join("") || '<tr><td colspan="3" style="text-align:center;color:var(--px-dim)">공시 데이터 없음</td></tr>';
		}});
}})();
</script>
</div>'''
    return head + body + footer


SAMPLES = [
    ("a", "다크 거래소형", None),      # None → 기본 CSS(시안 A)
    ("b", "라이트 클린형", "CSS_B"),
    ("c", "증권 앱형", "CSS_C"),
]


def sample_banner(current):
    links = ""
    for letter, label, _ in SAMPLES:
        style = ("background:#1a264c;color:#fff;" if letter == current
                 else "background:#fff;color:#1a264c;border:1px solid #d8c9a0;")
        links += (f'<a href="/price/sample-{letter}.html" style="{style}'
                  f'padding:6px 14px;border-radius:16px;text-decoration:none;'
                  f'font-size:12px;font-weight:bold;margin-left:8px;">'
                  f'{letter.upper()} {label}</a>')
    return ('<div style="background:#fff7e0;color:#6b4e00;font-size:12px;'
            'padding:10px 20px;text-align:center;">🎨 디자인 시안 비교 (검토용 페이지)'
            + links + "</div>")


def main():
    header, footer = load_shell()
    out = SITE / "price"
    out.mkdir(exist_ok=True)
    # 브랜드별 실제 페이지 (현재 시안 A 적용 — 시안 확정 시 교체)
    for cfg in BRANDS:
        io.open(out / f"{cfg['slug']}.html", "w", encoding="utf-8", newline="\n").write(
            render_page(header, footer, cfg))
        print(f"price/{cfg['slug']}.html 생성")
    # 디자인 시안 A 확정(2026-09-30) — 샘플 페이지는 더 이상 생성하지 않음
    for f in out.glob("sample-*.html"):
        f.unlink()
        print(f"{f.name} 삭제 (시안 확정)")


if __name__ == "__main__":
    main()
