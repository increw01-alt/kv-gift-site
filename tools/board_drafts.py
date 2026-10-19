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
        if not isinstance(section['body'], str) or not 100 <= len(section['body']) <= 650:
            raise ValueError('본문 길이 오류')
        strings.extend([section['heading'], section['body']])
    if not isinstance(data['checks'], list) or len(data['checks']) != 3:
        raise ValueError('확인 사항은 3개여야 합니다')
    if any(not isinstance(x, str) or not 10 <= len(x) <= 130 for x in data['checks']):
        raise ValueError('확인 사항 길이 오류')
    strings.extend(data['checks'])
    text = '\n'.join(strings)
    forbidden = r'https?://|www\.|[<>]|\d|[%％]|현금화|카드깡|급전|무조건|신용\s*무관|최저가|공식\s*인증|안전한\s*거래|제가|저는|제\s*경험|실제\s*고객|고객님께서|당일\s*입금|즉시\s*입금'
    if re.search(forbidden, text, re.I):
        raise ValueError('자동 검수에서 금액/수치/후기/금지 표현이 발견되어 게시를 중단했습니다.')
    return data


def generate(topic, model):
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
summary는 한국어 30~180자, sections는 정확히 세 개로 heading 3~45자와 body 100~650자,
checks는 구체적 확인 사항 세 개로 각각 10~130자. 비슷한 주의 문구를 반복하지 말고 질문에 직접 답한다.'''
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
    if result.get('status') != 'completed':
        raise ValueError('API 생성 미완료: 파일을 변경하지 않습니다.')
    output = ''.join(c['text'] for item in result.get('output', []) for c in item.get('content', []) if c.get('type') == 'output_text')
    return validate(json.loads(output))


def replace_one(pattern, replacement, text):
    text, n = re.subn(pattern, lambda m: replacement, text, count=1, flags=re.S)
    if n != 1:
        raise ValueError('사이트 템플릿이 변경되었습니다: ' + pattern[:70])
    return text


def render(board, topic, data, day, root=ROOT):
    validate(data)
    name, sample = BOARDS[board]
    rows_path = root / f'board/{board}/list.json'
    rows = read_json(rows_path)
    post_id = max(x['id'] for x in rows) + 1
    path = root / f'board/{board}/{post_id}.html'
    if path.exists():
        raise ValueError('이미 존재하는 글 번호입니다.')
    title = '[이용 안내] ' + topic
    url = f'{DOMAIN}/board/{board}/{post_id}'
    esc = html.escape
    source = (root / f'board/{board}/{sample}.html').read_text(encoding='utf-8')
    source = replace_one(r'<title>.*?</title>', f'<title>{esc(title)} | {name}</title>', source)
    for attr, field, value in [('name','description',data['summary']), ('property','og:description',data['summary']),
                               ('property','og:title',title), ('property','og:url',url),
                               ('property','og:image',DOMAIN+'/img/og_img.png')]:
        source = replace_one(f'<meta {attr}="{field}" content="[^"]*"[^>]*>', f'<meta {attr}="{field}" content="{esc(value)}">', source)
    source = replace_one(r'<link rel="canonical" href="[^"]*"[^>]*>', f'<link rel="canonical" href="{url}">', source)
    schema = {'@context':'https://schema.org','@type':'Article','headline':title,'description':data['summary'],
              'author':{'@type':'Organization','name':AUTHOR},'publisher':{'@type':'Organization','name':'한국상품권거래소'},
              'mainEntityOfPage':url,'datePublished':day.isoformat(),'image':DOMAIN+'/img/og_img.png'}
    source = replace_one(r'<script type="application/ld\+json">.*?</script>', '<script type="application/ld+json">'+json.dumps(schema,ensure_ascii=False).replace('<','\\u003c')+'</script>', source)
    body = '<p><strong>운영팀이 정리한 자주 묻는 질문 안내입니다. 실제 고객 후기나 접수된 문의가 아닙니다.</strong></p>'
    body += '<p>'+esc(data['summary'])+'</p>'
    for section in data['sections']:
        body += '<h2>'+esc(section['heading'])+'</h2><p>'+esc(section['body'])+'</p>'
    body += '<h2>상담 전 확인 사항</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in data['checks'])+'</ul>'
    body += '<p>취급 여부와 거래 조건은 해당 판매처·매입처에 확인해 주세요. 상품권 전체 번호와 개인정보는 공개 게시판에 올리지 마세요.</p>'
    body += '<p><a href="/guide.html">이용 안내</a> · <a href="/faq.html">자주 묻는 질문</a></p>'
    body += f'<p><a class="editorial-cta" href="{CHAT}" target="_blank" rel="nofollow noopener noreferrer">채널톡으로 문의하기</a></p>'
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
    css = '<style>.editorial-guide{font-size:16px;line-height:1.85;overflow-wrap:anywhere}.editorial-guide h2{font-size:22px;margin:30px 0 12px}.editorial-guide p{margin:16px 0}.editorial-guide ul{padding-left:24px;list-style:disc}.editorial-guide li{list-style:disc;margin:8px 0}.editorial-guide .editorial-cta{display:inline-block;padding:14px 22px;background:#13233e;color:#fff;border-radius:8px}</style>'
    source = source.replace('</head>', css+'</head>', 1)
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
    review += '## 상담 전 확인 사항\n\n'+'\n'.join('- '+x for x in data['checks'])
    review += '\n\n---\nAI가 작성한 운영팀 안내 초안입니다. 실제 고객 후기가 아닙니다.\n\n- [ ] 내용과 사업 조건 확인\n- [ ] 실제 고객 후기처럼 보이는 표현이 없는지 확인\n- [ ] 게시할 준비가 되면 **Merge pull request** 실행\n\n승인 리뷰만으로는 게시되지 않습니다. main에 병합해야 배포됩니다.\n'
    return title, review, [str(p.relative_to(root)) for p in updates]
