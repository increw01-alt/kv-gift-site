"""Apply one serialized dashboard settings request without generating content."""
import datetime as dt
import json
import os
import re
from editorial_settings import DEFAULT, FIELDS, KST, load_settings, validate
from run_board_publish import ROOT, run, sync_main, write_json, commit_files
from board_status import write_status


def apply_update(root, payload, now=None):
    if not isinstance(payload, dict) or set(payload) != {*FIELDS, 'requestId', 'expectedRevision'}:
        raise ValueError('허용되지 않은 설정 항목입니다.')
    if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', str(payload['requestId'])):
        raise ValueError('저장 요청 번호가 올바르지 않습니다.')
    values = validate(payload)
    current = load_settings(root, required=True)
    if current['revision'] == payload['requestId']:
        if any(current[key] != values[key] for key in FIELDS):
            raise ValueError('동일 요청 번호의 내용이 다릅니다.')
        return False
    if current['revision'] != payload['expectedRevision']:
        raise ValueError('다른 설정이 먼저 저장됐습니다. 새로고침 후 다시 저장하세요.')
    instant = now or dt.datetime.now(dt.timezone.utc)
    value = {**DEFAULT, **values, 'revision': payload['requestId'], 'updatedAt': instant.isoformat()}
    write_json(root/'data/editorial_settings.json', value)
    write_status(root, instant.astimezone(KST).date())
    return True


def main():
    if os.getenv('GITHUB_ACTIONS') != 'true' or os.getenv('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('설정 저장은 main의 GitHub Actions에서만 실행합니다.')
    raw = os.environ.get('SETTINGS_JSON', '')
    if len(raw.encode()) > 2048:
        raise ValueError('설정 요청이 너무 큽니다.')
    sync_main(run, ROOT)
    changed = apply_update(ROOT, json.loads(raw))
    if changed:
        commit_files(run, ['data/editorial_settings.json', 'data/editorial_status.json'], '[자동 게시 설정] 대시보드 변경 적용')
    print('설정 반영 완료. 글이나 이미지를 생성하지 않았습니다.')


if __name__ == '__main__':
    main()
