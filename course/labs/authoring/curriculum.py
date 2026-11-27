"""Active teaching subset of the immutable signed D11 assessment baseline."""
import copy
import json
import re
from pathlib import Path

POLICY = json.loads((Path(__file__).resolve().parents[2] / 'curriculum.json').read_text(encoding='utf-8'))
ACTIVE_NUMBERS = tuple(int(t[1:]) for t in POLICY['active_order'] if t.startswith('P'))
ACTIVE_ORDER = tuple(POLICY['active_order'])
RAW_MAXIMUM = POLICY['raw_maximum']
DISPLAY_IDS = POLICY['practice_display_ids'] | POLICY['mission_display_ids']


def display_task(task):
    return DISPLAY_IDS.get(task, task)


def display_task_references(text):
    # Preserve application record codes such as P5-PUBLIC-001 and M5-PUBLIC-001.
    return re.sub(r'(?<![A-Za-z0-9_-])[PM][456](?![A-Za-z0-9_-])', lambda match: display_task(match[0]), text)


def task_page(task):
    return display_task(task).lower() + '.md'

def active_registry(baseline):
    value = copy.deepcopy(baseline)
    value['tasks'] = [t for t in value['tasks'] if t['id'] in ACTIVE_ORDER]
    value['recommended_order'] = list(ACTIVE_ORDER)
    value['raw_points_by_mission'] = POLICY['mission_points']
    points = POLICY['intro_points'] | POLICY['practice_points'] | POLICY['mission_points']
    assert set(points) == set(ACTIVE_ORDER) and sum(points.values()) == RAW_MAXIMUM
    value['raw_points_by_task'] = points
    for task in value['tasks']:
        if task['id'] in ('P1', 'M1'):
            folder = 'jdu-practice' if task['id'] == 'P1' else 'jdu-mission'
            task['expected']['file'] = '/var/www/' + folder + task['expected']['path']
        task['raw_points_max'] = points[task['id']]
    value['raw_points_max'] = RAW_MAXIMUM
    return value
