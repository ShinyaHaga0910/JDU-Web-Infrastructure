"""Fixed teacher-owned D11 registry. No weights or expected values come from students."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import uuid

REGISTRY_BYTES = globals()['_REGISTRY_BYTES'] if '_REGISTRY_BYTES' in globals() else Path(__file__).with_name('assessment-registry.json').read_bytes()
REGISTRY = json.loads(REGISTRY_BYTES)
CONTRACT_ID = REGISTRY['contract_id']
CONTRACT_SHA256 = hashlib.sha256(REGISTRY_BYTES).hexdigest()
TASKS = {t['id']: t for t in REGISTRY['tasks']}
CHECKS = REGISTRY['check_definitions']
MISSIONS = tuple(t for t in TASKS if TASKS[t]['category'] == 'automated_mission')
MAXIMUM = sum(TASKS[t]['raw_points_max'] for t in MISSIONS)
assert MAXIMUM == 62 and len(MISSIONS) == 6

# The signed D11 wire contract above is immutable. The current curriculum is a
# teacher-owned subset; retired tasks never contribute to current course totals.
COURSE_ID = 'web-2026-11-20-with-connection-checks'
RETIRED_TASKS = frozenset({'P3', 'M3'})
COURSE_TASKS = {tid: task for tid, task in TASKS.items() if tid not in RETIRED_TASKS}
COURSE_MISSIONS = tuple(tid for tid in MISSIONS if tid in COURSE_TASKS)
INTRO_MARKERS = {'P0': ('WEB01_WEB_MARKER', 'web', 'p0-connection.txt'),
                 'M0': ('WEB01_DB_MARKER', 'db', 'm0-connection.txt')}
INTRO_CONTRACT_ID = CONTRACT_ID + '-connection-v1'
INTRO_CONTRACT_SHA256 = hashlib.sha256(json.dumps(
    [CONTRACT_SHA256, INTRO_CONTRACT_ID, INTRO_MARKERS], sort_keys=True).encode()).hexdigest()
COURSE_INTRO_MARKERS = {
    'P0': (INTRO_MARKERS['P0'],),
    'M0': (
        INTRO_MARKERS['M0'],
        ('WEB01_DNS_MARKER', 'dns', 'm0-connection.txt'),
        ('WEB01_REPO_MARKER', 'repo', 'm0-connection.txt'),
        ('WEB01_BASTION_MARKER', 'bastion', 'm0-connection.txt'),
    ),
}
M0_CONTRACT_ID = CONTRACT_ID + '-connection-v2'
M0_CONTRACT_SHA256 = hashlib.sha256(json.dumps(
    [CONTRACT_SHA256, M0_CONTRACT_ID, COURSE_INTRO_MARKERS['M0']], sort_keys=True).encode()).hexdigest()
COURSE_POINTS = {tid: len(markers) for tid, markers in COURSE_INTRO_MARKERS.items()} | {
    tid: TASKS[tid]['raw_points_max'] for tid in COURSE_MISSIONS}
COURSE_GRADED_TASKS = tuple(COURSE_POINTS)
COURSE_MAXIMUM = sum(COURSE_POINTS.values())
STATUSES = {'PASS', 'FAIL', 'UNKNOWN', 'NOT_APPLICABLE'}
HTTP_CONTRACT_ID = CONTRACT_ID + '-custom-roots-v1'
HTTP_CONTRACT_SHA256 = hashlib.sha256(json.dumps([CONTRACT_SHA256, HTTP_CONTRACT_ID,
    {'P1': '/var/www/jdu-practice/practice.txt', 'M1': '/var/www/jdu-mission/mission.txt'},
    'root:www-data', '0640', 'exact-location-root', 'M1-preserves-P1'], sort_keys=True).encode()).hexdigest()


def canonical_checks(task_id, *, intro=False, legacy_intro=False):
    checks = {cid: CHECKS[cid]['role'] for cid in TASKS[task_id]['required_report_checks']}
    if intro:
        markers = (INTRO_MARKERS[task_id],) if legacy_intro else COURSE_INTRO_MARKERS[task_id]
        checks.update((cid, role) for cid, role, _ in markers)
    return checks


def validate_report(report, instances):
    fields = {'schema_version', 'kind', 'lab_id', 'release_id', 'deployment_id', 'request_id',
              'mission_id', 'checks', 'contract_id', 'contract_sha256', 'run_id', 'checked_at', 'mode'}
    if (type(report) is not dict or set(report) != fields or type(report['schema_version']) is not int
            or report['schema_version'] != 2 or report['kind'] != 'assessment'
            or report['mission_id'] not in TASKS or report['mode'] not in ('read_only', 'functional')):
        raise ValueError('Unsupported assessment contract or fields')
    contract = report['contract_id'], report['contract_sha256']
    legacy_intro = (contract == (INTRO_CONTRACT_ID, INTRO_CONTRACT_SHA256)
                    and report['mission_id'] in INTRO_MARKERS)
    intro = legacy_intro or (contract == (M0_CONTRACT_ID, M0_CONTRACT_SHA256) and report['mission_id'] == 'M0')
    http_revision = contract == (HTTP_CONTRACT_ID, HTTP_CONTRACT_SHA256) and report['mission_id'] in ('P1', 'M1')
    if not intro and not http_revision and contract != (CONTRACT_ID, CONTRACT_SHA256):
        raise ValueError('Unsupported assessment contract')
    for name in ('request_id', 'run_id', 'deployment_id'):
        parsed = uuid.UUID(report[name])
        if parsed.version != 4 or str(parsed) != report[name]:
            raise ValueError('Canonical UUID4 required')
    stamp = datetime.fromisoformat(report['checked_at'])
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError('UTC observation time required')
    wanted = canonical_checks(report['mission_id'], intro=intro, legacy_intro=legacy_intro)
    checks = report['checks']
    if type(checks) is not list or not 1 <= len(checks) <= 100 or len(checks) != len(wanted):
        raise ValueError('Complete canonical check set required')
    seen = set()
    for item in checks:
        if type(item) is not dict or set(item) != {'id', 'role', 'instance_id', 'status'}:
            raise ValueError('Only bounded public check results are accepted')
        cid = item['id']
        if (type(cid) is not str or cid not in wanted or cid in seen or item['role'] != wanted[cid]
                or item['instance_id'] != instances[wanted[cid]] or item['status'] not in STATUSES):
            raise ValueError('Check ID, role, instance or status differs')
        seen.add(cid)
    if seen != set(wanted):
        raise ValueError('Missing or extra canonical check')
    functional = {'WEB06_PASSWORD_LOGIN', 'WEB06_CREATE_REFLECT', 'WEB06_EDIT_REFLECT',
                  'WEB06_LOGOUT', 'WEB07_ANONYMOUS_DENIED', 'WEB07_BAD_PASSWORD_DENIED'}
    if report['mode'] == 'read_only' and any(c['id'] in functional and c['status'] != 'UNKNOWN' for c in checks):
        raise ValueError('Read-only mode cannot assert functional observations')
    return TASKS[report['mission_id']]


def score(report):
    """Called only after strict report validation. Readiness never earns points."""
    task = TASKS[report['mission_id']]
    observed = {c['id']: c['status'] for c in report['checks']}
    scored, ready = task['progress_scored_checks'], task['readiness_checks']
    intro = report['contract_sha256'] in (INTRO_CONTRACT_SHA256, M0_CONTRACT_SHA256)
    if report['contract_sha256'] == M0_CONTRACT_SHA256:
        scored = [cid for cid, _, _ in COURSE_INTRO_MARKERS[task['id']]]
    elif intro:
        scored = [INTRO_MARKERS[task['id']][0]]
    unresolved = sum(observed[c] not in ('PASS', 'FAIL') for c in scored)
    ready_ok = all(observed[c] == 'PASS' for c in ready)
    passed = sum(observed[c] == 'PASS' for c in scored)
    return dict(raw_earned=passed, raw_maximum=len(scored), unresolved=unresolved,
                readiness_ok=ready_ok, evaluable=ready_ok and unresolved == 0,
                complete=ready_ok and unresolved == 0 and passed == len(scored),
                counts_toward_assessment=intro or task['category'] == 'automated_mission')


def build_report(task_id, identity, observations, run_id, *, mode='read_only', checked_at, intro=False, http_revision=False):
    report = {k: identity[k] for k in ('lab_id', 'release_id', 'deployment_id')}
    contract_id, contract_hash = CONTRACT_ID, CONTRACT_SHA256
    if http_revision:
        if task_id not in ('P1', 'M1') or intro:
            raise ValueError('Custom roots are only for P1/M1')
        contract_id, contract_hash = HTTP_CONTRACT_ID, HTTP_CONTRACT_SHA256
    if intro:
        contract_id, contract_hash = ((M0_CONTRACT_ID, M0_CONTRACT_SHA256) if task_id == 'M0'
                                     else (INTRO_CONTRACT_ID, INTRO_CONTRACT_SHA256))
    report.update(schema_version=2, kind='assessment', mission_id=task_id,
                  contract_id=contract_id, contract_sha256=contract_hash,
                  request_id=str(uuid.uuid4()), run_id=run_id, checked_at=checked_at, mode=mode)
    report['checks'] = []
    for cid, role in canonical_checks(task_id, intro=intro).items():
        value = observations.get(cid)
        if value is not None and type(value) is not bool:
            raise ValueError('Observer results must be boolean or unknown')
        report['checks'].append(dict(id=cid, role=role, instance_id=identity['instances'][role],
                                    status='UNKNOWN' if value is None else 'PASS' if value else 'FAIL'))
    validate_report(report, identity['instances'])
    return report
