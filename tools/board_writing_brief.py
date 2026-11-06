"""Carry the independent planner's concrete writing requirements into the article."""
import re

WRITING_BRIEF_RULES = '''topic_plan에 writing_brief가 있을 때만 다음 집필 기준을 적용한다.
writing_brief는 독립 기획 검수자가 승인한 집필 기준이다.
gap은 기존 글의 답만으로 해결되지 않는 구체적인 판단 차이다. 단순한 유형 추가나 용어 설명은 차이가 아니다.
example은 실제 고객 사례가 아닌 조건부 설명 예시다. 실제 업체 정책·숫자·금액·앱 기능을 가정하지 않는다.
section_actions의 각 항목은 본문의 해당 절에서 독자가 직접 실행할 행동과 그 결과다.
본문에는 example의 상황에서 그 행동을 어떻게 적용하고 어떤 결과를 얻는지 실제로 설명한다.
기획의 차별점을 되풀이 주장하거나 일반적인 확인·메모·문의 안내로 대체하지 않는다.
result는 독자가 글을 읽은 뒤 실제로 완성할 판단이나 결과다. 입력의 신규성 주장은 최종 검수를 대신하지 않는다.'''


def brief_schema(paths):
    text = {'type': 'string'}
    return {'type': ['object', 'null'], 'additionalProperties': False,
            'required': ['compared_paths', 'gap', 'example', 'section_actions', 'result'],
            'properties': {'compared_paths': {'type': 'array', 'maxItems': 3 if paths else 0,
                'items': {'type': 'string', 'enum': sorted(paths)} if paths else text},
                'gap': text, 'example': text, 'result': text,
                'section_actions': {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': text}}}


def validate_brief(value, paths, selected):
    if not selected:
        if value is not None:
            raise ValueError('보류한 기획에 승인 집필 기준이 있습니다.')
        return None
    if not isinstance(value, dict) or set(value) != {'compared_paths', 'gap', 'example', 'section_actions', 'result'}:
        raise ValueError('승인 기획의 집필 기준이 없습니다.')
    refs = value['compared_paths']
    if (not isinstance(refs, list) or len(refs) > 3 or
            any(not isinstance(p, str) or p not in paths for p in refs) or
            len(set(refs)) != len(refs) or (paths and not refs)):
        raise ValueError('집필 기준의 비교 글이 허용 목록과 다릅니다.')
    actions = value['section_actions']
    if not isinstance(actions, list) or len(actions) != 3:
        raise ValueError('집필 기준의 절별 행동이 누락됐습니다.')
    for text in [value['gap'], value['result'], *actions]:
        if not isinstance(text, str) or not 12 <= len(text) <= 240:
            raise ValueError('집필 기준 설명 길이 오류')
    if not isinstance(value['example'], str) or not 20 <= len(value['example']) <= 400:
        raise ValueError('집필 기준의 조건부 예시 오류')
    if len({x.strip() for x in actions}) != 3:
        raise ValueError('집필 기준의 절별 행동이 반복됩니다.')
    if re.search(r'\d|https?://|[<>%％]|현금화|카드깡|급전', ' '.join([value['gap'], value['example'], value['result'], *actions])):
        raise ValueError('집필 기준이 글 작성 제한과 충돌합니다.')
    return value
