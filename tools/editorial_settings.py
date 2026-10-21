"""Shared publishing policy. Dashboard input cannot increase the approved limits."""
import datetime as dt
import json
from pathlib import Path
import re

KST = dt.timezone(dt.timedelta(hours=9))
DEFAULT = {'schemaVersion': 1, 'revision': 'initial', 'enabled': True,
           'dailyTarget': 10, 'startTime': '09:17', 'endTime': '18:17',
           'timezone': 'Asia/Seoul', 'attemptLimit': 15,
           'catchUpUntil': '23:00', 'updatedAt': None}
FIELDS = ('enabled', 'dailyTarget', 'startTime', 'endTime')


def minute(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError('시간은 HH:MM 형식으로 입력하세요.')
    hour, part = map(int, value.split(':'))
    return hour * 60 + part


def validate(value):
    if not isinstance(value, dict) or type(value.get('enabled')) is not bool:
        raise ValueError('자동 게시 설정 형식을 확인하세요.')
    target = value.get('dailyTarget')
    if type(target) is not int or not 1 <= target <= 10:
        raise ValueError('하루 게시 수는 1~10편입니다.')
    first, last = minute(value.get('startTime')), minute(value.get('endTime'))
    if not 540 <= first <= last <= 1375 or (target > 1 and last - first < (target - 1) * 5):
        raise ValueError('09:00~22:55 사이에서 글 사이 최소 5분 간격을 확보하세요.')
    return {key: value[key] for key in FIELDS}


def load_settings(root, required=False):
    path = Path(root) / 'data/editorial_settings.json'
    if not path.exists() and not required:
        return dict(DEFAULT)
    value = json.loads(path.read_text(encoding='utf-8'))
    if (value.get('schemaVersion') != 1 or value.get('timezone') != 'Asia/Seoul'
            or value.get('attemptLimit') != 15 or value.get('catchUpUntil') != '23:00'
            or not re.fullmatch(r'initial|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', str(value.get('revision', '')))):
        raise ValueError('저장된 자동 게시 설정을 확인하세요.')
    validate(value)
    return value


def target_at(now, settings):
    if not settings['enabled']:
        return 0
    local = now.astimezone(KST)
    current = local.hour * 60 + local.minute
    start, end = minute(settings['startTime']), minute(settings['endTime'])
    target = settings['dailyTarget']
    if current < start or current >= 1380:
        return 0
    if target == 1 or current >= end:
        return target
    return min(target, (current - start) * (target - 1) // (end - start) + 1)
