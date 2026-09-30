# -*- coding: utf-8 -*-
"""
정적 게시판 생성기 — kv-gift-crawl 수집 데이터로 /board/ 이하 페이지 생성

입력:  ../kv-gift-crawl/data/<게시판>.json  (글 본문·댓글·이미지)
       ../kv-gift-crawl/data/list_meta.json (번호·분류·조회수·댓글수)
       ../kv-gift-crawl/images/<게시판>/    (본문 이미지 원본)
출력:  board/<게시판>/index.html            (목록 — list.json 기반 JS 렌더링)
       board/<게시판>/<wr_id>.html          (글 본문 — 완전 정적, SEO용)
       board/<게시판>/list.json             (목록 데이터)
       board-img/<게시판>/                  (본문 이미지)
       data/latest_posts.json               (메인 화면 최근 글 요약)
       sitemap-boards.xml                   (게시판 전체 URL)

실행:  kv-gift-site 폴더에서  python tools/generate_boards.py
"""
import html as html_mod
import io
import json
import os
import re
import shutil
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

SITE = Path(__file__).resolve().parent.parent
CRAWL = SITE.parent / "kv-gift-crawl"
DOMAIN = "https://kv-gift.co.kr"

BOARDS = {
    "purchase": dict(name="상품권 구매게시판", sub="모든 상품권 구매는 상품권 구매게시판에서 거래되고 있습니다.",
                     skin="purchase-sale", bg="/img/purchase_bg.jpg", layout="table", has_cat=True),
    "sale": dict(name="상품권 판매게시판", sub="모든 상품권 판매는 상품권 판매게시판에서 거래되고 있습니다.",
                 skin="purchase-sale", bg="/img/sale_bg.jpg", layout="table", has_cat=True),
    "free": dict(name="자유게시판", sub="한국상품권거래소 회원분들이 자유롭게 소통하는 공간입니다.",
                 skin="free", bg="/img/free_bg.jpg", layout="table", has_cat=False),
    "sense": dict(name="일반상식", sub="한국상품권거래소 회원분들이 알고계시는 여러가지 상식들로 소통하는 공간입니다.",
                  skin="free", bg="/img/free_bg.jpg", layout="table", has_cat=False),
    "general_notice": dict(name="공지사항", sub="한국상품권거래소의 최근 소식들을 확인해보세요.",
                           skin="notice", bg="/img/notice_bg.jpg", layout="card", has_cat=False),
    "gc_tip": dict(name="상품권 TIP", sub="한국상품권거래소에서 알고있는 모든 상품권 TIP을 회원분들께 공유합니다.",
                   skin="notice", bg="/img/notice_bg.jpg", layout="card", has_cat=False),
    "gc_word": dict(name="한국상품권협회 소식", sub="한국상품권협회의 근황을 회원분들에게 알려드립니다.",
                    skin="notice", bg="/img/notice_bg.jpg", layout="card", has_cat=False),
    "gc_information": dict(name="상품권 정보", sub="한국상품권거래소에서 알고있는 모든 상품권 정보를 회원분들께 공유합니다.",
                           skin="notice", bg="/img/notice_bg.jpg", layout="card", has_cat=False),
}

# 분류 버튼 아이콘 (원본 목록 페이지 순서)
CAT_ICONS = ["area_all_icon.svg", "area1_icon.svg", "area2_icon.svg", "area3_icon.svg",
             "area4_icon.svg", "area5_icon.svg", "area6_icon.svg", "area7_icon.svg",
             "area8_icon.svg", "area9_icon.svg", "area10_icon.svg", "area11_icon.svg",
             "area12_icon.svg", "area13_icon.svg"]
CAT_ORDER = ["백화점", "국민관광", "농협", "홈플러스", "주유", "컬쳐랜드", "해피머니",
             "온라인문화", "북앤라이프", "구글기프트", "에그머니", "틴캐시", "외식", "기타"]

# 메인 하단 추천 쇼핑몰 (index premium_slide 와 동일)
SHOPS = [("플러스문", "https://www.plusmoon.co.kr/"), ("◆플러스24◆", "https://plus24.or.kr/"),
         ("플러스유", "https://plusyou.co.kr/"), ("▶모아핀◀", "https://moapin.co.kr"),
         ("◆백화할부◆", "https://gift-tech.co.kr/")]


def esc(s):
    return html_mod.escape(str(s), quote=True)


# ---------- 셸(헤더/푸터) ----------
def load_shell():
    src = io.open(SITE / "faq.html", encoding="utf-8").read()
    header = src[:src.index('<div class="at-body"')]
    footer = src[src.index('<footer id="general_tail">'):]
    # 게시판 페이지는 /board/<bo>/ 하위라 상대경로 이미지가 깨짐 → 절대경로화
    header = header.replace('src="img/', 'src="/img/')
    footer = footer.replace('src="img/', 'src="/img/')
    return header, footer


def page_head(header, title, desc, url, image=None):
    h = re.sub(r"<title>[^<]*</title>", f"<title>{esc(title)}</title>", header)
    h = re.sub(r'(<meta name="description" content=")[^"]*(")', rf"\g<1>{esc(desc)}\g<2>", h)
    h = re.sub(r'(<link rel="canonical" href=")[^"]*(")', rf"\g<1>{url}\g<2>", h)
    h = re.sub(r'(<meta property="og:url" content=")[^"]*(")', rf"\g<1>{url}\g<2>", h)
    h = re.sub(r'(<meta property="og:title" content=")[^"]*(")', rf"\g<1>{esc(title)}\g<2>", h)
    h = re.sub(r'(<meta property="og:description" content=")[^"]*(")', rf"\g<1>{esc(desc)}\g<2>", h)
    if image:
        h = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf"\g<1>{image}\g<2>", h)
    return h


def iso_date(d):
    """'26.09.05' → '2026-09-05' (형식이 다르면 None)"""
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", d or "")
    return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


# ---------- 본문 정리 ----------
def build_image_map(bo):
    m = {}
    d = CRAWL / "images" / bo
    if d.is_dir():
        for f in d.iterdir():
            m[f.name] = f.name
    return m


def norm_img_name(url):
    base = os.path.basename(urllib.parse.urlparse(url).path)
    base = re.sub(r"^thumb-", "", base)
    base = re.sub(r"_\d+x\d+(?=\.\w+$)", "", base)
    return base


def clean_content(content_html, bo, img_map, stats):
    soup = BeautifulSoup(content_html, "html.parser")
    # 보안: 스크립트류 제거
    for tag in soup.find_all(["script", "iframe", "embed", "object", "form"]):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on") or (
                    attr.lower() in ("href", "src") and str(tag.get(attr, "")).strip().lower().startswith("javascript:")):
                del tag[attr]
    # 이미지 로컬화
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        name = norm_img_name(src)
        if name in img_map:
            img["src"] = f"/board-img/{bo}/{img_map[name]}"
            img.attrs.pop("content", None)
            stats["img_ok"] += 1
        elif "/data/" in src:
            img["src"] = urllib.parse.urljoin(DOMAIN + "/", src)
            stats["img_miss"] += 1
        img.attrs.pop("width", None)
    # 이미지 확대 링크 → 로컬 원본
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "view_image.php" in href:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            fn = q.get("fn", [""])[0]
            name = norm_img_name(fn)
            if name in img_map:
                a["href"] = f"/board-img/{bo}/{img_map[name]}"
                a["target"] = "_blank"
            else:
                a.attrs.pop("href", None)
        else:
            # 내부 게시판 링크 → 새 경로
            m = re.search(r"board\.php\?bo_table=(\w+)(?:&(?:amp;)?wr_id=(\d+))?", href)
            if m and m.group(1) in BOARDS:
                a["href"] = (f"/board/{m.group(1)}/{m.group(2)}.html" if m.group(2)
                             else f"/board/{m.group(1)}/")
    return str(soup)


def parse_comment(raw):
    lines = [l for l in raw.split("\n") if l.strip()]
    if len(lines) >= 3 and re.match(r"\d{2}\.\d{2}\.\d{2}", lines[1]):
        author, date, body = lines[0], lines[1], lines[2:]
    else:
        author, date, body = "", "", lines
    dedup = []
    for l in body:
        if not dedup or dedup[-1] != l:
            dedup.append(l)
    return author, date, dedup


# ---------- 목록 페이지 ----------
HERO_H1_CSS = ("{font-size:30px;font-weight:bold;color:#fff;line-height:40px;"
               "padding:0 0 20px;margin:0 0 20px;position:relative;}")

LIST_EXTRA_CSS = """
<style>
#list .list_title{background-image:url('%(bg)s');}
#list .list_title .wrap h1""" + HERO_H1_CSS + """
#list .list_title .wrap h1:after{content:"";display:block;position:absolute;bottom:0;left:0;width:30px;height:2px;background:var(--color-orange);}
#list{margin-bottom:100px;}
@media (max-width:768px){
  #list .list-pc th:nth-child(1),#list .list-pc td:nth-child(1),
  #list .list-pc th:last-child,#list .list-pc td:last-child{display:none}
}
#list .list-pc tbody tr{cursor:pointer}
#list .list-pc .list-subject a{color:inherit;text-decoration:none}
#list .list-page{margin:30px 0}
#board_search{display:flex;gap:6px;margin-top:20px;max-width:360px}
#board_search input{flex:1;height:32px;border:1px solid #ddd;padding:0 10px;font-size:13px}
#board_search button{height:32px;padding:0 14px;background:var(--color-orange);border:none}
#board_search button img{width:14px;height:14px}
</style>"""

CARD_LIST_CSS = """
<style>
#list .list_title{background-image:url('%(bg)s');}
#list .list_title .wrap h1""" + HERO_H1_CSS + """
#list .list_title .wrap h1:after{content:"";display:block;position:absolute;bottom:0;left:0;width:30px;height:2px;background:var(--color-orange);}
#list{margin-bottom:100px;}
#card_rows{width:calc(100%% - 40px);max-width:1200px;margin:0 auto;display:flex;flex-wrap:wrap;gap:20px}
#card_rows a{display:block;width:calc(25%% - 15px);border:1px solid #ddd;padding:25px 20px;color:#000;text-decoration:none;transition:.2s}
#card_rows a:hover{border-color:var(--color-orange)}
#card_rows strong{display:block;font-size:15px;line-height:1.5;height:45px;overflow:hidden;margin-bottom:15px;word-break:keep-all}
#card_rows span{font-size:12px;color:#999}
@media (max-width:1000px){#card_rows a{width:calc(50%% - 10px)}}
@media (max-width:600px){#card_rows a{width:100%%}}
</style>"""


def render_list_page(bo, cfg, header, footer, rows, cat_counts):
    url = f"{DOMAIN}/board/{bo}/"
    head = page_head(header, f"{cfg['name']} | 한국상품권거래소",
                     f"{cfg['sub']} 총 {len(rows)}건.", url)
    skin = f'<link rel="stylesheet" href="/css/board/{cfg["skin"]}.css">'

    search_html = (
        '<div id="board_search">'
        '<input type="text" id="stx" placeholder="검색어를 입력해 주세요." maxlength="20">'
        '<button type="button" onclick="doSearch()"><img src="/img/search_icon_w.svg" alt="검색"></button>'
        "</div>")

    title_html = (
        f'<div class="list_title"><div class="wrap">'
        f"<h1>{esc(cfg['name'])}</h1><span>{esc(cfg['sub'])}</span>{search_html}</div></div>")

    if cfg["layout"] == "card":
        # 카드형(소형 게시판)은 전체를 정적 렌더링 — 검색봇이 바로 읽음
        cards = "".join(
            f'<a href="/board/{bo}/{r["id"]}.html"><strong>{esc(r["title"])}</strong>'
            f'<span>{esc(r["date"] or "")}</span></a>' for r in rows)
        body = (f'<div class="at-body" style="width:100%">{skin}{CARD_LIST_CSS % cfg}'
                f'<section id="list" class="board-list">{title_html}'
                f'<div id="card_rows">{cards}</div></section></div>')
        return head + body + footer

    # 테이블형
    visual = ""
    if cfg["has_cat"]:
        shop_slides = "".join(
            f'<div class="swiper-slide" onclick="window.open(\'{u}\');">'
            f'<img src="/img/logo_slim_c.svg" alt=""><div class="text_box"><p>{esc(n)}</p>'
            f"<span>쇼핑몰 바로가기</span></div></div>" for n, u in SHOPS)
        cats = [c for c in CAT_ORDER if cat_counts.get(c)]
        btns = (f'<li onclick="setCat(\'\')"><img src="/img/{CAT_ICONS[0]}" alt="">'
                f"<p>전체</p><span>{len(rows)}</span></li>")
        for i, c in enumerate(cats):
            icon = CAT_ICONS[(i + 1) % len(CAT_ICONS)]
            btns += (f'<li data-cat="{esc(c)}" onclick="setCat(\'{esc(c)}\')">'
                     f'<img src="/img/{icon}" alt=""><p>{esc(c)}</p><span>{cat_counts[c]}</span></li>')
        visual = (f'<div class="visual"><b>상품권 구매 쇼핑몰 추천</b>'
                  f'<div class="premium_slide"><div class="swiper-wrapper">{shop_slides}</div></div>'
                  f'<ul class="search_content flex" id="quick_btn_wrap">{btns}</ul></div>')

    # 첫 페이지 20행은 정적으로 삽입 — 자바스크립트를 못 읽는 검색봇(네이버 등)도 글 링크 수집 가능
    static_rows = ""
    for r in rows[:20]:
        num = ('<span class="wr-icon wr-notice"></span>' if r["notice"]
               else f'<span class="en">{r["num"]}</span>')
        cmt = (f' <span class="count orangered">+<span class="cnt_cmt">{r["cmt"]}</span></span>'
               if r["cmt"] else "")
        cat_td = f'<td class="text-center">{esc(r["cat"] or "")}</td>' if cfg["has_cat"] else ""
        static_rows += (
            f'<tr onclick="goPost({r["id"]})"><td class="text-center font-11">{num}</td>{cat_td}'
            f'<td class="list-subject{" notice" if r["notice"] else ""}">'
            f'<a href="/board/{bo}/{r["id"]}.html">{esc(r["title"])}</a>{cmt}</td>'
            f'<td><b><span class="sv_member">{esc(r["author"] or "")}</span></b></td>'
            f'<td class="text-center en font-11">{esc(r["date"] or "")}</td>'
            f'<td class="text-center en font-11">{r["hit"] or 0}</td></tr>')

    cat_th = "<th scope=\"col\">분류</th>" if cfg["has_cat"] else ""
    table = (f'<div class="table-responsive"><table class="table div-table list-pc bg-white">'
             f"<thead><tr><th scope=\"col\">번호</th>{cat_th}<th scope=\"col\">제목</th>"
             f"<th scope=\"col\">작성자</th><th scope=\"col\">작성일</th>"
             f"<th scope=\"col\"><nobr>조회수</nobr></th></tr></thead>"
             f'<tbody id="board_rows">{static_rows}</tbody></table></div>')
    pager = '<div class="list-page text-center"><ul class="pagination pagination-sm en" id="board_pager"></ul></div>'

    body = (f'<div class="at-body" style="width:100%">{skin}{LIST_EXTRA_CSS % cfg}'
            f'<section id="list" class="board-list">{title_html}{visual}{table}{pager}</section>'
            f"{table_list_script(bo, cfg)}</div>")
    return head + body + footer


def table_list_script(bo, cfg):
    has_cat = "true" if cfg["has_cat"] else "false"
    return """
<script>
var ROWS = [], PAGE_SIZE = 20, HAS_CAT = %(has_cat)s;
var state = { page: 1, sca: '', stx: '' };
function esch(s){return String(s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function goPost(id){location.href='/board/%(bo)s/'+id+'.html';}
function filtered(){
  return ROWS.filter(function(r){
    if(state.sca && r.cat!==state.sca) return false;
    if(state.stx && r.title.indexOf(state.stx)<0) return false;
    return true;
  });
}
function render(){
  var rows=filtered();
  var total=rows.length, pages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  if(state.page>pages) state.page=pages;
  var start=(state.page-1)*PAGE_SIZE, slice=rows.slice(start,start+PAGE_SIZE);
  var out='';
  slice.forEach(function(r){
    var num = r.notice ? '<span class="wr-icon wr-notice"></span>' : '<span class="en">'+r.num+'</span>';
    var cmt = r.cmt>0 ? ' <span class="count orangered">+<span class="cnt_cmt">'+r.cmt+'</span></span>' : '';
    out += '<tr onclick="goPost('+r.id+')"><td class="text-center font-11">'+num+'</td>'+
      (HAS_CAT?'<td class="text-center">'+esch(r.cat||'')+'</td>':'')+
      '<td class="list-subject'+(r.notice?' notice':'')+'"><a href="/board/%(bo)s/'+r.id+'.html">'+esch(r.title)+'</a>'+cmt+'</td>'+
      '<td><b><span class="sv_member">'+esch(r.author||'')+'</span></b></td>'+
      '<td class="text-center en font-11">'+esch(r.date||'')+'</td>'+
      '<td class="text-center en font-11">'+(r.hit||0)+'</td></tr>';
  });
  document.getElementById('board_rows').innerHTML = out ||
    '<tr><td colspan="6" class="text-center" style="padding:60px 0;color:#999">게시물이 없습니다.</td></tr>';
  renderPager(pages);
  document.querySelectorAll('#quick_btn_wrap li').forEach(function(li){
    li.classList.toggle('atv',(li.getAttribute('data-cat')||'')===state.sca);
  });
}
function renderPager(pages){
  var p=state.page, out='';
  out+='<li class="'+(p<=1?'disabled':'')+'"><a '+(p>1?'href="javascript:goPage(1)"':'')+'><i class="fa fa-angle-double-left"></i></a></li>';
  out+='<li class="'+(p<=1?'disabled':'')+'"><a '+(p>1?'href="javascript:goPage('+(p-1)+')"':'')+'><i class="fa fa-angle-left"></i></a></li>';
  var s=Math.max(1,p-4), e=Math.min(pages,s+9); s=Math.max(1,e-9);
  for(var i=s;i<=e;i++) out+= i===p ? '<li class="active"><a>'+i+'</a></li>' : '<li><a href="javascript:goPage('+i+')">'+i+'</a></li>';
  out+='<li class="'+(p>=pages?'disabled':'')+'"><a '+(p<pages?'href="javascript:goPage('+(p+1)+')"':'')+'><i class="fa fa-angle-right"></i></a></li>';
  out+='<li class="'+(p>=pages?'disabled':'')+'"><a '+(p<pages?'href="javascript:goPage('+pages+')"':'')+'><i class="fa fa-angle-double-right"></i></a></li>';
  document.getElementById('board_pager').innerHTML=out;
}
function syncURL(){
  var q=new URLSearchParams();
  if(state.page>1)q.set('page',state.page);
  if(state.sca)q.set('sca',state.sca);
  if(state.stx)q.set('stx',state.stx);
  history.replaceState(null,'',location.pathname+(q.toString()?'?'+q.toString():''));
}
function goPage(p){state.page=p;syncURL();render();window.scrollTo(0,0);}
function setCat(c){state.sca=c;state.page=1;syncURL();render();}
function doSearch(){state.stx=document.getElementById('stx').value.trim();state.page=1;syncURL();render();}
document.addEventListener('DOMContentLoaded',function(){
  var q=new URLSearchParams(location.search);
  state.page=parseInt(q.get('page')||'1',10)||1;
  state.sca=q.get('sca')||''; state.stx=q.get('stx')||'';
  if(state.stx)document.getElementById('stx').value=state.stx;
  document.getElementById('stx').addEventListener('keydown',function(e){if(e.key==='Enter')doSearch();});
  fetch('/board/%(bo)s/list.json').then(function(r){return r.json();})
    .then(function(d){ROWS=d;render();});
});
</script>""" % {"bo": bo, "has_cat": has_cat}


# ---------- 글 페이지 ----------
VIEW_EXTRA_CSS = """
<style>
#view_wrap .view_title{background-image:url('%(bg)s');}
#view_wrap{margin-bottom:100px;}
#view_wrap .view-content img{max-width:100%%;height:auto;}
/* 제목을 h1로 쓰되 디자인은 스킨(파란 바) 그대로 — 브라우저 기본 h1 여백만 제거 */
#view_wrap .view_content h1.board_title{margin:0;}
#view_wrap .heading span+span{margin-left:15px;}
#view_wrap .view-comment{width:calc(100%% - 40px);max-width:1200px;margin:60px auto 15px;font-size:16px;}
#bo_vc{width:calc(100%% - 40px);max-width:1200px;margin:0 auto;}
#bo_vc .media{border:1px solid #eee;padding:15px;margin-bottom:10px;font-size:14px;}
#bo_vc .media b{margin-right:10px;}
#bo_vc .media .cmt-date{font-size:12px;color:#999;}
#bo_vc .media p{margin:8px 0 0;line-height:1.6;}
.view-nav{width:calc(100%% - 40px);max-width:1200px;margin:40px auto 0;display:flex;justify-content:space-between;gap:10px;}
.view-nav a{display:inline-block;padding:9px 22px;border:1px solid #ddd;color:#000;font-size:13px;text-decoration:none;transition:.2s;}
.view-nav a:hover{border-color:var(--color-orange);color:var(--color-orange);}
.view-nav a.list-btn{background:var(--color-orange);color:#fff;border-color:var(--color-orange);}
</style>"""


def render_view_page(bo, cfg, header, footer, post, meta, prev_id, next_id):
    pid = post["wr_id"]
    url = f"{DOMAIN}/board/{bo}/{pid}"
    desc = re.sub(r"\s+", " ", post.get("content_text", ""))[:120] or cfg["sub"]

    # og:image / JSON-LD 이미지: 본문 첫 로컬 이미지 우선
    first_img = None
    m = re.search(r'src="(/board-img/[^"]+)"', post["_clean_html"])
    if m:
        first_img = DOMAIN + m.group(1)
    og_image = first_img or f"{DOMAIN}/img/og_img.png"

    head = page_head(header, f"{post['title']} | {cfg['name']}", desc, url, image=og_image)
    skin = f'<link rel="stylesheet" href="/css/board/{cfg["skin"]}.css">'

    # Article 구조화 데이터 (검색 노출 강화)
    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": desc,
        "image": [og_image],
        "author": {"@type": "Person", "name": post.get("author") or "한국상품권거래소"},
        "publisher": {"@type": "Organization", "name": "한국상품권거래소",
                      "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/img/og_img.png"}},
        "mainEntityOfPage": url,
    }
    pub = iso_date(post.get("date"))
    if pub:
        ld["datePublished"] = pub
    ld_html = ('<script type="application/ld+json">'
               + json.dumps(ld, ensure_ascii=False) + "</script>")

    hit_html = f"<span>조회 {meta['hit']}</span>" if meta and meta.get("hit") else ""
    author = esc(post.get("author") or "한국상품권거래소")
    date = esc(post.get("date") or "")

    cmts = ""
    for raw in post.get("comments", []):
        a, d, body = parse_comment(raw)
        body_html = "<br>".join(esc(l) for l in body)
        cmts += (f'<div class="media"><b>{esc(a)}</b>'
                 f'<span class="cmt-date">{esc(d)}</span><p>{body_html}</p></div>')
    n_cmt = len(post.get("comments", []))

    nav = '<div class="view-nav">'
    nav += (f'<a href="/board/{bo}/{prev_id}.html">&laquo; 이전글</a>' if prev_id else "<span></span>")
    nav += f'<a class="list-btn" href="/board/{bo}/">목록</a>'
    nav += (f'<a href="/board/{bo}/{next_id}.html">다음글 &raquo;</a>' if next_id else "<span></span>")
    nav += "</div>"

    body = f'''<div class="at-body" style="width:100%">{skin}{VIEW_EXTRA_CSS % cfg}{ld_html}
<div id="view_wrap" class="view-wrap">
	<div class="view_title"><div class="wrap"><p>{esc(cfg["name"])}</p><span>{esc(cfg["sub"])}</span></div></div>
	<div class="view_content">
		<h1 class="board_title">{esc(post["title"])}</h1>
		<div class="heading"><span class="sv_member">{author}</span><span>{date}</span>{hit_html}</div>
		<div class="wrap"><div class="view-content">{post["_clean_html"]}</div></div>
		<h3 class="view-comment">댓글 {n_cmt}</h3>
		<section id="bo_vc" class="comment-media">{cmts}</section>
		{nav}
	</div>
</div>
</div>'''
    return head + body + footer


# ---------- 메인 ----------
def main():
    header, footer = load_shell()
    meta_all = json.load(io.open(CRAWL / "data" / "list_meta.json", encoding="utf-8"))
    latest = {}
    sitemap_urls = []
    total_pages = 0
    stats = {"img_ok": 0, "img_miss": 0}

    for bo, cfg in BOARDS.items():
        posts = json.load(io.open(CRAWL / "data" / f"{bo}.json", encoding="utf-8"))
        meta = meta_all.get(bo, {})
        img_map = build_image_map(bo)

        # 이미지 복사
        src_dir = CRAWL / "images" / bo
        dst_dir = SITE / "board-img" / bo
        if src_dir.is_dir():
            dst_dir.mkdir(parents=True, exist_ok=True)
            for f in src_dir.iterdir():
                if not (dst_dir / f.name).exists():
                    shutil.copy2(f, dst_dir / f.name)

        # 목록 데이터 (번호 내림차순 = 최신순, 공지 우선)
        rows = []
        for p in posts:
            m = meta.get(str(p["wr_id"]), {})
            rows.append({
                "id": p["wr_id"],
                "num": m.get("num", 0) or p["wr_id"],
                "cat": m.get("cat", ""),
                "title": p["title"],
                "author": p.get("author", ""),
                "date": p.get("date", ""),
                "hit": m.get("hit", 0),
                "cmt": m.get("cmt", len(p.get("comments", []))),
                "notice": m.get("notice", False),
            })
        rows.sort(key=lambda r: (not r["notice"], -r["num"]))
        cat_counts = {}
        for r in rows:
            if r["cat"]:
                cat_counts[r["cat"]] = cat_counts.get(r["cat"], 0) + 1

        out_dir = SITE / "board" / bo
        out_dir.mkdir(parents=True, exist_ok=True)
        io.open(out_dir / "list.json", "w", encoding="utf-8").write(
            json.dumps(rows, ensure_ascii=False))

        # 목록 페이지
        io.open(out_dir / "index.html", "w", encoding="utf-8", newline="\n").write(
            render_list_page(bo, cfg, header, footer, rows, cat_counts))
        board_lastmod = max((iso_date(r["date"]) or "" for r in rows), default="") or None
        sitemap_urls.append((f"{DOMAIN}/board/{bo}/", board_lastmod))

        # 글 페이지 (이전/다음: 목록 순서 기준)
        order = [r["id"] for r in rows]
        pos = {pid: i for i, pid in enumerate(order)}
        posts_by_id = {p["wr_id"]: p for p in posts}
        for p in posts:
            p["_clean_html"] = clean_content(p.get("content_html", ""), bo, img_map, stats)
        for p in posts:
            i = pos[p["wr_id"]]
            next_id = order[i - 1] if i > 0 else None            # 목록에서 위 = 더 최신
            prev_id = order[i + 1] if i + 1 < len(order) else None
            html_out = render_view_page(bo, cfg, header, footer, p,
                                        meta.get(str(p["wr_id"])), prev_id, next_id)
            io.open(out_dir / f"{p['wr_id']}.html", "w", encoding="utf-8", newline="\n").write(html_out)
            sitemap_urls.append((f"{DOMAIN}/board/{bo}/{p['wr_id']}", iso_date(p.get("date"))))
            total_pages += 1

        # 메인 요약용 최근 글
        n = 8 if bo == "free" else 5
        latest[bo] = [{"id": r["id"], "cat": r["cat"], "title": r["title"],
                       "author": r["author"], "date": r["date"]}
                      for r in rows if not r["notice"]][:n]
        print(f"[{bo}] 글 {len(posts)}개, 목록 1페이지 생성", flush=True)

    io.open(SITE / "data" / "latest_posts.json", "w", encoding="utf-8").write(
        json.dumps(latest, ensure_ascii=False, indent=1))

    # 사이트맵
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, lastmod in sitemap_urls:
        lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        sm.append(f"  <url><loc>{u}</loc>{lm}</url>")
    sm.append("</urlset>")
    io.open(SITE / "sitemap-boards.xml", "w", encoding="utf-8").write("\n".join(sm))

    print(f"\n총 {total_pages}개 글 페이지 + 목록 {len(BOARDS)}개 생성 완료")
    print(f"이미지: 로컬 연결 {stats['img_ok']}건, 원본서버 유지 {stats['img_miss']}건")


if __name__ == "__main__":
    main()
