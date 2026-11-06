"""Coverage-aware idea supply. Ranking is not an originality approval."""
import hashlib
import re
from board_originality import grams


PROBLEM_FIELDS = ('reader_problem', 'reader_situation', 'deliverable', 'outline')


def normalized(value):
    return re.sub(r'[^가-힣a-z0-9]', '', str(value).lower())


def problem_text(plan):
    parts = [plan.get('topic', plan.get('question', ''))]
    for key in PROBLEM_FIELDS:
        value = plan.get(key, '')
        parts.extend(value if isinstance(value, list) else [value])
    return ' '.join(str(p) for p in parts if p)


def coverage_index(plans, articles):
    """Read all dates/boards before ranking; never read legacy customer bodies."""
    entries = []
    for plan in plans:
        entries.append({**plan, '_grams': grams(problem_text(plan))})
    for article in articles:
        if article['body']:
            entries.append({'topic': article['title'], 'path': article['path'],
                            'status': 'published', '_grams': grams(article['title']+' '+article['body'])})
    return entries


def overlap(tokens, other):
    # Coverage rather than Jaccard: a long article must not dilute a short task.
    return len(tokens & other) / len(tokens) if tokens else 0


def risk(text, index):
    tokens = grams(text)
    return max((overlap(tokens, item['_grams']) for item in index), default=0)


def same_problem(plan, previous):
    """Only exact substantive reuse is removed locally. Meaning is reviewed by AI."""
    title = normalized(plan.get('topic', plan.get('question', '')))
    if title and title == normalized(previous.get('topic', previous.get('question', ''))):
        return True
    result = normalized(plan.get('deliverable', ''))
    if len(result) < 24 or result != normalized(previous.get('deliverable', '')):
        return False
    return any(len(normalized(plan.get(key, ''))) >= 24 and
               normalized(plan[key]) == normalized(previous.get(key, ''))
               for key in ('reader_problem', 'reader_situation'))


def rank_distinct(items, index, limit=4):
    """Prefer uncovered work and different decisions within the same batch."""
    remaining = list(items)
    picked = []
    scores = {id(item): risk(problem_text(item), index) for item in remaining}
    while remaining and len(picked) < limit:
        def score(item):
            tokens = grams(problem_text(item))
            sibling = max((overlap(tokens, grams(problem_text(p))) for p in picked), default=0)
            return scores[id(item)] + sibling * .35
        chosen = min(remaining, key=score)
        picked.append(chosen)
        remaining.remove(chosen)
    return picked


def covered_examples(plans, queries, limit=24):
    """Retrieve relevant old answers as well as the newest cross-board outcomes."""
    tokens = [grams(q) for q in queries]
    ranked = sorted(enumerate(plans), key=lambda pair: max(
        (overlap(t, grams(problem_text(pair[1]))) for t in tokens), default=0), reverse=True)
    chosen = [p for _, p in ranked[:max(0, limit-8)]]
    chosen.extend(plans[-8:])
    result, seen = [], set()
    for plan in chosen:
        key = (plan.get('topic'), plan.get('status'))
        if key in seen:
            continue
        seen.add(key)
        result.append({k: plan[k] for k in ('topic', 'path', 'status', *PROBLEM_FIELDS) if k in plan})
    return result


def direction_options(lanes, board, plans, index, limit=4):
    """Replace calendar rotation with least-covered, cross-board directions."""
    options = [{'id': board+'-'+hashlib.sha256(lane.encode()).hexdigest()[:10],
                'question': lane} for lane in lanes]
    # Recently attempted directions yield to other ideas, without banning a broad
    # subject forever. Distinct decisions in the same subject still get reviewed.
    recent_ids = {p.get('direction_id') for p in plans[-32:]}
    available = [o for o in options if o['id'] not in recent_ids] or options
    return [{'id': o['id'], 'brief': o['question']} for o in rank_distinct(available, index, limit)]


def supply_diagnostics(tasks, anchors, plans, index, dropped, directions):
    return {'version': 2, 'remainingAssignments': len(tasks),
            'selectedAssignments': [t['id'] for t in anchors],
            'coverageRecords': len(plans), 'coverageArticles': len({p['path'] for p in index if p.get('path')}),
            'stalePendingRemoved': dropped, 'directionIds': [d['id'] for d in directions]}
