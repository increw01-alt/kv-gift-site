"""사용자 승인(2026-10-20)에 따른 하루 최대 10편 자동 게시."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from board_drafts import ROOT, KST, NoTopic, generate, read_json, render
from board_editor import select_topic, edit_article, review_article, fresh_topic, prior_titles
from board_banner import generate_banner
from board_render import save_preview
from board_usage import UsageLog

DAILY_LIMIT = 10


def run(*args, root=ROOT):
    return subprocess.check_output(args, cwd=root, text=True, encoding='utf-8').strip()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def summary(text):
    print(text)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as output:
            output.write(text+'\n\n')


def emit_publication(url, banner):
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
            out.write(f'post_url={url}\nbanner={banner}\n')


def recover_publication(root, run_id):
    """실패 단계 재실행은 기존 게시글만 확인합니다. 날짜가 바뀌어도 재생성하지 않습니다."""
    matches = list((root/'data/editorial_runs').glob(f'*/{run_id}.json'))
    if not matches:
        return False
    if len(matches) != 1:
        raise ValueError('동일 실행의 게시 기록이 여러 개입니다.')
    record = read_json(matches[0])
    if record.get('status') != 'published' or not record.get('url'):
        return False
    banner = f'board-img/{record["board"]}/guide-{record["date_kst"]}-{run_id}.png'
    if not (root/banner).is_file():
        raise ValueError('기존 게시 배너 파일을 찾을 수 없습니다.')
    emit_publication(record['url'], banner)
    summary('기존 게시글을 재생성하지 않고 공개 상태만 확인합니다: '+record['url'])
    return True


def guard(root, day, run_id, attempt):
    if attempt != '1':
        return '재실행은 중복 과금을 막기 위해 생성하지 않습니다. 이전 실행 기록을 확인하세요.'
    records = root/'data/editorial_runs'/day.isoformat()
    if (records/f'{run_id}.json').exists():
        return '이미 처리한 실행입니다. 중복 게시하지 않습니다.'
    runs = list(records.glob('*.json')) if records.exists() else []
    history = read_json(root/'data/editorial_history.json')
    published = [x for x in history if x.get('publication_mode') == 'automatic'
                 and x.get('drafted_at') == day.isoformat()]
    if len(runs) >= DAILY_LIMIT or len(published) >= DAILY_LIMIT:
        return '오늘 자동 작성 한도 10회에 도달했습니다. 추가 생성·게시하지 않습니다.'
    return None


def sync_main(command, root):
    if command('git', 'branch', '--show-current') != 'main':
        raise ValueError('자동 게시 작업은 main 체크아웃에서만 실행합니다.')
    if command('git', 'status', '--porcelain'):
        raise ValueError('작업 폴더가 깨끗하지 않아 자동 게시를 중단합니다.')
    command('git', 'fetch', 'origin', 'main')
    command('git', 'merge', '--ff-only', 'origin/main')


def record_outcome(root, day, run_id, board, topic, status, review, usage, url=None):
    ledger = root/'data/editorial_runs'/day.isoformat()/f'{run_id}.json'
    outcome = {
        'run_id': run_id, 'date_kst': day.isoformat(), 'board': board, 'topic': topic,
        'status': status, 'url': url,
        'publication': 'main 반영 후 Cloudflare 배포 확인 필요' if url else '게시하지 않음',
        'review': review, 'api_usage': read_json(usage.path),
    }
    write_json(ledger, outcome)
    files = [ledger.relative_to(root).as_posix()]
    if board:
        path = root/'data/editorial_state.json'
        state = read_json(path) if path.exists() else {'held_topics': []}
        state['last_board'] = board
        state['last_run_id'] = run_id
        if status != 'published' and topic:
            state.setdefault('held_topics', []).append({'board': board, 'topic': topic, 'run_id': run_id})
        write_json(path, state)
        files.append(path.relative_to(root).as_posix())
    return files, outcome


def main(root=ROOT, command=None, now=None):
    command = command or (lambda *args: run(*args, root=root))
    if os.getenv('GITHUB_ACTIONS') != 'true' or os.getenv('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('자동 게시 실행은 GitHub Actions의 main에서만 허용됩니다.')
    preview = os.getenv('PREVIEW_ONLY', 'false').lower() == 'true'
    if preview and os.getenv('GITHUB_EVENT_NAME') != 'workflow_dispatch':
        raise ValueError('검토 전용 생성은 수동 실행에서만 가능합니다.')
    run_id = os.getenv('GITHUB_RUN_ID', '')
    if not re.fullmatch(r'\d+', run_id):
        raise ValueError('GitHub 실행 번호가 없습니다.')
    day = (now or dt.datetime.now(KST)).astimezone(KST).date()
    if not preview:
        sync_main(command, root)
    attempt = os.getenv('GITHUB_RUN_ATTEMPT', '1')
    reason = guard(root, day, run_id, attempt) if not preview else (
        '검토 전용 재실행도 중복 과금을 막기 위해 생성하지 않습니다.' if attempt != '1' else None)
    if reason:
        summary(reason+'\n\nAPI를 호출하지 않았습니다.')
        if not preview:
            recover_publication(root, run_id)
        return 0
    output = Path(os.getenv('RUNNER_TEMP', tempfile.gettempdir()))
    preview_dir = output/'board-review'
    preview_dir.mkdir(parents=True, exist_ok=True)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    usage = UsageLog(output/'board-api-usage.json',
                     {'mode': 'preview_only' if preview else 'automatic_publish', 'daily_limit': DAILY_LIMIT})
    board = topic = brief = data = raw = None
    report = {'approved': False, 'issues': []}
    status, api_status, error = 'held', 'failed', None
    try:
        board, topic, brief = select_topic(os.getenv('REQUESTED_BOARD') or 'auto', day, model, usage.record, root)
        usage.context.update({'board': board, 'topic': topic})
        data = generate(topic, model, usage.record, board=board, root=root, day=day)
        write_json(preview_dir/'draft.api-original.json', data)
        data = edit_article(board, topic, data, brief, model, usage.record, root)
        write_json(preview_dir/'edited-text.json', data)
        raw, image_info = generate_banner(topic, data, usage.record, board=board)
        save_preview(preview_dir, board, topic, data, day, raw, root, brief, approval_required=preview)
        write_json(preview_dir/'image-generation.json', image_info)
        report = review_article(board, topic, data, raw, brief, model, usage.record, root)
        api_status = 'completed'
        if report['approved']:
            status = 'ready'
    except NoTopic as exc:
        report = {'approved': False, 'issues': [str(exc)]}
        api_status = 'completed'
    except Exception as exc:
        status, error = 'error', f'{type(exc).__name__}: {exc}'
        report = {'approved': False, 'issues': [error]}
    finally:
        usage.save(api_status)
        shutil.copyfile(usage.path, preview_dir/'board-api-usage.json')
        write_json(preview_dir/'review.json', report)
        summary(usage.markdown())
    if preview:
        write_json(preview_dir/'result.json', {'status': status, 'published': False, 'review': report})
        summary(f'검토 전용 생성: {status}. 운영 사이트와 게시 이력은 변경하지 않았습니다.')
        return 1 if error else 0

    # 생성 도중 사람이 올린 변경을 먼저 반영하고 최신 목록에서 번호와 중복을 다시 확인합니다.
    sync_main(command, root)
    reason = guard(root, day, run_id, '1')
    if reason:
        summary(reason+' 생성 결과는 검토 Artifact에 보관했습니다.')
        return 0
    files, url = [], None
    if status == 'ready' and not fresh_topic(topic, prior_titles(root)):
        status = 'held'
        report = {'approved': False, 'issues': ['생성 중 같은 주제가 게시되어 중복 게시를 보류합니다.']}
    if status == 'ready':
        banner = f'board-img/{board}/guide-{day.isoformat()}-{run_id}.png'
        if (root/banner).exists():
            raise ValueError('배너 파일이 이미 있습니다. 덮어쓰지 않습니다.')
        title, _, files = render(board, topic, data, day, root, banner)
        (root/banner).parent.mkdir(parents=True, exist_ok=True)
        (root/banner).write_bytes(raw)
        files.append(banner)
        history_path = root/'data/editorial_history.json'
        history = read_json(history_path)
        history[-1].update({'publication_mode': 'automatic', 'run_id': run_id,
                           'usage_file': f'data/editorial_runs/{day.isoformat()}/{run_id}.json'})
        write_json(history_path, history)
        url = f'https://kv-gift.co.kr/board/{board}/{history[-1]["id"]}'
        status = 'published'
    audit_files, outcome = record_outcome(root, day, run_id, board, topic, status, report, usage, url)
    files.extend(audit_files)
    write_json(preview_dir/'result.json', outcome)
    command('git', 'diff', '--check')
    command('git', 'config', 'user.name', 'github-actions[bot]')
    command('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    command('git', 'add', '--', *files)
    command('git', 'commit', '-m', ('[자동 게시] '+topic) if url else '[자동 작성 기록] '+run_id+' '+status)
    # main 이동 시 일반 push가 거절됩니다. 강제 push나 임의 덮어쓰기는 하지 않습니다.
    try:
        command('git', 'push', 'origin', 'HEAD:refs/heads/main')
    except Exception:
        outcome.update({'status': 'push_failed', 'publication': 'main 반영 실패, 운영 게시 미확인'})
        write_json(preview_dir/'result.json', outcome)
        raise
    if url:
        draft_path = preview_dir/'draft.json'
        draft_record = read_json(draft_path)
        draft_record.update({'published': True, 'published_url': url,
                             'publication': 'main 반영 완료, 공개 배포는 다음 단계에서 확인'})
        write_json(draft_path, draft_record)
        summary('자동 검수를 통과하여 main에 반영했습니다: '+url+'\n\n다음 단계에서 공개 배포를 확인합니다.')
        emit_publication(url, banner)
    else:
        summary('이번 글은 게시하지 않았습니다. 사유: '+' / '.join(report.get('issues', [])))
    return 1 if error else 0


if __name__ == '__main__':
    raise SystemExit(main())
