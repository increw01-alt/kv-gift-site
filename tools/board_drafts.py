"""AI는 텍스트만 생성. 고정 템플릿으로 HTML을 만들고 승인용 브랜치에 반영."""
import datetime as dt
import difflib
import html
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = '한국상품권거래소 운영팀'
DOMAIN = 'https://kv-gift.co.kr'
CHAT = 'https://koreagiftcard.channel.io/home?page=board-guide'
BOARDS = {'purchase': ('상품권 구매게시판', 2560), 'sale': ('상품권 판매게시판', 3688)}
KST = dt.timezone(dt.timedelta(hours=9))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def normalized(text):
    return re.sub(r'[^가-힣a-z0-9]', '', text.lower())


def pick_topic(board, root=ROOT):
    topics = read_json(root / 'tools/board_topics.json')[board]
    rows = read_json(root / f'board/{board}/list.json')
    history = read_json(root / 'data/editorial_history.json') if (root / 'data/editorial_history.json').exists() else []
    used = {x['topic'] for x in history if x['board'] == board}
    titles = [normalized(x['title']) for x in rows]
    for topic in topics:
        if topic not in used and all(difflib.SequenceMatcher(None, normalized(topic), t).ratio() < .88 for t in titles):
            return topic
    raise ValueError('미사용 주제가 없습니다. tools/board_topics.json에 새 질문을 추가하세요.')


def validate(data):
    if set(data) != {'summary', 'sections', 'checks'}:
        raise ValueError('글 구조 오류')
    if not isinstance(data['summary'], str) or not 30 <= len(data['summary']) <= 180:
        raise ValueError('요약 길이 오류')
    if not isinstance(data['sections'], list) or len(data['sections']) != 3:
        raise ValueError('본문은 3개 절이어야 합니다')
    strings = [data['summary']]
    for section in data['sections']:
        if set(section) != {'heading', 'body'}:
            raise ValueError('본문 구조 오류')
        if not isinstance(section['heading'], str) or not 3 <= len(section['heading']) <= 45:
            raise ValueError('소제목 길이 오류')
        if not isinstance(section['body'], str) or not 60 <= len(section['body']) <= 650:
            raise ValueError('본문 길이 오류')
        strings.extend([section['heading'], section['body']])
    if not isinstance(data['checks'], list) or len(data['checks']) != 3:
        raise ValueError('확인 사항은 3개여야 합니다')
    if any(not isinstance(x, str) or not 10 <= len(x) <= 130 for x in data['checks']):
        raise ValueError('확인 사항 길이 오류')
    strings.extend(data['checks'])
    text = '\n'.join(strings)
    forbidden = r'https?://|www\.|[<>]|\d|[%％]|현금화|카드깡|급전|무조건|신용\s*무관|최저가|공식\s*인증|안전한\s*거래|(?<![가-힣])제가|(?<![가-힣])저는|(?<![가-힣])제\s*경험|실제\s*고객|고객님께서|당일\s*입금|즉시\s*입금'
    match = re.search(forbidden, text, re.I)
    if match:
        raise ValueError('자동 검수에서 금지 표현이 발견되어 게시를 중단했습니다: ' + match.group(0))
    return data


def generate(topic, model, on_usage=None):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ValueError('GitHub Secret OPENAI_API_KEY가 없습니다.')
    string = {'type': 'string'}
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['summary', 'sections', 'checks'],
              'properties': {'summary': string, 'sections': {'type': 'array', 'items': {
                  'type': 'object', 'additionalProperties': False, 'required': ['heading', 'body'],
                  'properties': {'heading': string, 'body': string}}}, 'checks': {'type': 'array', 'items': string}}}
    instructions = '''한국상품권거래소 운영팀의 한국어 질문·답변 안내 초안을 작성한다.
독자가 실제로 준비하거나 확인할 항목을 구체적으로 설명하되, 고객을 가장한 후기나 실제 상담 사례를 만들지 않는다.
사이트는 상품권 정보와 상담을 안내한다. 업체의 취급 여부, 수수료, 할부 조건, 정산 시간, 운영 시간, 환불 권리 등 확인되지 않은 사실을 단정하지 않는다.
최신 정책이나 법률을 아는 것처럼 쓰지 않는다. 발행사·판매처·매입처에 각각 무엇을 확인할지 구분한다.
수치, 숫자, 금액, 비율, 할인율, 처리 기간, 보장, 공식 인증, 현금화, 카드깡, 급전 표현은 쓰지 않는다.
개인정보나 상품권 전체 번호를 공개 게시판에 쓰도록 유도하지 않는다. HTML, 마크다운, URL 없이 평문으로만 작성한다.
말투는 상담 담당자가 옆에서 설명하듯 자연스러운 해요체로 쓴다. 가상의 경험담은 만들지 않는다.
'주요 사항을 안내합니다', '정확히 파악하여', '중요합니다', '꼼꼼히 확인하세요' 같은 추상적 문구를 반복하지 않는다.
summary는 질문에 바로 답하는 도입 30~120자. sections는 정확히 세 개, heading은 독자의 짧은 질문 3~45자.
body는 60~350자, 두세 개의 짧은 문단을 빈 줄(\\n\\n)로 구분한다. 문단마다 한두 문장만 쓴다.
독자가 그대로 물어볼 수 있는 질문을 따옴표로 한 번 제시해도 좋다. 질문 예시는 실제 고객 발언처럼 소개하지 않는다.
checks는 행동 중심의 짧은 항목 세 개로 각각 10~60자. 제목과 본문에 같은 설명을 반복하지 않는다.
특수기호와 번호는 템플릿에서 붙이므로 직접 넣지 않는다. 장식보다 쉬운 표현과 문단 구분에 집중한다.'''
    payload = {'model': model, 'store': False, 'max_output_tokens': 2600,
               'instructions': instructions, 'input': topic,
               'text': {'format': {'type': 'json_schema', 'name': 'board_guide', 'strict': True, 'schema': schema}}}
    request = urllib.request.Request('https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        # 응답 본문이나 인증 헤더는 로그에 출력하지 않습니다.
        raise RuntimeError(f'OpenAI API HTTP {error.code}. 결제/모델 접근/키 권한을 확인하세요.') from None
    if on_usage:
        on_usage('text', model, result.get('usage') or {})
    if result.get('status') != 'completed':
        raise ValueError('API 생성 미완료: 파일을 변경하지 않습니다.')
    output = ''.join(c['text'] for item in result.get('output', []) for c in item.get('content', []) if c.get('type') == 'output_text')
    return validate(json.loads(output))


def replace_one(pattern, replacement, text):
    text, n = re.subn(pattern, lambda m: replacement, text, count=1, flags=re.S)
    if n != 1:
        raise ValueError('사이트 템플릿이 변경되었습니다: ' + pattern[:70])
    return text


def paragraphs(text):
    """빈 줄을 의미 있는 문단으로 렌더링. 모델 텍스트는 항상 escape."""
    chunks = [part.strip() for part in re.split(r'\n\s*\n', text) if part.strip()]
    if len(chunks) == 1:
        # 빈 줄을 놓친 응답도 두 문장마다 나눕니다.
        sentences = re.split(r'(?<=[.!?。])\s+', text.strip())
        chunks = [' '.join(sentences[i:i+2]) for i in range(0, len(sentences), 2)]
    return ''.join('<p>'+html.escape(part)+'</p>' for part in chunks)


EDITORIAL_CSS = '''<style>
.editorial-guide{font-size:16px;line-height:1.85;overflow-wrap:anywhere;color:#26354a}
#view_wrap .editorial-guide p.editorial-label{font-size:13px !important;color:#627087;margin:0 0 18px}
.editorial-guide .editorial-intro{background:#f3f6fa;border-left:3px solid #c4a466;padding:18px 22px;border-radius:0 10px 10px 0;margin:0 0 32px}
#view_wrap .editorial-guide p{margin:0 0 18px !important;font-size:16px !important;line-height:1.85 !important;font-weight:400;word-break:keep-all}
.editorial-guide .editorial-intro p:last-child{margin-bottom:0}
.editorial-guide section{margin:0 0 32px}
.editorial-guide h2{font-size:21px;line-height:1.5;margin:0 0 14px;font-weight:700;color:#15243b}
.editorial-guide .editorial-number{color:#907039;margin-right:9px;font-size:16px}
.editorial-guide .editorial-checks{padding:22px;background:#f7f8fa;border:1px solid #e4e9ef;border-radius:12px}
.editorial-guide .editorial-checks ul{padding:0;margin:0;list-style:none}
.editorial-guide .editorial-checks li{list-style:none;display:flex;gap:10px;margin:10px 0;line-height:1.65}
.editorial-guide .editorial-checks li span{color:#287460;font-weight:700;flex-shrink:0}
#view_wrap .editorial-guide p.editorial-note{font-size:13px !important;color:#687487;margin:20px 0 !important}
.editorial-guide .editorial-links{display:flex;flex-wrap:wrap;gap:14px;margin:16px 0}
.editorial-guide .editorial-links a{display:inline;width:auto;text-decoration:underline}
.editorial-guide .editorial-cta{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:12px 22px;background:#13233e;color:#fff;border-radius:8px;font-weight:600;width:auto}
@media(max-width:500px){.editorial-guide h2{font-size:19px}.editorial-guide .editorial-intro,.editorial-guide .editorial-checks{padding:16px}.editorial-guide .editorial-cta{width:100%}}
</style>'''


def article_body(data):
    body = '<p class="editorial-label">상품권 이용 가이드 · 운영팀 답변</p>'
    body += '<div class="editorial-intro">'+paragraphs(data['summary'])+'</div>'
    for number, section in enumerate(data['sections'], 1):
        body += f'<section><h2><span class="editorial-number">{number:02d}</span>'+html.escape(section['heading'])+'</h2>'+paragraphs(section['body'])+'</section>'
    body += '<section class="editorial-checks"><h2>문의 전, 이것만 챙겨두세요</h2><ul>'
    body += ''.join('<li><span aria-hidden="true">✓</span><div>'+html.escape(x)+'</div></li>' for x in data['checks'])+'</ul></section>'
    body += '<p class="editorial-note">※ 취급 여부와 거래 조건은 해당 판매처·매입처에 확인해 주세요. 상품권 전체 번호와 개인정보는 공개 게시판에 올리지 마세요.</p>'
    body += '<nav class="editorial-links" aria-label="관련 안내"><a href="/guide.html">이용 안내 →</a><a href="/faq.html">자주 묻는 질문 →</a></nav>'
    body += f'<a class="editorial-cta" href="{CHAT}" target="_blank" rel="nofollow noopener noreferrer">궁금한 점, 채널톡으로 물어보세요 →</a>'
    body += '<p class="editorial-note">운영팀이 정리한 자주 묻는 질문 안내입니다.<br>실제 고객 후기나 접수된 문의가 아닙니다.</p>'
    return body


def render(board, topic, data, day, root=ROOT, banner=None):
    validate(data)
    if banner and not re.fullmatch(r'board-img/(purchase|sale)/[a-zA-Z0-9-]+\.png', banner):
        raise ValueError('잘못된 배너 경로입니다.')
    name, sample = BOARDS[board]
    rows_path = root / f'board/{board}/list.json'
    rows = read_json(rows_path)
    post_id = max(x['id'] for x in rows) + 1
    path = root / f'board/{board}/{post_id}.html'
    if path.exists():
        raise ValueError('이미 존재하는 글 번호입니다.')
    title = '[이용 안내] ' + topic
    url = f'{DOMAIN}/board/{board}/{post_id}'
    image_url = f'{DOMAIN}/{banner}' if banner else DOMAIN+'/img/og_img.png'
    esc = html.escape
    source = (root / f'board/{board}/{sample}.html').read_text(encoding='utf-8')
    source = replace_one(r'<title>.*?</title>', f'<title>{esc(title)} | {name}</title>', source)
    for attr, field, value in [('name','description',data['summary']), ('property','og:description',data['summary']),
                               ('property','og:title',title), ('property','og:url',url),
                               ('property','og:image',image_url)]:
        source = replace_one(f'<meta {attr}="{field}" content="[^"]*"[^>]*>', f'<meta {attr}="{field}" content="{esc(value)}">', source)
    source = replace_one(r'<link rel="canonical" href="[^"]*"[^>]*>', f'<link rel="canonical" href="{url}">', source)
    if banner:
        # 공유 미리보기에도 해당 글의 배너를 사용합니다.
        for attr, field, value in [('name', 'twitter:image', image_url),
                                   ('property', 'og:image:alt', topic+' 안내 배너')]:
            tag = f'<meta {attr}="{field}" content="{esc(value)}">'
            pattern = f'<meta {attr}="{field}" content="[^"]*"[^>]*>'
            source = (replace_one(pattern, tag, source) if re.search(pattern, source)
                      else source.replace('</head>', tag+'\n</head>', 1))
    schema = {'@context':'https://schema.org','@type':'Article','headline':title,'description':data['summary'],
              'author':{'@type':'Organization','name':AUTHOR},'publisher':{'@type':'Organization','name':'한국상품권거래소'},
              'mainEntityOfPage':url,'datePublished':day.isoformat(),'image':image_url}
    source = replace_one(r'<script type="application/ld\+json">.*?</script>', '<script type="application/ld+json">'+json.dumps(schema,ensure_ascii=False).replace('<','\\u003c')+'</script>', source)
    body = article_body(data)
    if banner:
        body = (f'<figure style="margin:0 0 28px"><img src="/{banner}" width="1536" height="1024" '
                f'alt="{esc(topic)} 안내 배너" decoding="async" '
                'style="display:block;width:100%;height:auto;border-radius:12px" />'
                '<figcaption style="font-size:12px;color:#687487;margin-top:8px">'
                '글의 이해를 돕기 위한 AI 생성 안내 이미지</figcaption></figure>') + body
    fragment = f'''<div id="view_wrap" class="view-wrap">
<div class="view_title"><div class="wrap"><p>{name}</p><span>상품권 이용 전 궁금한 내용을 확인해 보세요.</span></div></div>
<div class="view_content"><h1 class="board_title">{esc(title)}</h1>
<div class="heading"><span class="sv_member">{AUTHOR}</span><span>{day.strftime('%y.%m.%d')}</span><span>조회 <em id="hit_view" data-base="0" style="font-style:normal">0</em></span></div>
<div class="wrap"><article class="view-content editorial-guide">{body}</article></div>
<div class="view-nav"><a class="list-btn" href="/board/{board}/">목록으로</a></div></div></div>
<script>fetch('/api/views/{board}/{post_id}').then(function(r){{return r.json();}}).then(function(d){{if(d && typeof d.n === 'number')document.getElementById('hit_view').textContent=d.n.toLocaleString();}}).catch(function(){{}});</script>
'''
    start = source.index('<div id="view_wrap"')
    end = source.index('</div><footer id="general_tail">', start)
    source = source[:start] + fragment + source[end:]
    source = source.replace('</head>', EDITORIAL_CSS+'</head>', 1)
    source = source.replace('width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0','width=device-width, initial-scale=1.0')
    entry = {'id':post_id,'num':max(x['num'] for x in rows)+1,'cat':'기타','title':title,'author':AUTHOR,'date':day.strftime('%y.%m.%d'),'hit':0,'cmt':0,'notice':False}
    rows.insert(0,entry)
    index_path = root / f'board/{board}/index.html'
    index = index_path.read_text(encoding='utf-8')
    table = ''
    for row in rows[:20]:
        table += f'<tr onclick="goPost({row["id"]})"><td class="text-center font-11">{row["num"]}</td><td class="text-center">{esc(row["cat"])}</td><td class="list-subject"><a href="/board/{board}/{row["id"]}.html">{esc(row["title"])}</a></td><td>{esc(row["author"])}</td><td class="text-center">{esc(row["date"])}</td><td class="text-center">{row["hit"]}</td></tr>'
    index = replace_one(r'<tbody[^>]*>.*?</tbody>', '<tbody id="board_rows">'+table+'</tbody>', index)
    # 기존 렌더러가 사용하는 tbody ID를 그대로 보존합니다.
    original = re.search(r'<tbody([^>]*)>', index_path.read_text(encoding='utf-8')).group(1)
    index = index.replace('<tbody id="board_rows">','<tbody'+original+'>',1)
    index = re.sub(r'총 \d+건\.',f'총 {len(rows)}건.',index)
    latest_path = root / 'data/latest_posts.json'
    latest = read_json(latest_path)
    latest[board] = [{k:x[k] for k in ('id','cat','title','author','date')} for x in rows[:5]]
    sitemap_path = root / 'sitemap-boards.xml'
    sitemap = sitemap_path.read_text(encoding='utf-8').replace('</urlset>',f'  <url><loc>{url}</loc><lastmod>{day.isoformat()}</lastmod></url>\n</urlset>')
    history_path = root / 'data/editorial_history.json'
    history = read_json(history_path) if history_path.exists() else []
    history.append({'board':board,'id':post_id,'topic':topic,'drafted_at':day.isoformat()})
    updates = {path:source, rows_path:json.dumps(rows,ensure_ascii=False), index_path:index,
               latest_path:json.dumps(latest,ensure_ascii=False,indent=1)+'\n',sitemap_path:sitemap,
               history_path:json.dumps(history,ensure_ascii=False,indent=2)+'\n'}
    for file, content in updates.items():
        file.write_text(content,encoding='utf-8')
    review = f'# {title}\n\n작성자: {AUTHOR}\n\n{data["summary"]}\n\n'
    for section in data['sections']:
        review += f'## {section["heading"]}\n\n{section["body"]}\n\n'
    review += '## 문의 전, 이것만 챙겨두세요\n\n'+'\n'.join('- ✓ '+x for x in data['checks'])
    review += '\n\n---\nAI가 작성한 운영팀 안내 초안입니다. 실제 고객 후기가 아닙니다.\n\n- [ ] 내용과 사업 조건 확인\n- [ ] 실제 고객 후기처럼 보이는 표현이 없는지 확인\n- [ ] 게시할 준비가 되면 **Merge pull request** 실행\n\n승인 리뷰만으로는 게시되지 않습니다. main에 병합해야 배포됩니다.\n'
    return title, review, [str(p.relative_to(root)) for p in updates]
