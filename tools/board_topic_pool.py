"""Bounded, unverified planning backlog, replenished by the existing topic request."""
import json
from pathlib import Path
from board_topic_supply import direction_options, coverage_index

POOL_LIMIT = 12
REFILL_BELOW = 2
FIELDS = ('topic', 'source_id', 'task_id', 'reader_problem', 'distinct_angle', 'outline',
          'reader_situation', 'deliverable', 'direction_id')
LANES = {
    'gc_tip': ['잔액과 추가 결제액을 구분해 사용 순서를 결정하는 계산', '여러 사용 기한을 달력에 배치하는 우선순위', '실물 종이의 보관 장소와 손상 예방', '가족별 사용 계획과 남은 잔액의 대조'],
    'purchase': ['액면가가 다른 선택지의 실제 지출 비교', '원래 필요한 물건과 선물 예산의 적합성 판단', '사용 장소와 이동 동선을 고려한 선택', '여러 수신자의 용도에 맞춰 금액을 배분하는 기준'],
    'gc_information': ['발행사와 판매처와 사용처의 역할 관계도', '지류와 모바일과 교환권의 상태 전환 구분', '액면가와 판매가와 잔액의 용어 차이', '동일한 이름처럼 보이는 상품 종류를 분류하는 기준'],
    'sale': ['보유 목적과 사용할 계획을 대조하는 선택 기준', '제시 금액과 실제 정산 내역의 항목 대조', '사용한 상품권과 사용하지 않은 상품권의 분류', '한 장의 금액과 여러 장의 합계에서 생기는 계산 실수'],
    'general_notice': ['키보드와 모바일 화면으로 정보에 접근하는 방법', '문서 글자 크기와 읽는 순서의 접근성', '공용 기기에서 파일을 남기지 않는 이용 습관', '공개 문의와 비공개 문의에 적합한 정보의 구분'],
    'sense': ['한정된 예산 안에서 선물의 쓰임새를 비교하는 기준', '모임의 참여 방식에 따른 역할 배분', '물건을 늘리지 않는 선물 선택과 보관 부담', '이동 거리와 이용 시간을 함께 생각하는 생활 계획'],
    'free': ['서로 다른 선택 기준을 비교하는 운영팀 질문', '선물 사용 계획을 바꾸게 된 판단 기준', '편의성과 선택의 폭 사이에서 고르는 질문', '개인 경험을 주장하지 않고 여러 관점을 비교하는 질문'],
}
LANES['gc_tip'] += [
    '작은 화면에서 여러 선택 옵션을 조작할 때 선택값이 유지되는지 확인하는 실행 실험',
    '종이 안내를 펼치거나 디지털 화면을 넘길 때 떨어진 조건들을 대응시키는 읽기 기술',
    '물품 교환 후 조립·설치가 필요한 물건의 준비 공간과 순서를 실제로 배치하는 작업',
    '색상·모양에만 의존하지 않고 보유 물품을 구별하는 개인 표식 설계',
    '연결이 끊기거나 작업이 중단될 때 마지막으로 확정한 행동부터 이어가는 복구 절차',
    '선택 가능한 옵션이 여러 개인 교환 물품에서 서로 양립할 수 없는 조합을 제거하는 과정',
    '큰 글씨와 소리 안내 등 서로 다른 감각으로 같은 이용 정보를 전달하는 접근성 연습',
    '소비한 물품의 실제 사용량을 보고 다음 이용량을 줄이거나 늘리는 생활 실험',
]
LANES['purchase'] += [
    '선물을 전달하는 사람이 결정할 항목과 받는 사람이 남겨 두길 바라는 선택권의 경계',
    '희망 조건이 서로 충돌하는 구매안에서 양보할 수 없는 조건으로 후보를 제거하는 절차',
    '신뢰할 수 있는 설명의 근거와 광고의 평가 표현을 구별하는 정보 읽기',
    '주문을 확정하기 전 서로 의존하는 준비 작업을 역순으로 짜는 일정 설계',
    '여러 후보의 설명에서 같은 단어의 적용 대상이 달라 비교가 불가능한 항목을 찾는 과정',
    '직접 전달하는 선물에서 내용물과 겉포장 안내가 분리될 때 수신자가 혼동하지 않을 배치',
    '취향을 미리 묻는 과정이 선물의 놀라움을 해치지 않도록 질문 범위를 정하는 선택',
    '예산·시간·수신자 선택권 사이의 상충 관계를 의사결정 순서로 풀어내는 과정',
]
LANES['gc_information'] += [
    '안내문에서 가능·필수·제외를 나타내는 문장이 논리적으로 다른 의미를 갖는 이유',
    '접수된 사실과 실제 처리 결과를 구별하는 증거의 성격',
    '여러 조건 중 모두 충족과 하나만 충족을 구분하는 조건문의 논리',
    '정보 화면의 수정 시점과 그 정보가 적용되는 기간을 구별하는 시간 개념',
    '한 상품의 이름·별칭·분류와 서로 다른 상품의 관계를 구분하는 개념도',
    '본인 확인에 사용하는 정보와 조회에 쓰는 정보가 수행하는 역할의 차이',
    '확정된 값·예시 값·예상 값의 증거 수준과 해석 방식의 차이',
    '전체 집합과 일부 항목의 합계가 다른 경우 빠진 범위를 찾는 개념 연습',
]
LANES['sale'] += [
    '공동 보유물에서 문의 담당자 변경 시 전달 권한과 결정 권한을 혼동하지 않는 인계',
    '매입처의 추가 질문에 아직 답을 모를 때 추측과 확인 가능한 사실을 분리하는 대응',
    '여러 장의 실물 상품권을 세는 중 작업이 끊겼을 때 이중 집계를 막는 물리적 배치',
    '서로 다른 전제가 붙은 견적을 동일한 조건으로 비교할 수 있도록 기준을 맞추는 과정',
    '안내된 업무 범위 밖의 요청을 받았을 때 정보를 추가 제공하기 전에 요청 주체를 확인하는 행동',
    '상품권 일부의 상태를 아직 확인하지 못했을 때 확인 완료분과 보류분의 작업 흐름',
    '판매를 진행하지 않기로 결정한 뒤 문의를 종료하고 보유 계획으로 돌리는 정리',
    '판매 전 기대했던 결과와 실제로 확인한 결과의 차이를 원인별로 나누는 사후 점검',
]
LANES['general_notice'] += [
    '키보드만으로 링크를 따라갈 때 현재 선택 위치와 이동 순서를 인식하는 이용 방법',
    '브라우저의 자동 입력이 남긴 값과 사용자가 방금 입력한 내용을 구별하는 습관',
    '파일을 열기 전에 설치·알림·권한 요청을 읽고 원래 하려던 일과 비교하는 이용 안내',
    '정보를 공유할 때 이미지 대신 의미 있는 링크 설명을 쓰는 접근성 안내',
    '본문을 읽는 중 열린 새 화면이 원래 안내와 다른 출처인지 확인하는 행동',
    '검색에서 발견한 글의 수정 기록과 현재 본문을 혼동하지 않는 읽기 방법',
    '읽기 순서가 복잡한 표나 접힌 문단에서 빠진 행·열·조건을 찾는 방법',
    '화면 밝기·방향·입력 도구를 변경해도 원래 선택과 위치를 잃지 않는 이용 절차',
]
LANES['sense'] += [
    '불확실한 약속을 확정 일정과 분리해 다른 사람의 시간을 지키는 협의',
    '자주 쓰는 물건을 찾고 꺼내고 되돌려 놓는 동작 수를 줄이는 공간 배치',
    '불필요한 알림을 줄이되 중요한 연락을 놓치지 않는 개인 알림 분류',
    '복잡한 설명에서 정의·이유·예시를 분리해 다른 사람에게 다시 설명하는 연습',
    '한 번에 끝나지 않는 집안일을 중단하기 좋은 지점으로 나누는 작업 설계',
    '여러 사람이 함께 쓰는 물건에서 위치 표시와 사용 중 표시를 분리하는 관리',
    '문서에서 사실 문장과 자신의 의견 문장을 구분해 오해를 줄이는 편집',
    '비슷하게 생긴 물건이나 파일을 찾을 때 위치가 바뀌어도 통하는 분류 체계',
]
LANES['free'] += [
    '빠른 결정과 의견 수렴이 충돌할 때 어떤 상황에서 결정권을 맡길지 생각하는 질문',
    '개별 취향을 존중하는 선택과 모두에게 동일한 조건을 주는 선택을 비교하는 질문',
    '추천을 받을 때 좋아하는 것보다 피하고 싶은 것을 먼저 묻는 방식의 차이',
    '과거 선택의 결과를 다시 볼 때 결과의 우연과 당시 판단의 질을 구분하는 질문',
    '설명과 실제 시연 중 어느 쪽이 새로운 방법을 배우는 데 도움이 되는지 생각하는 질문',
    '모르는 것을 바로 질문할지 스스로 찾아볼지 판단할 때 고려할 비용과 시간',
    '공유 물품의 사용 편의와 원래 상태로 돌려놓을 책임을 함께 정하는 질문',
    '계획에서 선택 여지를 남겨 두는 것과 미리 확정하는 것의 부담을 비교하는 질문',
]


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


def expansion_focus(root, board, day, plans=None, index=None):
    lanes = LANES[board]
    plans = plans or []
    index = index if index is not None else coverage_index(plans, [])
    return {'purpose': '새 독자 문제 공급용 방향이며 사실·정책·고객 사례가 아님',
            'directions': direction_options(lanes, board, plans, index),
            'requirements': ['이미 있는 답으로 해결되지 않는 구체적인 결정 상황',
                             '비교 기준·계산 순서·분류 결과처럼 독자가 직접 완성할 결과물',
                             '새 약관·금액·혜택·업체 정책을 만들지 않는 내용']}
