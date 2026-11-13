"""Active teaching subset of the immutable signed D11 assessment baseline."""
import copy
import json
from pathlib import Path

POLICY = json.loads((Path(__file__).resolve().parents[2] / 'curriculum.json').read_text(encoding='utf-8'))
ACTIVE_NUMBERS = tuple(int(t[1:]) for t in POLICY['active_order'] if t.startswith('P'))
ACTIVE_ORDER = tuple(POLICY['active_order'])
RAW_MAXIMUM = POLICY['raw_maximum']

def active_registry(baseline):
    value = copy.deepcopy(baseline)
    value['tasks'] = [t for t in value['tasks'] if t['id'] in ACTIVE_ORDER]
    value['recommended_order'] = list(ACTIVE_ORDER)
    value['raw_points_by_mission'] = POLICY['mission_points']
    value['raw_points_max'] = RAW_MAXIMUM
    return value
