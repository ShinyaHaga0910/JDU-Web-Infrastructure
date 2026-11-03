"""Fixed-denominator views; latest evaluable attempt is separate from current health."""
from registry import CONTRACT_ID, CONTRACT_SHA256, MAXIMUM, MISSIONS, TASKS


def grade_key(mission_id):
    return 'GRADE#' + CONTRACT_SHA256 + '#' + mission_id


def current_key(task_id):
    return 'LATEST#D11#' + CONTRACT_SHA256 + '#' + task_id


def project_lab(lab):
    rows = {r['sk']: r for r in lab.get('results', [])}
    current, selected = {}, {}
    for mid in TASKS:
        latest = rows.get(current_key(mid))
        if latest and latest.get('contract_sha256') == CONTRACT_SHA256:
            current[mid] = latest
        grade = rows.get(grade_key(mid))
        if (grade and grade.get('contract_sha256') == CONTRACT_SHA256
                and grade.get('deployment_id') == lab.get('deployment_id')):
            selected[mid] = grade
    earned = sum(int(selected[m]['raw_earned']) for m in MISSIONS if m in selected)
    pending = [m for m in MISSIONS if m not in selected]
    uncertain = [m for m in MISSIONS if m in current and not current[m].get('evaluable')]
    context = lab.get('assessment_context', 'unassigned')
    return dict(lab_id=lab['lab_id'], contract_id=CONTRACT_ID, contract_sha256=CONTRACT_SHA256,
                assessment_context=context, course_export_eligible=context == 'course',
                raw_earned=earned, raw_maximum=MAXIMUM, fully_evaluated=not pending and not uncertain,
                complete=not pending and all(current.get(m, {}).get('complete') for m in MISSIONS),
                missing_or_unresolved=pending, current_unresolved=uncertain,
                current=current, selected=selected)


def export_labs(labs, after='', limit=25):
    """No email, secret, normalized 25-point grade, or fixture grade enters this export."""
    exported = []
    candidates = sorted(labs, key=lambda r: r['lab_id'])
    for lab in candidates:
        view = project_lab(lab)
        if not view['course_export_eligible'] or lab['lab_id'] <= after:
            continue
        if len(exported) == limit:
            break
        def compact(row):
            if not row:
                return None
            numeric = ('raw_earned', 'raw_maximum', 'unresolved')
            return {k: int(v) if k in numeric else v for k, v in row.items() if k in (*numeric, 'readiness_ok',
                'evaluable', 'complete', 'received_at', 'checked_at', 'request_id', 'deployment_id')}
        exported.append({k: v for k, v in view.items() if k not in ('current', 'selected')} | {
            'missions': {m: dict(raw_maximum=TASKS[m]['raw_points_max'],
                                selected=compact(view['selected'].get(m)), current=compact(view['current'].get(m)))
                         for m in MISSIONS}})
    last = exported[-1]['lab_id'] if exported else after
    more = any(l['lab_id'] > last and l.get('assessment_context') == 'course' for l in candidates)
    return dict(contract_id=CONTRACT_ID, contract_sha256=CONTRACT_SHA256, raw_maximum=MAXIMUM,
                normalized_course_points_included=False, students=exported, next_after=last if more else None)
