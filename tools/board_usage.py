"""API 응답 사용량과 기준 단가를 기록합니다. 청구서가 아닌 예상 비용입니다."""
import datetime as dt
import json
import os
from pathlib import Path

PRICE_DATE = '2026-10-20'
PRICE_SOURCE = 'https://developers.openai.com/api/docs/pricing'
RATES = {
    'gpt-4.1-mini': {'input': 0.40, 'cached': 0.10, 'output': 1.60},
    'gpt-5.4-mini': {'input': 0.75, 'cached': 0.075, 'output': 4.50},
    'gpt-image-2': {'text_input': 5.00, 'image_input': 8.00, 'output': 30.00},
}


def estimate(kind, model, usage):
    rates = RATES.get(model)
    if not rates or not all(isinstance(usage.get(k), int) and usage[k] >= 0
                            for k in ('input_tokens', 'output_tokens')):
        return None
    details = usage.get('input_tokens_details') or {}
    if kind in ('text', 'topic', 'editing', 'review') and model in ('gpt-4.1-mini', 'gpt-5.4-mini'):
        cached = details.get('cached_tokens', 0)
        if not isinstance(cached, int) or not 0 <= cached <= usage['input_tokens']:
            return None
        amount = ((usage['input_tokens'] - cached) * rates['input']
                  + cached * rates['cached'] + usage['output_tokens'] * rates['output'])
    elif kind == 'image' and model == 'gpt-image-2':
        text, image = details.get('text_tokens'), details.get('image_tokens')
        if not all(isinstance(n, int) and n >= 0 for n in (text, image)):
            return None
        if text + image != usage['input_tokens']:
            return None
        amount = text * rates['text_input'] + image * rates['image_input'] + usage['output_tokens'] * rates['output']
    else:
        return None
    return round(amount / 1_000_000, 8)


def begin_request(on_usage, kind, model):
    """Track the existing bound usage callback before sending an API request."""
    owner = getattr(on_usage, '__self__', None)
    if isinstance(owner, UsageLog):
        owner.begin_request(kind, model)


class UsageLog:
    def __init__(self, path, context=None):
        self.path = Path(path)
        self.records = []
        self.requests = []
        self.untracked_records = False
        self.context = context or {}

    def begin_request(self, kind, model):
        # Persist before sending; timeouts and unreadable responses remain unknown.
        self.requests.append({'kind': kind, 'model': model,
                              'started_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                              'usage_record_index': None})
        self.save('in_progress')

    def record(self, kind, model, usage):
        pending = next((r for r in reversed(self.requests)
                        if r['kind'] == kind and r['model'] == model
                        and r['usage_record_index'] is None), None)
        if pending is not None:
            pending['usage_record_index'] = len(self.records)
        else:
            self.untracked_records = True
        self.records.append({
            'kind': kind, 'model': model, 'usage': usage,
            'estimated_usd': estimate(kind, model, usage),
            'rates_usd_per_million_tokens': RATES.get(model),
            'price_checked_on': '2026-10-21' if model == 'gpt-5.4-mini' else PRICE_DATE,
            'price_source': 'https://developers.openai.com/api/docs/models/gpt-5.4-mini' if model == 'gpt-5.4-mini' else PRICE_SOURCE,
            'recorded_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        })
        self.save('in_progress')

    def save(self, status):
        costs = [r['estimated_usd'] for r in self.records]
        pending = any(r['usage_record_index'] is None for r in self.requests)
        tracked = bool(self.requests) and not self.untracked_records
        # A local validation failure does not invalidate already metered calls.
        # Legacy callbacks on failed runs remain conservative without request tracking.
        complete = (bool(costs) and None not in costs and not pending
                    and (status == 'completed' or (status == 'failed' and tracked)))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            'run_id': os.getenv('GITHUB_RUN_ID'),
            'run_attempt': os.getenv('GITHUB_RUN_ATTEMPT'),
            'context': self.context,
            'status': status, 'records': self.records,
            'request_tracking_version': 1, 'requests': self.requests,
            'accounting_status': 'complete' if complete else 'in_progress' if status == 'in_progress' else 'partial' if costs else 'unknown',
            'known_subtotal_usd': round(sum(x for x in costs if x is not None), 8),
            'estimated_total_usd': round(sum(costs), 8) if complete else None,
            'note': '단가 기준일은 price_checked_on. 실제 청구액 아님. 세금·환전 제외. 응답 없는 요청은 비용 확인 불가.',
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def markdown(self):
        lines = ['## API 사용량과 예상 비용', '',
                 '| 구분 | 모델 | 입력 토큰 | 출력 토큰 | 예상 USD |',
                 '|---|---|---:|---:|---:|']
        for r in self.records:
            u = r['usage']
            cost = '확인 불가' if r['estimated_usd'] is None else f"${r['estimated_usd']:.6f}"
            label = {'text':'글 초안','topic':'새 주제','editing':'문장 편집','review':'글·이미지 검수','image':'본문 상단 이미지'}.get(r['kind'],r['kind'])
            lines.append(f"| {label} | {r['model']} | {u.get('input_tokens', '미제공')} | {u.get('output_tokens', '미제공')} | {cost} |")
        subtotal = sum(r['estimated_usd'] or 0 for r in self.records)
        lines += ['', f'계산 가능한 요청 합계: **${subtotal:.6f}**',
                  '\n단가 기준일과 출처는 단계별 JSON의 price_checked_on/price_source를 확인하세요. 실제 청구액이 아닌 예상 비용이며 세금·환전은 제외합니다.',
                  '단가 미등록 모델·사용량 누락·응답 없는 실패 요청은 비용 확인 불가입니다.',
                  f'[단가 출처]({PRICE_SOURCE})']
        return '\n'.join(lines)
