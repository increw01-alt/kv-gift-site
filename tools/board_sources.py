"""Only bounded, non-verbatim interest signals cross from private Drive to this public repo."""
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def catalog(root=ROOT):
    return json.loads((root/'tools/editorial_source_catalog.json').read_text(encoding='utf-8'))


def validate_source(value, root=ROOT):
    fields = {'schema_version', 'source', 'checked_at', 'source_modified_at', 'source_sha256',
              'message_count', 'signals'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('참고 자료에는 허용된 집계 항목만 전달할 수 있습니다.')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['source'] != 'kakao_drive':
        raise ValueError('참고 자료 형식 오류')
    for field in ('checked_at', 'source_modified_at'):
        if not isinstance(value[field], str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z', value[field]):
            raise ValueError('자료 확인 날짜 오류')
        dt.datetime.fromisoformat(value[field].replace('Z', '+00:00'))
    if not re.fullmatch(r'[a-f0-9]{64}', str(value['source_sha256'])):
        raise ValueError('자료 지문 오류')
    if type(value['message_count']) is not int or not 1 <= value['message_count'] <= 1000000:
        raise ValueError('메시지 집계 오류')
    known = {item['id'] for item in catalog(root)}
    if not isinstance(value['signals'], list) or not 1 <= len(value['signals']) <= len(known):
        raise ValueError('관심 주제가 없는 자료입니다.')
    seen = set()
    for item in value['signals']:
        if (not isinstance(item, dict) or set(item) != {'id', 'count'} or
            item['id'] not in known or item['id'] in seen or type(item['count']) is not int or
            not 1 <= item['count'] <= value['message_count']):
            raise ValueError('허용되지 않은 관심 주제 집계입니다.')
        seen.add(item['id'])
    return value


def source_context(board, root=ROOT):
    path = root/'data/editorial_sources.json'
    if not path.exists():
        return None
    value = validate_source(json.loads(path.read_text(encoding='utf-8')), root)
    counts = {x['id']: x['count'] for x in value['signals']}
    questions = [{k: item[k] for k in ('id', 'question', 'keywords')}
                 for item in catalog(root) if board in item['boards'] and item['id'] in counts]
    questions.sort(key=lambda x: counts[x['id']], reverse=True)
    if not questions:
        return None
    return {'kind': 'anonymized_question_signals', 'checked_at': value['checked_at'],
            'source_modified_at': value['source_modified_at'], 'source_sha256': value['source_sha256'],
            'questions': questions,
            'limitations': '대화 속 관심 주제를 분류한 자료다. 원문 인용, 고객 경험 또는 현재 조건의 사실 근거가 아니다. '
                            '오래된 대화일 수 있다. 개인정보와 대화 문장은 전달하지 않는다.'}
