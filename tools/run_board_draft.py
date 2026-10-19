"""GitHub Actions 전용. main에는 push하지 않고 검토 PR만 생성합니다."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
from board_drafts import ROOT, KST, pick_topic, generate, render


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf-8').strip()


def main():
    board = os.getenv('REQUESTED_BOARD') or ('sale' if os.getenv('EVENT_SCHEDULE') == '0 1 * * 5' else 'purchase')
    if board not in ('purchase','sale'):
        raise ValueError('게시판 선택 오류')
    prs = json.loads(run('gh','pr','list','--state','open','--limit','100','--json','headRefName,url'))
    pending = [p for p in prs if p['headRefName'].startswith('auto/board-')]
    if pending:
        print('검토 대기 글이 있어 추가 생성을 건너뜁니다: '+pending[0]['url'])
        return
    day = dt.datetime.now(KST).date()
    branch = f'auto/board-{day.isoformat()}-{board}'
    if run('git','ls-remote','--heads','origin',branch):
        print('오늘 생성한 브랜치가 이미 있습니다. 재생성과 중복 과금을 방지합니다: '+branch)
        return
    topic = pick_topic(board)
    data = generate(topic, os.getenv('OPENAI_MODEL','gpt-4.1-mini'))
    title, review, files = render(board,topic,data,day)
    run('git','diff','--check')
    run('git','switch','-c',branch)
    run('git','config','user.name','github-actions[bot]')
    run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    run('git','add','--',*files)
    run('git','commit','-m',title)
    run('git','push','origin','HEAD:refs/heads/'+branch)
    with tempfile.TemporaryDirectory() as temp:
        body = Path(temp)/'review.md'
        body.write_text(review,encoding='utf-8')
        url = run('gh','pr','create','--base','main','--head',branch,'--title','[게시 전 검토] '+title,'--body-file',str(body))
    print(url)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write('검토할 글: '+url+'\n\nmain에 병합하기 전에는 운영 사이트에 게시되지 않습니다.\n')


if __name__ == '__main__':
    main()
