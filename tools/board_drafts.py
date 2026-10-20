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
from urllib.parse import urlsplit
from board_profiles import PROFILES, ROTATION

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = '한국상품권거래소 운영팀'
DOMAIN = 'https://kv-gift.co.kr'
CHAT = 'https://koreagiftcard.channel.io/home?page=board-guide'
BOARDS = {key: value['name'] for key, value in PROFILES.items()}
TEMPLATE = 'board/general_notice/42.html'
KST = dt.timezone(dt.timedelta(hours=9))


class NoTopic(ValueError):
    """유효한 주제가 없으면 API 호출 전에 정상적으로 건너뜁니다."""


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def normalized(text):
    return re.sub(r'[^가-힣a-z0-9]', '', text.lower())


def news_brief(topic, root=ROOT, day=None):
    day = day or dt.datetime.now(KST).date()
    for brief in read_json(root / 'tools/board_news_briefs.json'):
        if brief.get('topic') != topic:
            continue
        if not dt.date.fromisoformat(brief['verified_on']) <= day <= dt.date.fromisoformat(brief['expires_on']):
            continue
        if not brief.get('facts') or not all(isinstance(x, str) and x.strip() for x in brief['facts']):
            continue
        if not brief.get('sources'):
            continue
        for source in brief['sources']:
            parsed = urlsplit(source['url'])
            if parsed.scheme != 'https' or parsed.netloc != 'kv-gift.co.kr' or not source.get('title'):
                raise ValueError('협회 소식은 확인된 운영 사이트 자료를 사용해야 합니다.')
            path = root / parsed.path.lstrip('/')
            if not path.is_file() and not path.with_suffix('.html').is_file():
                raise ValueError('협회 소식의 확인 자료가 저장소에 없습니다.')
        return brief
    raise NoTopic('사용 가능한 확인 자료가 없습니다. 협회 소식은 자료 확인 후 작성합니다.')


def pick_topic(board, root=ROOT, day=None):
    if board not in BOARDS:
        raise ValueError('게시판 선택 오류')
    topics = read_json(root / 'tools/board_topics.json').get(board, [])
    if PROFILES[board].get('requires_brief'):
        topics = [b['topic'] for b in read_json(root / 'tools/board_news_briefs.json')]
    rows = read_json(root / f'board/{board}/list.json')
    history = read_json(root / 'data/editorial_history.json') if (root / 'data/editorial_history.json').exists() else []
    # 게시판을 바꾸어 같은 주제를 재생산하지 않습니다.
    used = {normalized(x['topic']) for x in history}
    titles = [normalized(x['title']) for x in rows] + list(used)
    for topic in topics:
        if normalized(topic) in used or any(difflib.SequenceMatcher(None, normalized(topic), t).ratio() >= .82 for t in titles):
            continue
        if PROFILES[board].get('requires_brief'):
            try:
                news_brief(topic, root, day)
            except NoTopic:
                continue
        return topic
    raise NoTopic('미사용 주제 또는 유효한 확인 자료가 없습니다.')


def select_board(requested='auto', root=ROOT, day=None):
    if requested != 'auto':
        return requested, pick_topic(requested, root, day)
    history_path = root / 'data/editorial_history.json'
    history = read_json(history_path) if history_path.exists() else []
    last = next((x['board'] for x in reversed(history) if x.get('automation') and x['board'] in ROTATION), None)
    start = (ROTATION.index(last) + 1) % len(ROTATION) if last else 0
    for offset in range(len(ROTATION)):
        board = ROTATION[(start + offset) % len(ROTATION)]
        try:
            return board, pick_topic(board, root, day)
        except NoTopic:
            continue
    raise NoTopic('모든 게시판의 준비된 주제가 소진되었습니다. 새 주제 또는 확인 자료가 필요합니다.')


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


def generate(topic, model, on_usage=None, board='purchase', root=ROOT, day=None):
    profile = PROFILES[board]
    brief = news_brief(topic, root, day) if profile.get('requires_brief') else None
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
    instructions += ('\n이 글을 넣을 게시판: ' + profile['name']
                     + '\n게시판 편집 기준: ' + profile['purpose']
                     + '\n세 절의 역할: ' + profile['outline']
                     + '\n각 절은 서로 다른 구체적 내용을 설명한다. 모든 절을 문의하라는 말로 끝내지 않는다.'
                     + '\n협회 소식의 확인 자료가 주어지면 그 안의 사실만 사용하고 새로운 사건이나 성과를 덧붙이지 않는다.')
    payload = {'model': model, 'store': False, 'max_output_tokens': 2600,
               'instructions': instructions, 'input': json.dumps({'topic': topic, 'verified_brief': brief}, ensure_ascii=False),
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


def render(board, topic, data, day, root=ROOT, banner=None):
    from board_render import render_post
    validate(data)
    brief = news_brief(topic, root, day) if PROFILES[board].get('requires_brief') else None
    return render_post(board, topic, data, day, root, banner, brief)
