"""Read-only cooldown for repeated novelty holds; does not alter daily budgets."""
import datetime as dt
import json
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except ValueError:
        return None


def attempt_time(record):
    context = (record.get('api_usage') or {}).get('context') or {}
    return timestamp(record.get('attempt_started_at') or context.get('attempt_started_at')
                     or record.get('scheduled_at'))


def novelty_hold(record):
    if record.get('status') != 'held':
        return False
    issues = ' '.join((record.get('review') or {}).get('issues') or [])
    return any(marker in issues for marker in ('중복', '주제 사전 검수 보류', '다른 독자 문제', '기존 본문과 같은 질문'))


def retry_state(root, day):
    records = [json.loads(path.read_text(encoding='utf-8'))
               for path in (Path(root)/'data/editorial_runs'/day.isoformat()).glob('*.json')]
    floor = dt.datetime.combine(day, dt.time(), tzinfo=KST)
    records.sort(key=lambda r: (attempt_time(r) or floor, str(r.get('run_id', '')).zfill(24)), reverse=True)
    streak = 0
    for record in records:
        if not novelty_hold(record):
            break
        streak += 1
    last = attempt_time(records[0]) if records and streak else None
    minutes = min(120, 30 * 2**min(streak-1, 2)) if streak and last else 0
    return {'consecutiveTopicHolds': streak,
            'retryAfter': (last+dt.timedelta(minutes=minutes)).isoformat() if minutes else None,
            'cooldownMinutes': minutes}


def retry_guard(root, day, now):
    state = retry_state(root, day)
    deadline = timestamp(state['retryAfter'])
    if deadline and now < deadline:
        return (f"중복·주제 검수 보류 {state['consecutiveTopicHolds']}회 연속으로 "
                f"한국 시간 {deadline.astimezone(KST):%H:%M}까지 대기합니다. "
                '이번 점검은 API를 호출하거나 생성 시도를 차감하지 않습니다.')
    return None
