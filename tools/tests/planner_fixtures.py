"""Complete planning responses for tests focused on unrelated planner behavior."""
import copy
import json
from unittest.mock import Mock


def writing_brief(paths=()):
    return {'compared_paths': list(paths)[:1],
            'gap': '기존 안내로 결정할 수 없는 참여자의 의견 차이를 조율합니다.',
            'example': '공동 선물을 원하는 사람과 개별 선물을 원하는 사람이 함께 준비하는 경우를 비교해요.',
            'section_actions': ['서로의 참여 목적을 묻고 공동으로 정할 범위를 구분해요.',
                                '합의한 범위와 각자 고를 부분을 나누어 선택해요.',
                                '합의되지 않은 부분은 개별 준비로 돌려 실행해요.'],
            'result': '합의한 공동 준비 범위와 개별 선택 범위를 완성해요.'}


def complete_report(report, content):
    report = copy.deepcopy(report)
    index = report.get('selected_index', -1)
    comparisons = json.loads(content[0]['text'])['comparisons']
    paths = comparisons[index]['compare_paths'] if 0 <= index < len(comparisons) else []
    report.setdefault('writing_brief', writing_brief(paths) if index >= 0 else None)
    return report


class PlannerMock(Mock):
    def _execute_mock_call(self, *args, **kwargs):
        value = super()._execute_mock_call(*args, **kwargs)
        if len(args) > 3 and args[3] == 'topic_novelty_screen' and isinstance(value, dict):
            return complete_report(value, args[1])
        return value
