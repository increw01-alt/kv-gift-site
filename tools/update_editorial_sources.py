"""Import safe source signals; never accept raw conversations, URLs or arbitrary questions."""
import json
import os
from board_sources import validate_source
from run_board_publish import ROOT, run, sync_main, write_json, commit_files


def apply_update(root, value):
    validate_source(value, root)
    path = root/'data/editorial_sources.json'
    if path.exists():
        current = json.loads(path.read_text(encoding='utf-8'))
        if current['checked_at'] >= value['checked_at']:
            return False
    write_json(path, value)
    return True


def main():
    if os.getenv('GITHUB_ACTIONS') != 'true' or os.getenv('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('자료 갱신은 main Actions에서만 가능합니다.')
    raw = os.getenv('SOURCE_SIGNALS_JSON', '')
    if len(raw.encode()) > 12000:
        raise ValueError('자료 집계 요청 크기 초과')
    value = json.loads(raw)
    validate_source(value)
    sync_main(run, ROOT)
    if apply_update(ROOT, value):
        commit_files(run, ['data/editorial_sources.json'], '[작성 참고 자료] 비식별 관심 주제 갱신')
    print('관심 주제 집계 반영 완료. 원문 저장 및 유료 생성 없음.')


if __name__ == '__main__':
    main()
