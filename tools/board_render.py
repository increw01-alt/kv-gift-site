"""승인된 본문 레이아웃으로 렌더링하고 게시판별 목록 형태를 보존합니다."""
import html
import json
import re
from pathlib import Path
from board_profiles import PROFILES
from board_drafts import AUTHOR, DOMAIN, TEMPLATE, paragraphs, read_json, replace_one

ASSOCIATION = 'https://koreagiftcard.co.kr/'


def title_for(board, topic):
    return PROFILES[board]['prefix'] + ' ' + topic


def article_html(board, topic, data, day, banner, brief=None):
    profile, esc = PROFILES[board], html.escape
    title = title_for(board, topic)
    result = (f'<article data-editorial-board="{board}"><span class="tag">{esc(profile["label"])}</span>'
              f'<h1>{esc(title)}</h1><div class="meta">{AUTHOR} · {day.isoformat()}</div>'
              f'<p class="lead">{esc(data["summary"])}</p>')
    if banner:
        result += (f'<figure><img src="{esc(banner, quote=True)}" width="1536" height="1024" '
                   f'alt="{esc(topic, quote=True)} 안내 이미지" decoding="async" fetchpriority="high">'
                   '<figcaption>글의 이해를 돕기 위한 AI 생성 안내 이미지</figcaption></figure>')
    for number, section in enumerate(data['sections'], 1):
        result += (f'<section class="section"><span class="num">{number:02d} / {esc(profile["label"])}</span>'
                   f'<h2>{esc(section["heading"])}</h2>{paragraphs(section["body"])}</section>')
    result += f'<section class="takeaway"><h2>{esc(profile["checks"])}</h2><ul>'
    result += ''.join('<li>'+esc(value)+'</li>' for value in data['checks']) + '</ul></section>'
    if profile.get('note'):
        result += f'<p class="note">{esc(profile["note"])}</p>'
    if brief:
        result += '<aside class="sources"><strong>확인 자료</strong><p>'
        result += '<br>'.join(f'<a href="{esc(x["url"], quote=True)}">{esc(x["title"])}</a>' for x in brief['sources'])
        result += f'</p><p>자료 확인일: {esc(brief["verified_on"])} · 위 자료에 확인된 소식을 정리했습니다.</p></aside>'
    if board not in ('sense', 'free'):
        result += (f'<a class="cta" href="{ASSOCIATION}" target="_blank" rel="noopener">'
                   '<small>한국상품권협회</small><h2>상품권 이용, 더 궁금한 점이 있나요?</h2>'
                   '<p>상품권 정보와 상담 안내를 확인해 보세요.<br>'
                   '개별 주문·사용·취소 처리는 해당 구매처나 발행사에 문의해 주세요.</p>'
                   '<span class="button">한국상품권협회 안내 보기 ↗</span></a>')
    result += ('<p class="foot">운영팀이 정리한 안내 콘텐츠입니다. 실제 고객 후기나 접수된 문의가 아닙니다. '
               '상품권 전체 번호와 개인정보는 공개 게시판에 올리지 마세요.</p></article>')
    return result


def update_list(board, index, rows, entry):
    esc, profile = html.escape, PROFILES[board]
    if profile['list'] == 'cards':
        card = (f'<a href="/board/{board}/{entry["id"]}"><strong>{esc(entry["title"])}</strong>'
                f'<span>{entry["date"]}</span></a>')
        index = replace_one(r'<div id="card_rows">', '<div id="card_rows">'+card, index)
    else:
        table = ''
        for row in rows[:20]:
            table += f'<tr onclick="goPost({row["id"]})"><td class="text-center font-11">{row["num"]}</td>'
            if profile.get('category'):
                table += f'<td class="text-center">{esc(row.get("cat", ""))}</td>'
            table += (f'<td class="list-subject"><a href="/board/{board}/{row["id"]}.html">'
                      f'{esc(row["title"])}</a></td><td>{esc(row.get("author", ""))}</td>'
                      f'<td class="text-center">{esc(row["date"])}</td><td class="text-center">{row["hit"]}</td></tr>')
        opening = re.search(r'<tbody[^>]*>', index).group()
        index = replace_one(r'<tbody[^>]*>.*?</tbody>', opening+table+'</tbody>', index)
    return re.sub(r'총 \d+건\.', f'총 {len(rows)}건.', index)


def update_home(board, homepage, rows):
    selectors = {
        'purchase': r'(<div class="board1 flex">.*?<div class="left">.*?<ul>).*?</ul>',
        'sale': r'(<div class="board1 flex">.*?<div class="right">.*?<ul>).*?</ul>',
        'free': r'(<div class="free_board">.*?<ul>).*?</ul>',
        'gc_tip': r'(<div class="tip_board">.*?<ul>).*?</ul>',
        'general_notice': r'(<div class="add_board" id="notice">.*?<ul>).*?</ul>',
    }
    if board not in selectors:
        return homepage
    selector, esc = selectors[board], html.escape
    opening = re.search(selector, homepage, re.S).group(1)
    if board in ('purchase', 'sale'):
        items = '<li class="board_title flex"><p>분류</p><p>제목</p><p>작성자</p><p>작성일</p></li>'
    else:
        items = ''
    for row in rows[:5]:
        path = f'/board/{board}/{row["id"]}'
        link = f'<p><a href="{path}">{esc(row["title"])}</a></p>'
        items += f'<li class="flex" onclick="location.href=\'{path}\'">'
        if board in ('purchase', 'sale'):
            items += f'<p>{esc(row.get("cat", ""))}</p>'+link+f'<p>{esc(row.get("author", ""))}</p><p>{row["date"]}</p>'
        else:
            items += link + ('' if board == 'gc_tip' else f'<span>{row["date"]}</span>')
        items += '</li>'
    homepage = replace_one(selector, opening+'\n'+items+'\n</ul>', homepage)
    if board == 'general_notice':
        old = re.search(r'<div class="notice flex".*?</div>', homepage, re.S).group()
        new = replace_one(r'<p>.*?</p>', f'<p>{esc(rows[0]["title"])}</p>', old)
        new = replace_one(r'<span>.*?</span>', f'<span>{rows[0]["date"]}</span>', new)
        homepage = homepage.replace(old, new, 1)
    return homepage


def render_post(board, topic, data, day, root, banner, brief):
    profile, esc = PROFILES[board], html.escape
    if banner and not re.fullmatch(rf'board-img/{re.escape(board)}/[a-zA-Z0-9_-]+\.png', banner):
        raise ValueError('잘못된 배너 경로입니다.')
    folder = root / 'board' / board
    rows = read_json(folder / 'list.json')
    existing_ids = [int(p.stem) for p in folder.glob('*.html') if p.stem.isdigit()]
    post_id = max([profile.get('id_floor', 0)] + [x['id'] for x in rows] + existing_ids) + 1
    path = folder / f'{post_id}.html'
    title, url = title_for(board, topic), f'{DOMAIN}/board/{board}/{post_id}'
    image_url = f'{DOMAIN}/{banner}' if banner else DOMAIN+'/img/og_img.png'
    source = (root / TEMPLATE).read_text(encoding='utf-8')
    source = replace_one(r'<title>.*?</title>', f'<title>{esc(title)} | {esc(profile["name"])} | 한국상품권거래소</title>', source)
    for attr, field, value in [
        ('name', 'description', data['summary']), ('name', 'keywords', profile['name']+', '+topic),
        ('property', 'og:type', 'article'), ('property', 'og:description', data['summary']),
        ('property', 'og:title', title), ('property', 'og:url', url), ('property', 'og:image', image_url),
        ('property', 'og:image:alt', topic+' 안내 이미지'), ('name', 'twitter:image', image_url),
    ]:
        source = replace_one(f'<meta {attr}="{field}" content="[^"]*"[^>]*>',
                             f'<meta {attr}="{field}" content="{esc(value, quote=True)}">', source)
    source = replace_one(r'<link rel="canonical" href="[^"]*"[^>]*>', f'<link rel="canonical" href="{url}">', source)
    schema = {'@context': 'https://schema.org', '@type': 'Article', 'headline': title, 'description': data['summary'],
              'author': {'@type': 'Organization', 'name': AUTHOR},
              'publisher': {'@type': 'Organization', 'name': '한국상품권거래소'},
              'mainEntityOfPage': url, 'datePublished': day.isoformat(), 'dateModified': day.isoformat(),
              'articleSection': profile['name'], 'image': image_url}
    source = replace_one(r'<script type="application/ld\+json">.*?</script>',
                         '<script type="application/ld+json">'+json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c')+'</script>', source)
    fragment = (f'<main id="approved-tip"><nav class="crumb" aria-label="현재 위치">'
                f'<a href="/">홈</a> / <a href="/board/{board}/">{esc(profile["name"])}</a></nav>'
                + article_html(board, topic, data, day, '/'+banner if banner else None, brief)
                + f'<nav class="tip-nav" aria-label="게시글 이동"><a href="/board/{board}/">목록으로</a>'
                '<a href="/board/gc_information/">상품권 정보 보기</a></nav></main>')
    source = replace_one(r'<main id="approved-tip">.*?</main>', fragment, source)
    assert source.count('<h1>') == 1
    entry = {'id': post_id, 'num': max((x['num'] for x in rows), default=0)+1,
             'cat': '기타' if profile.get('category') else '', 'title': title, 'author': AUTHOR,
             'date': day.strftime('%y.%m.%d'), 'hit': 0, 'cmt': 0, 'notice': False}
    rows.insert(0, entry)
    index_path = folder / 'index.html'
    index = update_list(board, index_path.read_text(encoding='utf-8'), rows, entry)
    latest_path = root / 'data/latest_posts.json'
    latest = read_json(latest_path)
    latest[board] = [{k: x[k] for k in ('id', 'cat', 'title', 'author', 'date')} for x in rows[:5]]
    sitemap_path = root / 'sitemap-boards.xml'
    sitemap = sitemap_path.read_text(encoding='utf-8')
    if f'<loc>{url}</loc>' in sitemap:
        raise ValueError('이미 사이트맵에 등록된 글 번호입니다.')
    sitemap = replace_one(
        rf'<url><loc>{re.escape(DOMAIN)}/board/{board}/</loc><lastmod>[^<]+</lastmod></url>',
        f'<url><loc>{DOMAIN}/board/{board}/</loc><lastmod>{day.isoformat()}</lastmod></url>', sitemap)
    sitemap = sitemap.replace('</urlset>', f'  <url><loc>{url}</loc><lastmod>{day.isoformat()}</lastmod></url>\n</urlset>')
    history_path = root / 'data/editorial_history.json'
    history = read_json(history_path) if history_path.exists() else []
    history.append({'board': board, 'id': post_id, 'topic': topic, 'drafted_at': day.isoformat(), 'automation': True})
    updates = {path: source, folder / 'list.json': json.dumps(rows, ensure_ascii=False)+'\n',
               index_path: index, latest_path: json.dumps(latest, ensure_ascii=False, indent=1)+'\n',
               sitemap_path: sitemap, history_path: json.dumps(history, ensure_ascii=False, indent=2)+'\n'}
    home_path = root / 'index.html'
    old_home = home_path.read_text(encoding='utf-8')
    home = update_home(board, old_home, rows)
    if home != old_home:
        updates[home_path] = home
    # 모든 템플릿 검증과 치환을 마친 뒤 파일을 기록합니다.
    for file, content in updates.items():
        file.write_text(content, encoding='utf-8', newline='\n')
    review = (f'# {title}\n\n게시판: **{profile["name"]}** · 작성자: {AUTHOR}\n\n'
              f'편집 방향: {profile["purpose"]}\n\n{data["summary"]}\n\n')
    for section in data['sections']:
        review += f'## {section["heading"]}\n\n{section["body"]}\n\n'
    review += f'## {profile["checks"]}\n\n' + '\n'.join('- ✓ '+x for x in data['checks'])
    if brief:
        review += '\n\n## 확인 자료\n\n' + '\n'.join(f'- [{x["title"]}]({x["url"]})' for x in brief['sources'])
    review += ('\n\n---\nAI가 작성한 운영팀 안내 초안입니다. 실제 고객 후기가 아닙니다.\n\n'
               '- [ ] 게시판 성격과 내용·이미지가 맞는지 확인\n- [ ] 내용과 사업 조건 확인\n'
               '- [ ] 게시할 준비가 되면 **Merge pull request** 실행\n\n'
               '승인 리뷰만으로는 게시되지 않습니다. main에 병합해야 배포됩니다.\n')
    return title, review, [p.relative_to(root).as_posix() for p in updates]


def save_preview(folder, board, topic, data, day, raw, root, brief=None):
    """운영 파일이나 PR을 변경하지 않는 검토 전용 미리보기."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'banner.png').write_bytes(raw)
    css = (root / 'css/board/approved-tip.css').read_text(encoding='utf-8')
    value = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width, initial-scale=1">'
             '<meta name="robots" content="noindex,nofollow">'
             f'<title>{html.escape(title_for(board, topic))} | 게시 전 검토</title>'
             f'<style>{css}</style></head><body style="margin:0;background:#f5f6f8">'
             '<main id="approved-tip"><p class="note">게시 전 검토본 · 운영 사이트 미게시</p>'
             + article_html(board, topic, data, day, 'banner.png', brief) + '</main></body></html>')
    (folder / 'index.html').write_text(value, encoding='utf-8', newline='\n')
    (folder / 'draft.json').write_text(json.dumps({
        'board': board, 'topic': topic, 'data': data, 'date': day.isoformat(), 'brief': brief,
        'published': False, 'requires_user_approval': True,
    }, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
