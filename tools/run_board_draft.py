"""GitHub Actions 전용. main에는 push하지 않고 검토 PR만 생성합니다."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
from board_drafts import ROOT, KST, pick_topic, generate, render
from board_banner import generate_banner
from board_usage import UsageLog


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
    usage_path = Path(os.getenv('RUNNER_TEMP', tempfile.gettempdir())) / 'board-api-usage.json'
    usage = UsageLog(usage_path)
    status = 'failed'
    try:
        data = generate(topic, os.getenv('OPENAI_MODEL','gpt-4.1-mini'), on_usage=usage.record)
        # 두 API가 모두 성공한 뒤에만 게시판 파일을 변경합니다.
        raw, image_info = generate_banner(topic, data, on_usage=usage.record)
        status = 'completed'
    finally:
        usage.save(status)
        print(usage.markdown())
        if os.getenv('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                f.write(usage.markdown() + '\n\n생성 상태: ' + status + '\n')
    banner = f'board-img/{board}/guide-{day.isoformat()}-{board}.png'
    image_path = ROOT / banner
    if image_path.exists():
        raise ValueError('동일 배너가 이미 있습니다. 덮어쓰지 않습니다.')
    title, review, files = render(board,topic,data,day,banner=banner)
    image_path.parent.mkdir(parents=True,exist_ok=True)
    image_path.write_bytes(raw)
    files.append(banner)
    repo = os.environ['GITHUB_REPOSITORY']
    image_url = f'https://github.com/{repo}/blob/{branch}/{banner}?raw=true'
    review = (usage.markdown() + '\n\n## 배너 미리보기\n\n![글 내용에 맞춘 자동 생성 배너]('+image_url+')\n\n'
              '- [ ] 배너의 한글 오탈자·문구·그림과 본문의 일치 여부 확인\n\n' + review)
    review += ('\n\n<details><summary>이미지 생성 설정과 프롬프트</summary>\n\n'
               f'모델: `{image_info["model"]}` / 품질: `{image_info["quality"]}` / 한 장\n\n'
               '```text\n'+image_info['prompt']+'\n```\n</details>\n')
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
            f.write('배너: '+image_url+'\n\n이미지 API 사용량: '+json.dumps(image_info['usage'])+'\n')


if __name__ == '__main__':
    main()
