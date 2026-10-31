"""Bounded, unverified planning backlog, replenished by the existing topic request."""
import json
from pathlib import Path

POOL_LIMIT = 12
REFILL_BELOW = 2
FIELDS = ('topic', 'source_id', 'task_id', 'reader_problem', 'distinct_angle', 'outline',
          'reader_situation', 'deliverable')
LANES = {
    'gc_tip': ['잔액과 추가 결제액을 구분해 사용 순서를 결정하는 계산', '여러 사용 기한을 달력에 배치하는 우선순위', '실물 종이의 보관 장소와 손상 예방', '가족별 사용 계획과 남은 잔액의 대조'],
    'purchase': ['액면가가 다른 선택지의 실제 지출 비교', '원래 필요한 물건과 선물 예산의 적합성 판단', '사용 장소와 이동 동선을 고려한 선택', '여러 수신자의 용도에 맞춰 금액을 배분하는 기준'],
    'gc_information': ['발행사와 판매처와 사용처의 역할 관계도', '지류와 모바일과 교환권의 상태 전환 구분', '액면가와 판매가와 잔액의 용어 차이', '동일한 이름처럼 보이는 상품 종류를 분류하는 기준'],
    'sale': ['보유 목적과 사용할 계획을 대조하는 선택 기준', '제시 금액과 실제 정산 내역의 항목 대조', '사용한 상품권과 사용하지 않은 상품권의 분류', '한 장의 금액과 여러 장의 합계에서 생기는 계산 실수'],
    'general_notice': ['키보드와 모바일 화면으로 정보에 접근하는 방법', '문서 글자 크기와 읽는 순서의 접근성', '공용 기기에서 파일을 남기지 않는 이용 습관', '공개 문의와 비공개 문의에 적합한 정보의 구분'],
    'sense': ['한정된 예산 안에서 선물의 쓰임새를 비교하는 기준', '모임의 참여 방식에 따른 역할 배분', '물건을 늘리지 않는 선물 선택과 보관 부담', '이동 거리와 이용 시간을 함께 생각하는 생활 계획'],
    'free': ['서로 다른 선택 기준을 비교하는 운영팀 질문', '선물 사용 계획을 바꾸게 된 판단 기준', '편의성과 선택의 폭 사이에서 고르는 질문', '개인 경험을 주장하지 않고 여러 관점을 비교하는 질문'],
}


def pool_path(root):
    return Path(root)/'data/editorial_topic_pool.json'


def load_pool(root):
    path = pool_path(root)
    if not path.exists():
        return {'schemaVersion': 1, 'boards': {}}
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schemaVersion') != 1 or not isinstance(value.get('boards'), dict):
        raise ValueError('주제 대기열 형식 오류')
    return value


def pending_plans(root, board):
    plans = load_pool(root)['boards'].get(board, [])
    if not isinstance(plans, list) or len(plans) > POOL_LIMIT:
        raise ValueError('주제 대기열 크기 오류')
    return plans


def clean_plan(plan):
    return {key: plan[key] for key in FIELDS if key in plan}


def pool_update(board, plans):
    unique = {}
    for plan in plans:
        unique.setdefault(plan['topic'], clean_plan(plan))
    return {'board': board, 'pending': list(unique.values())[:POOL_LIMIT]}


def apply_pool_update(root, update):
    """Called only while recording the outcome, after main has been synchronized."""
    if not update:
        return None
    if update.get('board') not in LANES or not isinstance(update.get('pending'), list):
        raise ValueError('주제 대기열 갱신 오류')
    value = load_pool(root)
    value['boards'][update['board']] = pool_update(update['board'], update['pending'])['pending']
    path = pool_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    return path.relative_to(root).as_posix()


def expansion_focus(root, board, day):
    lanes = LANES[board]
    previous = list((Path(root)/'data/editorial_runs'/day.isoformat()).glob('*.json'))
    offset = (day.toordinal()+len(previous)) % len(lanes)
    return {'purpose': '새 독자 문제 공급용 방향이며 사실·정책·고객 사례가 아님',
            'directions': [lanes[offset], lanes[(offset+1) % len(lanes)]],
            'requirements': ['이미 있는 답으로 해결되지 않는 구체적인 결정 상황',
                             '비교 기준·계산 순서·분류 결과처럼 독자가 직접 완성할 결과물',
                             '새 약관·금액·혜택·업체 정책을 만들지 않는 내용']}
