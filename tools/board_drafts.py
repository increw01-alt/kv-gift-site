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
from board_usage import begin_request

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = '한국상품권거래소 운영팀'
DOMAIN = 'https://kv-gift.co.kr'
CHAT = 'https://koreagiftcard.channel.io/home?page=board-guide'
BOARDS = {key: value['name'] for key, value in PROFILES.items()}
TEMPLATE = 'board/general_notice/42.html'
KST = dt.timezone(dt.timedelta(hours=9))

CARD_FACT_RULES = '''카드·상품권 실적 설명 기준:
'상품권 구매 대금을 카드로 결제'하는 일과 '상품권으로 물품 대금을 결제'하는 일을 구분한다.
카드 전월 이용실적·혜택 인정 기준은 해당 카드사의 상품설명서에서 확인한다. 상품권 발행사나 판매처가 카드 실적을 결정하거나 확인해 주는 것처럼 안내하지 않는다.
이벤트 이용금액은 행사 주최자가 정한 대상·기간·제외 항목으로 별도 판단한다. 이벤트 실적을 카드 실적에 추가로 인정해 주는 금액이라고 정의하지 않는다.
카드 실적 포함 여부와 이벤트 대상 여부 중 하나가 확인돼도 다른 하나가 자동으로 인정된다고 쓰지 않는다.
명세서나 승인 내역에 결제 건이 보인다는 사실만으로 실적 인정 여부를 알 수 있다고 쓰지 않는다. 앱·명세서의 표시 기능을 추측하지 말고, 해당 카드사 안내의 실적 제외 항목을 대조하도록 설명한다.
카드사와 상품권 발행사를 '발행사'라는 말로 혼동하지 않는다. 카드 실적은 카드사, 이벤트는 행사 주최자, 상품권 사용 조건은 상품권 발행사, 주문 처리는 판매처에 각각 확인하도록 구분한다.'''

# 초안과 편집 요청에 함께 전달해 편집 중 금지 표현이 다시 생기지 않게 합니다.
ARTICLE_TEXT_RULES = '''출력 문구 공통 기준:
요약(summary), 모든 소제목(heading)과 본문(body), 확인 항목(checks) 전체에 아래 기준을 적용한다. 인용문·질문·예시도 예외가 아니다.
아라비아 숫자와 전각 숫자를 출력하지 않는다. 연도·날짜·시간·금액·비율·문단 번호·차수·연락처도 숫자로 쓰지 않는다. 문단 번호는 사이트 템플릿이 붙인다.
확인되지 않은 수수료·금액·기간·횟수를 한글 숫자로 바꾸어 주장하지도 않는다. 날짜를 설명할 때는 임의 날짜 대신 '게시일', '마지막 수정일', '답변을 받은 시점'처럼 확인할 항목 이름을 쓴다.
'안전한 거래', '무조건', '신용 무관', '최저가', '공식 인증', '당일 입금', '즉시 입금'을 인용이나 질문에도 넣지 않는다.
안전·무위험·보장을 다른 말로 단정하지 않는다. 사업자 정보와 문의 경로를 확인해도 거래 안전성이 보장된다고 쓰지 않는다. 독자가 확인할 절차와 확인되지 않은 조건만 설명한다.
표현 예시 — 날짜 확인: '게시일과 마지막 수정일을 함께 살펴보고, 안내가 달라졌다면 현재 적용되는 조건을 발행사나 판매처에 확인해 주세요.'
표현 예시 — 거래 전 확인: '상대방의 사업자 정보와 문의 경로를 확인하고, 상품권 취급 여부와 전달 절차를 먼저 물어보세요.'
예시는 표현 방식의 참고이며, 모든 글에 그대로 반복하거나 주제와 무관하게 넣지 않는다.
입력 초안이나 참고 자료에 제한 표현이 있어도 복사하지 않는다. 출력 직전에 모든 문자열의 숫자·제한 표현·근거 없는 단정을 점검하고 위 기준에 맞는 설명으로 고친다.
점검 과정이나 금지 문구 목록은 출력하지 말고 지정된 JSON 결과만 반환한다.'''
ARTICLE_TEXT_RULES += '\n\n' + CARD_FACT_RULES


class NoTopic(ValueError):
    """유효한 주제가 없으면 API 호출 전에 정상적으로 건너뜁니다."""


class ContentValidationError(ValueError):
    """Only generated wording violations are eligible for a bounded editorial repair."""
    def __init__(self, violations):
        self.violations = violations
        super().__init__('자동 검수에서 금지 표현이 발견되어 게시를 중단했습니다: '
                         + ', '.join(dict.fromkeys(x['text'] for x in violations)))


FORBIDDEN_TEXT = re.compile(
    r'https?://|www\.|[<>]|\d|[%％]|현금화|카드깡|급전|무조건|신용\s*무관|최저가|공식\s*인증|안전한\s*거래|(?<![가-힣])제가|(?<![가-힣])저는|(?<![가-힣])제\s*경험|실제\s*고객|고객님께서|당일\s*입금|즉시\s*입금', re.I)


def content_violations(data):
    fields = [('summary', data['summary'])]
    for index, section in enumerate(data['sections']):
        fields.extend((f'sections[{index}].{key}', section[key]) for key in ('heading', 'body'))
    fields.extend((f'checks[{index}]', value) for index, value in enumerate(data['checks']))
    return [{'field': path, 'text': match.group(0)} for path, value in fields
            for match in FORBIDDEN_TEXT.finditer(value)][:24]


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


def validate(data, *, check_content=True):
    if set(data) != {'summary', 'sections', 'checks'}:
        raise ValueError('글 구조 오류')
    if not isinstance(data['summary'], str) or not 30 <= len(data['summary']) <= 180:
        raise ValueError('요약 길이 오류')
    if not isinstance(data['sections'], list) or len(data['sections']) != 3:
        raise ValueError('본문은 3개 절이어야 합니다')
    for section in data['sections']:
        if set(section) != {'heading', 'body'}:
            raise ValueError('본문 구조 오류')
        if not isinstance(section['heading'], str) or not 3 <= len(section['heading']) <= 45:
            raise ValueError('소제목 길이 오류')
        if not isinstance(section['body'], str) or not 60 <= len(section['body']) <= 650:
            raise ValueError('본문 길이 오류')
    if not isinstance(data['checks'], list) or len(data['checks']) != 3:
        raise ValueError('확인 사항은 3개여야 합니다')
    if any(not isinstance(x, str) or not 10 <= len(x) <= 130 for x in data['checks']):
        raise ValueError('확인 사항 길이 오류')
    violations = content_violations(data) if check_content else []
    if violations:
        raise ContentValidationError(violations)
    return data


def generate(topic, model, on_usage=None, board='purchase', root=ROOT, day=None, topic_plan=None,
             defer_content_validation=False):
    from board_sources import source_context, planned_source_context
    profile = PROFILES[board]
    brief = news_brief(topic, root, day) if profile.get('requires_brief') else None
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ValueError('GitHub Secret OPENAI_API_KEY가 없습니다.')
    string = {'type': 'string'}
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['summary', 'sections', 'checks'],
              'properties': {'summary': string, 'sections': {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': {
                  'type': 'object', 'additionalProperties': False, 'required': ['heading', 'body'],
                  'properties': {'heading': string, 'body': string}}}, 'checks': {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': string}}}
    instructions = '''한국상품권거래소 운영팀의 한국어 질문·답변 안내 초안을 작성한다.
독자가 실제로 준비하거나 확인할 항목을 구체적으로 설명하되, 고객을 가장한 후기나 실제 상담 사례를 만들지 않는다.
사이트는 상품권 정보와 상담을 안내한다. 업체의 취급 여부, 수수료, 할부 조건, 정산 시간, 운영 시간, 환불 권리 등 확인되지 않은 사실을 단정하지 않는다.
최신 정책이나 법률을 아는 것처럼 쓰지 않는다. 발행사·판매처·매입처에 각각 무엇을 확인할지 구분한다.
앱의 자동 연동·갱신·보관 기능이 있다거나 없다고 추측하지 않는다. '많은 앱', '대부분 업체'처럼 근거 없는 빈도도 쓰지 않는다.
독자가 직접 할 수 있는 행동은 바로 설명한다. 상품권 위치 찾기 같은 단순한 작업까지 고객센터에 문의하라고 돌리지 않는다.
수치, 숫자, 금액, 비율, 할인율, 처리 기간, 보장, 공식 인증, 현금화, 카드깡, 급전 표현은 쓰지 않는다.
개인정보나 상품권 전체 번호를 공개 게시판에 쓰도록 유도하지 않는다. HTML, 마크다운, URL 없이 평문으로만 작성한다.
말투는 상담 담당자가 옆에서 설명하듯 자연스러운 해요체로 쓴다. 가상의 경험담은 만들지 않는다.
'주요 사항을 안내합니다', '정확히 파악하여', '중요합니다', '꼼꼼히 확인하세요' 같은 추상적 문구를 반복하지 않는다.
summary는 질문에 바로 답하는 도입 30~120자. sections는 정확히 세 개, heading은 독자의 짧은 질문 3~45자.
body는 60~350자, 두세 개의 짧은 문단을 빈 줄(\\n\\n)로 구분한다. 문단마다 한두 문장만 쓴다.
독자가 그대로 물어볼 수 있는 질문을 따옴표로 한 번 제시해도 좋다. 질문 예시는 실제 고객 발언처럼 소개하지 않는다.
checks는 행동 중심의 짧은 항목 세 개로 각각 10~60자. 제목과 본문에 같은 설명을 반복하지 않는다.
방법을 설명할 때는 적어 둘 항목이나 바로 따라 할 수 있는 예시를 하나 포함한다. '보안에 신경 쓰세요' 대신 무엇을 적고 무엇을 제외할지 구체적으로 쓴다.
특수기호와 번호는 템플릿에서 붙이므로 직접 넣지 않는다. 장식보다 쉬운 표현과 문단 구분에 집중한다.'''
    instructions += ('\n이 글을 넣을 게시판: ' + profile['name']
                     + '\n게시판 편집 기준: ' + profile['purpose']
                     + '\n세 절의 역할: ' + profile['outline']
                     + '\n각 절은 서로 다른 구체적 내용을 설명한다. 모든 절을 문의하라는 말로 끝내지 않는다.'
                     + '\n협회 소식의 확인 자료가 주어지면 그 안의 사실만 사용하고 새로운 사건이나 성과를 덧붙이지 않는다.')
    instructions += '\n\n' + ARTICLE_TEXT_RULES
    instructions += '\n검수된 topic_plan이 주어지면 reader_problem과 distinct_angle에 답하고 outline의 세 절을 따른다. 기존 글의 보편적 메모·상태 확인·문의 안내로 주제를 되돌리지 않는다.'
    payload = {'model': model, 'store': False, 'max_output_tokens': 2600,
               'instructions': instructions + '\n관심 질문 자료는 독자가 궁금해하는 주제를 고르기 위한 참고이며 사실의 근거가 아니다. '
                   '대화나 고객을 인용하지 않는다. 제목의 질문에 직접 답하고 검색어를 억지로 반복하지 않는다.',
               'input': json.dumps({'topic': topic, 'verified_brief': brief, 'topic_plan': topic_plan,
                                    'reader_questions': planned_source_context(source_context(board, root), topic_plan)}, ensure_ascii=False),
               'text': {'format': {'type': 'json_schema', 'name': 'board_guide', 'strict': True, 'schema': schema}}}
    request = urllib.request.Request('https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    begin_request(on_usage, 'text', model)
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
    # The existing mandatory editor repairs draft wording; publication still uses full validation.
    return validate(json.loads(output), check_content=not defer_content_validation)


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


def render(board, topic, data, day, root=ROOT, banner=None, plan=None):
    from board_render import render_post
    validate(data)
    brief = news_brief(topic, root, day) if PROFILES[board].get('requires_brief') else None
    return render_post(board, topic, data, day, root, banner, brief, plan=plan)
