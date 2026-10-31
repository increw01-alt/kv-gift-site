"""Shared publishing policy. Dashboard input cannot increase the approved limits."""
import datetime as dt
import json
from pathlib import Path
import re

KST = dt.timezone(dt.timedelta(hours=9))
DEFAULT = {'schemaVersion': 1, 'revision': 'initial', 'enabled': True,
           'dailyTarget': 10, 'startTime': '00:17', 'endTime': '21:53',
           'timezone': 'Asia/Seoul', 'attemptLimit': 15,
           'catchUpUntil': '24:00', 'updatedAt': None}
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
    if not 0 <= first <= last <= 1435 or (target > 1 and last - first < (target - 1) * 5):
        raise ValueError('00:00~23:55 사이에서 글 사이 최소 5분 간격을 확보하세요.')
    return {key: value[key] for key in FIELDS}


def load_settings(root, required=False):
    path = Path(root) / 'data/editorial_settings.json'
    if not path.exists() and not required:
        return dict(DEFAULT)
    value = json.loads(path.read_text(encoding='utf-8'))
    if (value.get('schemaVersion') != 1 or value.get('timezone') != 'Asia/Seoul'
            or value.get('attemptLimit') != 15 or value.get('catchUpUntil') not in ('23:00', '24:00')
            or not re.fullmatch(r'initial|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', str(value.get('revision', '')))):
        raise ValueError('저장된 자동 게시 설정을 확인하세요.')
    validate(value)
    if minute(value['endTime']) >= cutoff_minute(value):
        raise ValueError('마지막 목표는 보충 종료 시각보다 빨라야 합니다.')
    return value


def cutoff_minute(settings):
    # Keep existing immutable revisions readable while migrating to midnight.
    return 1440 if settings['catchUpUntil'] == '24:00' else 1380


def target_at(now, settings):
    if not settings['enabled']:
        return 0
    local = now.astimezone(KST)
    current = local.hour * 60 + local.minute
    start, end = minute(settings['startTime']), minute(settings['endTime'])
    target = settings['dailyTarget']
    if current < start or current >= cutoff_minute(settings):
        return 0
    if target == 1 or current >= end:
        return target
    return min(target, (current - start) * (target - 1) // (end - start) + 1)
