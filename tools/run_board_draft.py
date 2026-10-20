"""GitHub Actions 전용. main에는 push하지 않고 검토 PR만 생성합니다."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
import shutil
from board_drafts import ROOT, KST, BOARDS, NoTopic, select_board, news_brief, generate, render
from board_profiles import PROFILES
from board_render import save_preview
from board_banner import generate_banner
from board_usage import UsageLog


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf-8').strip()


def report_skip(message):
    print(message)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write('## 이번 실행은 생성하지 않았습니다\n\n' + message
                    + '\n\n글·이미지 API를 호출하지 않았습니다. 새 API 비용은 발생하지 않습니다.\n')


def main():
    requested = os.getenv('REQUESTED_BOARD') or 'auto'
    preview_only = os.getenv('PREVIEW_ONLY', 'false').lower() == 'true'
    if requested != 'auto' and requested not in BOARDS:
        raise ValueError('게시판 선택 오류')
    if preview_only and os.getenv('GITHUB_EVENT_NAME') != 'workflow_dispatch':
        raise ValueError('검토 전용 생성은 수동 실행에서만 사용할 수 있습니다.')
    if not preview_only:
        prs = json.loads(run('gh','pr','list','--state','open','--limit','100','--json','headRefName,url'))
        pending = [p for p in prs if p['headRefName'].startswith('auto/board-')]
        if pending:
            report_skip('검토 대기 글이 있어 추가 생성을 건너뜁니다: '+pending[0]['url'])
            return
    day = dt.datetime.now(KST).date()
    try:
        board, topic = select_board(requested, day=day)
    except NoTopic as error:
        report_skip(str(error))
        return
    branch = f'auto/board-{day.isoformat()}-{board}'
    if not preview_only and run('git','ls-remote','--heads','origin',branch):
        report_skip('오늘 생성한 브랜치가 이미 있습니다. 재생성과 중복 과금을 방지합니다: '+branch)
        return
    brief = news_brief(topic, day=day) if PROFILES[board].get('requires_brief') else None
    output_dir = Path(os.getenv('RUNNER_TEMP', tempfile.gettempdir()))
    usage_path = output_dir / 'board-api-usage.json'
    usage = UsageLog(usage_path, {'board': board, 'board_name': BOARDS[board], 'topic': topic,
                                 'mode': 'preview_only' if preview_only else 'review_pr'})
    status = 'failed'
    try:
        data = generate(topic, os.getenv('OPENAI_MODEL','gpt-4.1-mini'), on_usage=usage.record, board=board, day=day)
        # 두 API가 모두 성공한 뒤에만 게시판 파일을 변경합니다.
        raw, image_info = generate_banner(topic, data, on_usage=usage.record, board=board)
        status = 'completed'
    finally:
        usage.save(status)
        print(usage.markdown())
        if os.getenv('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                f.write(usage.markdown() + '\n\n생성 상태: ' + status + '\n')
    preview_dir = output_dir / 'board-review'
    save_preview(preview_dir, board, topic, data, day, raw, ROOT, brief)
    shutil.copyfile(usage_path, preview_dir / 'board-api-usage.json')
    if preview_only:
        print('검토 전용 글·이미지를 생성했습니다. Artifact: board-review. PR과 운영 사이트는 변경하지 않았습니다.')
        if os.getenv('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                f.write(f'\n## 검토 전용 미리보기\n\n게시판: {BOARDS[board]}\n\n주제: {topic}\n\n'
                        'Artifacts의 board-review 파일에서 글·배너·비용을 확인하세요. '
                        'PR을 만들거나 운영 사이트에 게시하지 않았습니다.\n')
        return
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
              '- [ ] 네이비·골드·아이보리 일러스트가 글 내용과 어울리는지 확인\n'
              '- [ ] 짧은 한글 제목의 오탈자와 모바일 가독성 확인\n'
              '- [ ] 하단 KV 로고가 원본과 같고 상품권 발행사 표시처럼 보이지 않는지 확인\n\n' + review)
    review += ('\n\n<details><summary>이미지 생성 설정과 프롬프트</summary>\n\n'
               f'모델: `{image_info["model"]}` / 품질: `{image_info["quality"]}` / 한 장\n\n'
               '참고 이미지: 승인된 일러스트 + 드라이브 KV 로고 원본 (`tools/assets/board-banner/`)\n\n'
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
