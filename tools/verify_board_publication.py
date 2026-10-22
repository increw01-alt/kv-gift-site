"""Cloudflare 반영 뒤 게시글 본문과 배너가 실제 공개되는지 확인합니다."""
import hashlib
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from board_drafts import ROOT, DOMAIN
from board_banner import validate_png


def verify(url, banner, attempts=9, interval=20):
    if not url.startswith(DOMAIN+'/board/') or not banner.startswith('board-img/'):
        raise ValueError('게시 확인 주소 오류')
    expected = hashlib.sha256((ROOT/banner).read_bytes()).digest()
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


if __name__ == '__main__':
    verify(os.environ['POST_URL'], os.environ['POST_BANNER'])
    if os.getenv('GITHUB_ACTIONS') == 'true':
        from run_board_publish import run, sync_main, commit_files, write_json
        from board_status import write_status
        run_id = os.environ['GITHUB_RUN_ID']
        sync_main(run, ROOT)
        ledgers = list((ROOT/'data/editorial_runs').glob(f'*/{run_id}.json'))
        if len(ledgers) != 1:
            raise ValueError('공개 확인을 기록할 실행이 유일하지 않습니다.')
        ledger = ledgers[0]
        record = json.loads(ledger.read_text(encoding='utf-8'))
        if record.get('status') != 'published' or record.get('url') != os.environ['POST_URL']:
            raise ValueError('공개 확인 주소와 게시 기록이 다릅니다.')
        record['public_verified_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        record['publication'] = '공개 게시글과 원본 PNG 확인 완료'
        record['banner_sha256'] = hashlib.sha256((ROOT/os.environ['POST_BANNER']).read_bytes()).hexdigest()
        write_json(ledger, record)
        status_file = write_status(ROOT, dt.date.fromisoformat(record['date_kst']))
        commit_files(run, [ledger.relative_to(ROOT).as_posix(), status_file, 'data/editorial_archive.json'], '[공개 게시 확인] '+run_id)
