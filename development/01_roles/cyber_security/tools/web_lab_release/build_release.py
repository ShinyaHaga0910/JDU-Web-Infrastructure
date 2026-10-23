"""Build a signed student release around the exact accepted D08 and D11 bytes."""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
from release_tools import digest, encoded, load, parse, read, save, time_value, tree, POINTS

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('foundation', 'assessment', 'teacher-evidence', 'student-evidence', 'output', 'signing-home'):
        p.add_argument('--' + n, required=True, type=Path)
    p.add_argument('--trusted-fingerprint', required=True)
    p.add_argument('--distribution-id', required=True)
    a = p.parse_args()
    foundation_module = load('jdu_course_builder_foundation', a.foundation / 'distribution.py')
    foundation = foundation_module.verify(a.foundation, a.trusted_fingerprint)
    validation = load('jdu_course_builder_signature', a.foundation / 'core/release_validation.py')
    raw = read(a.assessment)
    key = read(a.foundation / 'package-signing-public.asc')
    validation.verify_signature(raw, read(str(a.assessment) + '.asc'), key, a.trusted_fingerprint)
    assessment_module = load('jdu_course_builder_assessment', ROOT.parent / 'web_lab_assessment/candidate_install.py')
    assessment_files, assessment_manifest = assessment_module.checked_archive(raw)
    teacher, student = [parse(read(v)) for v in (a.teacher_evidence, a.student_evidence)]
    st, final = student['acceptance'], teacher['final']
    if (teacher['archive_sha256'] != digest(raw) or final['raw_earned'] != 62 or final['raw_maximum'] != 62
            or final['mission_points'] != POINTS or final['current_unknown']
            or final['exact_report_and_receipt_pairs_verified'] < 18
            or final['verification_context_retained'] is not True or final['actual_course_export_count'] != 0
            or teacher['private_s3_three_objects_full_get_verified'] is not True
            or st['mission_points'] != POINTS or st['raw_earned'] != 62 or st['practice_p0_p6_complete'] is not True
            or st['interactive_ssm_hidden_prompt_and_wrong_password_rejection'] is not True):
        raise ValueError('Exact accepted 62-point cross-account runtime evidence required')
    a.output.mkdir(mode=0o700, exist_ok=False)
    for name, data in tree(a.foundation).items():
        path = a.output / 'foundation' / name; path.parent.mkdir(mode=0o700, parents=True, exist_ok=True); save(path, data)
    for name, data in assessment_files.items():
        path = a.output / 'assessment' / name; path.parent.mkdir(mode=0o700, parents=True, exist_ok=True); save(path, data)
    save(a.output / 'assessment.tar.gz', raw)
    save(a.output / 'assessment.tar.gz.asc', read(str(a.assessment) + '.asc'))
    save(a.output / 'package-signing-public.asc', key)
    for name in ('release_tools.py', 'student.py', 'teacher.py', 'STUDENT.md', 'TEACHER.md', 'RELEASE.md'):
        save(a.output / name, read(ROOT / name))
    save(a.output / 'ACCEPTANCE.json', encoded(dict(scope='accepted_runtime_reference',
        teacher_evidence_sha256=digest(read(a.teacher_evidence)), student_evidence_sha256=digest(read(a.student_evidence)),
        assessment_archive_sha256=digest(raw), mission_points=POINTS, raw_maximum=62,
        exact_report_receipt_pairs=final['exact_report_and_receipt_pairs_verified'], verification_excluded=True,
        interactive_hidden_input_and_wrong_password_rejection=True, functional_success_real_http=True,
        successful_human_password_entry_tested=False, class_ready=False, test_student_identity_included=False)))
    now = datetime.now(timezone.utc)
    registry = parse(assessment_files['assessment-registry.json'])
    value = dict(schema_version=1, scope='web_course_distribution', distribution_id=a.distribution_id,
        class_id=foundation['release']['class_id'], teacher_account=foundation['release']['teacher_account'], region='us-east-1',
        created_at=now.isoformat(), expires_at=min(now + timedelta(days=7), time_value(foundation['release']['expires_at'])).isoformat(),
        foundation_distribution_sha256=foundation['release_sha256'], core_manifest_sha256=foundation['core']['manifest_sha256'],
        assessment_archive_sha256=digest(raw), assessment_manifest_sha256=digest(assessment_files['D11-MANIFEST.json']),
        contract_id=registry['contract_id'], contract_sha256=digest(assessment_files['assessment-registry.json']), raw_maximum=62,
        distribution_ready=True, class_ready=False,
        files=[dict(path=n, sha256=digest(v), size_bytes=len(v)) for n, v in sorted(tree(a.output).items())])
    save(a.output / 'course-release.json', encoded(value))
    sign = ['gpg', '--no-options', '--homedir', str(a.signing_home), '--batch', '--digest-algo', 'SHA256',
        '--local-user', a.trusted_fingerprint, '--armor', '--detach-sign']
    subprocess.run(sign + ['--output', str(a.output / 'course-release.json.asc'), str(a.output / 'course-release.json')], check=True, capture_output=True)
    load('jdu_course_builder_complete_verification', a.output / 'release_tools.py').verify(a.output, a.trusted_fingerprint)
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(tree(a.output).items()):
            info = tarfile.TarInfo('jdu-web-course/' + name); info.size = len(data); info.mode = 0o600; info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    archive_path = Path(str(a.output) + '.tar.gz'); data = gzip.compress(out.getvalue(), mtime=0); save(archive_path, data)
    subprocess.run(sign + ['--output', str(archive_path) + '.asc', str(archive_path)], check=True, capture_output=True)
    save(str(a.output) + '.public.json', encoded(dict(distribution_id=a.distribution_id,
        archive_sha256=digest(data), archive_size_bytes=len(data), release_sha256=digest(encoded(value)),
        file_count=len(value['files']), raw_maximum=62, expires_at=value['expires_at'],
        distribution_ready=True, class_ready=False, foundation_and_assessment_bytes_preserved=True, credentials_included=False)))
    print('SIGNED_WEB_COURSE_RELEASE_BUILT; immutable accepted foundation and assessment preserved')


if __name__ == '__main__':
    main()
