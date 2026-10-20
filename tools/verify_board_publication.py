"""Cloudflare 반영 뒤 게시글 본문과 배너가 실제 공개되는지 확인합니다."""
import hashlib
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
            with urllib.request.urlopen(DOMAIN+'/'+banner, timeout=15) as response:
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
        except (urllib.error.URLError, ValueError, TimeoutError):
            if attempt+1 == attempts:
                raise RuntimeError('제한 시간 안에 공개 배포를 확인하지 못했습니다. main 반영과 Cloudflare 상태를 확인하세요.') from None
            time.sleep(interval)


if __name__ == '__main__':
    verify(os.environ['POST_URL'], os.environ['POST_BANNER'])
