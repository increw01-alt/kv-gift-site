"""Cloudflare 반영 뒤 게시글 본문과 배너가 실제 공개되는지 확인합니다."""
import hashlib
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from board_drafts import ROOT, DOMAIN, KST
from board_banner import validate_png


def verify(url, banner, attempts=9, interval=20, root=ROOT):
    if not url.startswith(DOMAIN+'/board/') or not banner.startswith('board-img/'):
        raise ValueError('게시 확인 주소 오류')
    expected = hashlib.sha256((root/banner).read_bytes()).digest()
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={'Cache-Control':'no-cache', 'User-Agent':'KV-Publication-Check/1.0'})
            with urllib.request.urlopen(request, timeout=15) as response:
                page = response.read().decode('utf-8')
            if f'href="{url}"' not in page or '/'+banner not in page:
                raise ValueError('이전 페이지 또는 새 배너가 없는 응답')
            image_request = urllib.request.Request(DOMAIN+'/'+banner,
                headers={'Cache-Control':'no-cache', 'User-Agent':'KV-Publication-Check/1.0'})
            with urllib.request.urlopen(image_request, timeout=15) as response:
                raw = response.read()
            validate_png(raw)
            if hashlib.sha256(raw).digest() != expected:
                raise ValueError('배너 파일 불일치')
            message = '공개 게시글과 원본 배너 확인 완료: '+url
            print(message)
            if os.getenv('GITHUB_STEP_SUMMARY'):
                with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as out:
                    out.write('\n\n'+message+'\n')
            return
        except (urllib.error.URLError, ValueError, TimeoutError) as error:
            if attempt+1 == attempts:
                raise RuntimeError('공개 배포 확인 실패: '+str(error)
                                   + '. main 반영과 Cloudflare 상태를 확인하세요.') from None
            time.sleep(interval)


def publication_target(record, root):
    board, day, run_id = record.get('board', ''), record.get('date_kst', ''), str(record.get('run_id', ''))
    if (not re.fullmatch(r'[a-z_]+', board) or not re.fullmatch(r'\d{4}-\d\d-\d\d', day)
            or not run_id.isdigit() or record.get('status') != 'published'):
        raise ValueError('공개 확인 게시 기록 오류')
    url = record.get('url', '')
    if not re.fullmatch(re.escape(DOMAIN+'/board/'+board+'/')+r'\d+', url):
        raise ValueError('공개 확인 주소와 게시 기록이 다릅니다.')
    banner = f'board-img/{board}/guide-{day}-{run_id}.png'
    if not (root/banner).is_file():
        raise ValueError('원본 배너 파일이 없습니다.')
    return url, banner


def verify_record(path, root=ROOT, verifier=None, now=None, attempts=9):
    from run_board_publish import write_json
    record = json.loads(path.read_text(encoding='utf-8'))
    url, banner = publication_target(record, root)
    (verifier or verify)(url, banner, root=root, attempts=attempts)
    # Only after HTML and original-image verification; preserve all usage and publication dates.
    record['public_verified_at'] = (now or dt.datetime.now(dt.timezone.utc)).isoformat()
    record['publication'] = '공개 게시글과 원본 PNG 확인 완료'
    record['banner_sha256'] = hashlib.sha256((root/banner).read_bytes()).hexdigest()
    write_json(path, record)
    return path.relative_to(root).as_posix()


def reconcile_pending(root=ROOT, day=None, verifier=None, now=None):
    """Read existing posts only; no generation, retries of publishing, or new charges."""
    from board_status import write_status
    day = day or dt.datetime.now(KST).date()
    changed = []
    pending = []
    for path in sorted((root/'data/editorial_runs').glob('*/*.json')):
        if not (day-dt.timedelta(days=7)).isoformat() <= path.parent.name <= day.isoformat():
            continue
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('status') == 'published' and not record.get('public_verified_at'):
            pending.append(path)
    for path in pending[:3]:
        try:
            changed.append(verify_record(path, root, verifier, now, attempts=1))
        except (RuntimeError, ValueError, urllib.error.URLError, TimeoutError) as error:
            print('공개 확인 보류 '+path.stem+': '+str(error))
    if changed:
        # Rechecking yesterday must not replace today's dashboard with yesterday's totals.
        changed += [write_status(root, day), 'data/editorial_archive.json']
    return changed


if __name__ == '__main__':
    from run_board_publish import run, sync_main, commit_files
    from board_status import write_status
    if os.getenv('GITHUB_ACTIONS') != 'true':
        raise ValueError('공개 확인 기록 실행은 GitHub Actions에서만 허용됩니다.')
    sync_main(run, ROOT)
    if '--reconcile' in sys.argv:
        files = reconcile_pending()
        if files:
            commit_files(run, files, '[공개 게시 확인] 누락된 확인 기록 보완')
    else:
        run_id = os.environ['GITHUB_RUN_ID']
        ledgers = list((ROOT/'data/editorial_runs').glob(f'*/{run_id}.json'))
        if len(ledgers) != 1:
            raise ValueError('공개 확인을 기록할 실행이 유일하지 않습니다.')
        record = json.loads(ledgers[0].read_text(encoding='utf-8'))
        if publication_target(record, ROOT) != (os.environ['POST_URL'], os.environ['POST_BANNER']):
            raise ValueError('공개 확인 주소와 게시 기록이 다릅니다.')
        ledger = verify_record(ledgers[0])
        status_file = write_status(ROOT, dt.datetime.now(KST).date())
        commit_files(run, [ledger, status_file, 'data/editorial_archive.json'], '[공개 게시 확인] '+run_id)
