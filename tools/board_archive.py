"""Sanitized publication and API-cost history, rebuilt from durable ledgers."""
import datetime as dt
import json
import math
from pathlib import Path
import re

KST = dt.timezone(dt.timedelta(hours=9))


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def amount(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def charge_date(at, fallback):
    try:
        instant = dt.datetime.fromisoformat(at.replace('Z', '+00:00'))
        if instant.tzinfo is None:
            raise ValueError('timezone required')
        return at, instant.astimezone(KST).date().isoformat()
    except (ValueError, AttributeError, TypeError):
        return None, fallback


def usage_charges(entry, usage):
    rows = []
    for item in usage.get('records', []):
        at, day = charge_date(item.get('recorded_at_utc'), entry['dateKst'])
        cost = amount(item.get('estimated_usd'))
        tokens = item.get('usage') or {}
        rows.append({'entryId': entry['id'], 'dateKst': day, 'recordedAt': at,
                     'kind': item.get('kind', 'unknown'), 'estimatedUsd': cost,
                     'knownSubtotalUsd': cost or 0, 'requests': 1,
                     'inputTokens': tokens.get('input_tokens') if type(tokens.get('input_tokens')) is int else None,
                     'outputTokens': tokens.get('output_tokens') if type(tokens.get('output_tokens')) is int else None})
    for request in usage.get('requests', []):
        if request.get('usage_record_index') is not None:
            continue
        at, day = charge_date(request.get('started_at_utc'), entry['dateKst'])
        rows.append({'entryId': entry['id'], 'dateKst': day, 'recordedAt': at,
                     'kind': request.get('kind', 'unknown'), 'estimatedUsd': None,
                     'knownSubtotalUsd': 0, 'requests': 1,
                     'inputTokens': None, 'outputTokens': None})
    total = amount(usage.get('estimated_total_usd'))
    known = amount(usage.get('known_subtotal_usd'))
    if not rows:
        rows.append({'entryId': entry['id'], 'dateKst': entry['dateKst'], 'recordedAt': None,
                     'kind': 'unrecorded', 'estimatedUsd': total,
                     'knownSubtotalUsd': known if known is not None else total or 0,
                     'requests': 0, 'inputTokens': None, 'outputTokens': None})
    elif total is None and all(row['estimatedUsd'] is not None for row in rows):
        # A failed/in-progress run can have some metered calls but not a complete bill.
        rows.append({'entryId': entry['id'], 'dateKst': rows[-1]['dateKst'], 'recordedAt': None,
                     'kind': 'unrecorded', 'estimatedUsd': None, 'knownSubtotalUsd': 0,
                     'requests': 0, 'inputTokens': None, 'outputTokens': None})
    return rows


def build_archive(root, now=None):
    root = Path(root)
    entries, charges, urls = [], [], set()
    for path in sorted((root/'data/editorial_runs').glob('*/*.json')):
        item = read(path)
        day = item.get('date_kst', path.parent.name)
        dt.date.fromisoformat(day)
        run_id = str(item.get('run_id', path.stem))
        if not run_id.isdigit():
            raise ValueError('Invalid archive run ID')
        usage = item.get('api_usage') or {}
        entry = {'id': 'run:'+run_id, 'runId': run_id, 'dateKst': day,
                 'dateBasis': 'run_day', 'status': item['status'], 'board': item.get('board'),
                 'topic': item.get('topic'), 'url': item.get('url'),
                 'publicVerifiedAt': item.get('public_verified_at'),
                 'source': item.get('trigger_source') or 'manual',
                 'estimatedUsd': amount(usage.get('estimated_total_usd')),
                 'knownSubtotalUsd': amount(usage.get('known_subtotal_usd'))}
        entries.append(entry)
        charges.extend(usage_charges(entry, usage))
        if entry['url']:
            urls.add(entry['url'])
    for item in read(root/'data/editorial_history.json', []):
        board, post_id = item.get('board', ''), str(item.get('id', ''))
        if not re.fullmatch(r'[a-z_]+', board) or not post_id.isdigit():
            continue
        url = f'https://kv-gift.co.kr/board/{board}/{post_id}'
        # Draft metadata alone is not proof that a post was added to the site.
        if url in urls or not (root/'board'/board/f'{post_id}.html').is_file():
            continue
        day = item['drafted_at']
        dt.date.fromisoformat(day)
        usage = {}
        if item.get('usage_file'):
            usage_path = (root/item['usage_file']).resolve()
            if usage_path.is_relative_to((root/'data').resolve()):
                value = read(usage_path, {})
                usage = value.get('api_usage', value)
        entry = {'id': f'post:{board}:{post_id}', 'runId': usage.get('run_id'),
                 'dateKst': day, 'dateBasis': 'recorded_day', 'status': 'published',
                 'board': board, 'topic': item.get('topic'), 'url': url,
                 'publicVerifiedAt': None, 'source': item.get('publication_mode') or 'user_approved',
                 'estimatedUsd': amount(usage.get('estimated_total_usd')),
                 'knownSubtotalUsd': amount(usage.get('known_subtotal_usd'))}
        entries.append(entry)
        charges.extend(usage_charges(entry, usage))
        urls.add(url)
    days = [r['dateKst'] for r in entries] + [r['dateKst'] for r in charges]
    return {'schemaVersion': 1, 'generatedAt': (now or dt.datetime.now(dt.timezone.utc)).isoformat(),
            'coverageStart': min(days) if days else None, 'timezone': 'Asia/Seoul',
            'records': entries, 'charges': charges}


def write_archive(root):
    path = Path(root)/'data/editorial_archive.json'
    path.write_text(json.dumps(build_archive(root), ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    return path.relative_to(root).as_posix()
