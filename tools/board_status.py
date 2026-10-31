"""Public operational summary; contains no credentials or private customer data."""
import datetime as dt
import json
from pathlib import Path
from editorial_settings import load_settings
from board_archive import write_archive
from board_retry import retry_state

KST = dt.timezone(dt.timedelta(hours=9))


def build_status(root, day, now=None):
    settings = load_settings(root)
    records = []
    for path in sorted((Path(root)/'data/editorial_runs'/day.isoformat()).glob('*.json')):
        item = json.loads(path.read_text(encoding='utf-8'))
        usage = item.get('api_usage', {})
        complete = item.get('status') != 'generating' and usage.get('estimated_total_usd') is not None
        known_cost = usage.get('known_subtotal_usd')
        if known_cost is None and complete:
            known_cost = usage['estimated_total_usd']
        records.append({
            'runId': item.get('run_id', path.stem), 'status': item['status'],
            'board': item.get('board'), 'topic': item.get('topic'), 'url': item.get('url'),
            'triggerEvent': item.get('trigger_event'), 'triggerSource': item.get('trigger_source'),
            'scheduledAt': item.get('scheduled_at'),
            'publicVerifiedAt': item.get('public_verified_at'),
            'estimatedUsd': usage.get('estimated_total_usd') if complete else None,
            'knownSubtotalUsd': known_cost,
        })
    costs = [r['estimatedUsd'] for r in records]
    return {
        'schemaVersion': 1, 'generatedAt': (now or dt.datetime.now(dt.timezone.utc)).isoformat(),
        'dateKst': day.isoformat(), 'dailyTarget': settings['dailyTarget'], 'attemptLimit': 15,
        'published': sum(r['status'] == 'published' for r in records),
        'verified': sum(r['status'] == 'published' and bool(r['publicVerifiedAt']) for r in records),
        'attempts': len(records), 'held': sum(r['status'] == 'held' for r in records),
        'errors': sum(r['status'] in ('error', 'push_failed') for r in records),
        'knownSubtotalUsd': round(sum(r['knownSubtotalUsd'] for r in records if r['knownSubtotalUsd'] is not None), 8),
        'estimatedTotalUsd': round(sum(costs), 8) if all(c is not None for c in costs) else None,
        'records': records,
        'topicRetry': retry_state(root, day),
    }


def write_status(root, day):
    path = Path(root)/'data/editorial_status.json'
    path.write_text(json.dumps(build_status(root, day), ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    write_archive(root)
    return path.relative_to(root).as_posix()
