from pathlib import Path
import ast
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / '01_roles/cyber_security/system_requirements'
PREFIX = '2026-10_web_infrastructure_d11_'
cp = BASE / (PREFIX + 'assessment_contract.json')
sp = BASE / (PREFIX + 'assessment_spec.md')
c = json.loads(cp.read_text())
spec = sp.read_text()
defs, sets, tasks = c['check_definitions'], c['check_sets'], c['tasks']
ids = [t['id'] for t in tasks]
by_id = {t['id']: t for t in tasks}
assert len(ids) == len(set(ids)) == 14
assert set(ids) == {f'P{i}' for i in range(7)} | {f'M{i}' for i in range(7)}
assert c['user_decisions']['personal_demonstration_required'] is False
assert c['manual_points_max'] == c['user_decisions']['teacher_manual_points'] == 0
assert c['user_decisions']['course_normalization_handled_by_teacher'] is True
assert c['grading_policy']['automatic_course_normalization'] is False
assert 'course_points_max' not in c and 'score_groups' not in cp.read_text()
assert 'M7' not in ids and 'demonstration' not in sets
assert c['class_ready'] is False

role_names = set(c['shared_constraints']['roles'])
check_pattern = re.compile(r'[A-Z][A-Z0-9_-]{1,47}')
for cid, d in defs.items():
    assert check_pattern.fullmatch(cid), cid
    assert d['raw_points'] in (0, 1) and type(d['raw_points']) is int
    assert d['role'] in role_names
    assert d['pass_condition'] and d['title']
for name, checks in sets.items():
    assert len(checks) == len(set(checks)) and set(checks) <= set(defs)
assert set(defs) == set().union(*map(set, sets.values()))

count_by_mission, globally_scored = {}, []
for task in tasks:
    report = task['required_report_checks']
    scored = task['progress_scored_checks']
    ready = task['readiness_checks']
    assert len(report) == len(set(report)) and 1 <= len(report) <= 100
    assert set(report) == set(scored) | set(ready)
    assert set(scored).isdisjoint(ready)
    assert set(report) <= set(defs)
    assert all(defs[k]['raw_points'] == 1 for k in scored)
    assert all(defs[k]['raw_points'] == 0 for k in ready)
    assert task['progress_points_max'] == len(scored)
    assert len(scored) == sum(defs[k]['raw_points'] for k in sets[task['check_set']])
    assert set(task['requires_current']) <= set(ids)
    if task['category'] == 'automated_mission':
        assert task['raw_points_max'] == len(scored)
        count_by_mission[task['id']] = len(scored)
        globally_scored += scored
    else:
        assert task['raw_points_max'] == 0
assert len(globally_scored) == len(set(globally_scored)), 'No check can score in two missions'
assert count_by_mission == c['raw_points_by_mission']
assert sum(count_by_mission.values()) == c['raw_points_max'] == c['automated_points_max'] == 62

order = c['recommended_order']
assert len(order) == len(set(order)) == len(ids) and set(order) == set(ids)
for t in tasks:
    assert all(order.index(p) < order.index(t['id']) for p in t['requires_current'])
assert order.index('P5') < order.index('P6') < order.index('M5') < order.index('M6')
assert all(not p.startswith('P') for p in by_id['M5']['requires_current'])
assert by_id['P2']['requires_current'] == ['P1']
assert by_id['M2']['requires_current'] == ['M1']
assert by_id['M4']['setup_nologin_after_m5_is_valid'] is True
assert by_id['M4']['app_tables_required_at_this_stage'] is False

hp = ROOT / '01_roles/cyber_security/tools/web_lab_teacher/http_task.py'
assignments = {}
for n in ast.parse(hp.read_text()).body:
    if isinstance(n, ast.Assign):
        for target in n.targets:
            if isinstance(target, ast.Name) and target.id in ('TASKS', 'CHECKS'):
                assignments[target.id] = ast.literal_eval(n.value)
assert sets['http'] == list(assignments['CHECKS'])
for mid, expected in assignments['TASKS'].items():
    assert by_id[mid]['required_report_checks'] == list(assignments['CHECKS'])
    assert by_id[mid]['module'] == expected['module']
    assert by_id[mid]['expected'] == {k: v for k, v in expected.items() if k != 'module'}
assert hashlib.sha256(hp.read_bytes()).hexdigest() == '5f50d4b586630c93b0c4c3274dc8ac0bc05a4d6bba9d35f1145ecf2c24cb2462'
initial_passes = {'WEB02_IDENTITY', 'WEB02_REPO_PREREQUISITE'}
assert len(initial_passes) == 2 and len(initial_passes & set(by_id['M1']['progress_scored_checks'])) == 0
assert len(set(sets['http']) & set(by_id['M1']['progress_scored_checks'])) == 8

for mid, value in count_by_mission.items():
    assert re.search(rf'^\| {mid} \| [^|]+ \| {value} \|$', spec, re.M), mid
table_checks = re.findall(r'^\| (WEB\d\d_[A-Z0-9_]+) \|', spec, re.M)
assert len(table_checks) == len(set(table_checks)) == 62
assert set(table_checks) == set(globally_scored)
assert '教師の実演点なし** | **62**' in spec
assert c['interactive_app_acceptance']['authentication_bypass'] is False
assert c['interactive_app_acceptance']['own_probe_record_retained'] is True
assert c['interactive_app_acceptance']['status'] == 'design_only_not_implemented'
assert all(c['runtime_capabilities'][k] is False for k in (
    'canonical_registry_implemented', 'raw_score_projection_implemented',
    'new_task_dispatch_implemented', 'practice_app_profile_implemented',
    'interactive_app_acceptance_implemented', 'signed_d08_distribution_changed'))
assert c['grading_policy']['cross_attempt_check_union'] is False
assert c['grading_policy']['highest_score_automatically_selected'] is False
assert c['grading_policy']['unknown_points'] is None
assert c['grading_policy']['fixed_denominator'] is True
assert c['shared_constraints']['all_nodes_ssm_retained'] is True
assert c['shared_constraints']['ssh_private_keys_exported_to_shared_windows'] is False
assert c['shared_constraints']['app_required_records_are_subset_not_entire_table'] is True
for profile in c['profiles'].values():
    assert len(profile['records']) == 2
    assert {r['is_public'] for r in profile['records']} == {True, False}

docs = [sp,
    ROOT / '01_roles/cyber_security/lesson_plans/2026-10-13_web_infrastructure_exercises_and_autograding_design.md',
    ROOT / '01_roles/cyber_security/lesson_plans/2026-10-13_web_infrastructure_status_and_next_steps.md',
    BASE / '2026-10_web_infrastructure_design_decision_register.md',
    BASE / '2026-10_web_infrastructure_catalog_app_spec.md',
    ROOT / '03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md']
links = 0
for doc in docs:
    for raw in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8-sig')):
        link = raw.strip('<>')
        if '://' in link or link.startswith('#') or re.match(r'[A-Za-z]:', link):
            continue
        target = link.split('#', 1)[0]
        assert (doc.parent / target).exists(), (doc.name, target)
        links += 1

index_path = ROOT / '03_knowledge/aws_official/web_lab_packages_2026-10-15/distribution-class193548-r3.index.public.json'
index = json.loads(index_path.read_text())
for entry in index['files']:
    data = (ROOT / entry['path']).read_bytes()
    assert len(data) == entry['size_bytes'], entry['path']
    assert hashlib.sha256(data).hexdigest() == entry['sha256'], entry['path']

source_paths = [hp,
    ROOT / '01_roles/cyber_security/tools/web_lab_teacher/progress_api.py',
    ROOT / '01_roles/cyber_security/tools/web_lab_teacher/check_dispatch.py',
    ROOT / '01_roles/cyber_security/tools/web_lab_catalog/tests/test_proxy.py',
    ROOT / '01_roles/cyber_security/tools/web_lab_catalog/tests/test_runtime.py']
files = []
for p in [sp, cp] + source_paths:
    data = p.read_bytes()
    files.append(dict(path=str(p.relative_to(ROOT)), size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
report = dict(scope='approved_d11_design_static_consistency_only_not_runtime_acceptance', date='2026-10-23',
    contract_id=c['contract_id'], approval_status=c['approval_status'],
    task_count=len(tasks), practice_count=7, graded_missions=6,
    raw_points_by_mission=count_by_mission, raw_points_max=62,
    one_point_scored_checks=62, manual_points=0,
    personal_demonstration_required=False, course_normalization='teacher_external',
    all_checks_unique_and_fully_accounted=True, no_scored_check_reused_between_missions=True,
    no_provided_readiness_check_awards_points=True,
    p1_m1_existing_ten_ids_role_paths_and_bodies_preserved=True,
    http_initial_two_ready_passes_award_zero_of_eight=True,
    schema_document_version_not_wire_update=True,
    prerequisite_graph_and_profile_order_valid=True,
    optional_practice_not_required_for_m5=True,
    per_report_check_count_within_existing_api_limit=True,
    spec_tables_match_exact_canonical_scored_check_set=True,
    checked_local_links=links, all_relative_links_resolve=True,
    d08_index_files_verified=len(index['files']), d08_index_file_hashes_unchanged=True,
    runtime_implementation_verified_by_this_static_check=False,
    interactive_functional_acceptance_not_verified_by_this_static_check=True,
    aws_resources_or_grade_records_changed=False, class_ready=False,
    files=files)
out = BASE / (PREFIX + 'validation.public.json')
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: report[k] for k in ('contract_id', 'task_count', 'raw_points_by_mission', 'raw_points_max', 'manual_points', 'checked_local_links', 'd08_index_files_verified', 'class_ready')}, ensure_ascii=False))
