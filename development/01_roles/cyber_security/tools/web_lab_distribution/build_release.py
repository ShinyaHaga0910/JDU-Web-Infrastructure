"""Promote an accepted immutable D08 core into a signed distribution kit."""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
from distribution import digest, load_module, read, save_json, timestamp, verify


def acceptance(proof, checked, index):
    required_true = ('candidate_acceptance_passed', 'fresh_student_create_accepted',
        'teacher_exact_bodies_receipts_and_latest_verified', 'all_five_actual_ssm_user_sessions_verified',
        'all_four_persistent_internal_ssh_verified', 'all_five_s3_bootstrap_access_closed',
        'original_ids_roots_work_ssh_and_grading_credential_retained_after_restart',
        'operator_post_restart_gui_and_firefox_confirmed', 'student_signed_short_commands_verified',
        'teacher_short_dashboard_command_verified', 'student_services_restored_to_initial_state')
    manifest = checked['manifest']
    if (any(proof.get(k) is not True for k in required_true)
            or proof['manifest_sha256'] != checked['manifest_sha256']
            or proof['payload_sha256'] != manifest['artifacts']['repo_bundle']['sha256']
            or proof['teacher_api_base_url'] != 'https://' + manifest['grading']['fqdn']
            or proof['teacher_fixed_ipv4'] != manifest['grading']['ipv4']
            or proof['foundation_checks_passed'] != 47 or proof['aws_checks_passed'] != 29
            or proof['web02_assessments_verified'] != 13 or proof['teacher_exact_stored_reports'] != 17
            or index.get('candidate_acceptance_passed') is not True
            or index['class_id'] != proof['class_id'] or index['deployment_id'] != proof['deployment_id']):
        raise ValueError('Fresh cross-account acceptance for this exact core is required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'acceptance', 'evidence-index', 'output', 'signing-home'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--fingerprint', required=True)
    parser.add_argument('--distribution-id', required=True)
    parser.add_argument('--teacher-stack', default='jdu-web-progress-2026')
    args = parser.parse_args()
    os.umask(0o077)
    here = Path(__file__).resolve().parent
    validation = load_module('jdu_distribution_builder_core_validation', args.core / 'release_validation.py')
    checked = validation.verify_release(args.core / 'deployment-manifest.json', args.core / 'deployment-manifest.json.asc',
        args.core / 'package-signing-public.asc', args.fingerprint, args.core, include_bundle=False)
    proof = json.loads(read(args.acceptance))
    index = json.loads(read(args.evidence_index))
    acceptance(proof, checked, index)
    for entry in index['files']:
        data = read(args.evidence_index.parent / entry['path'], 16 * 1048576)
        if (digest(data), len(data)) != (entry['sha256'], entry['size_bytes']):
            raise ValueError('Recorded public or encrypted acceptance evidence differs')
    args.output.mkdir(mode=0o700, exist_ok=False)
    (args.output / 'core').mkdir(mode=0o700)
    for source in args.core.iterdir():
        data = read(source, 4 * 1048576)
        (args.output / 'core' / source.name).write_bytes(data)
    for name in ('distribution.py', 'publish_release.py', 'STUDENT.md', 'TEACHER.md', 'RELEASE.md'):
        shutil.copyfile(here / name, args.output / name)
    shutil.copyfile(args.core / 'package-signing-public.asc', args.output / 'package-signing-public.asc')
    # Cohort software contains no test student's identity, state, keys or token.
    save_json(args.output / 'ACCEPTANCE.json', dict(scope='d08_immutable_core_acceptance_reference',
        core_manifest_sha256=checked['manifest_sha256'], payload_sha256=proof['payload_sha256'],
        accepted_at=proof['completed_at'], evidence_index_sha256=digest(read(args.evidence_index)),
        source_acceptance_sha256=digest(read(args.acceptance)), fresh_cross_account_create=True,
        aws_checks=29, foundation_checks=47, web02_assessments=13, teacher_exact_reports=17,
        post_restart_gui=True, initial_environment_distribution_only=True, class_ready=False))
    now = datetime.now(timezone.utc)
    release = dict(schema_version=1, scope='d08_initial_environment_distribution',
        distribution_id=args.distribution_id, class_id=proof['class_id'], teacher_account=proof['teacher_account'],
        teacher_stack=args.teacher_stack, region=checked['manifest']['region'], created_at=now.isoformat(),
        expires_at=min(now + timedelta(days=7), timestamp(checked['manifest']['expires_at'])).isoformat(),
        core_manifest_sha256=checked['manifest_sha256'], distribution_ready=True, class_ready=False,
        course_points_assigned=False, files=[])
    for source in sorted(args.output.rglob('*')):
        if source.is_file():
            data = source.read_bytes()
            release['files'].append(dict(path=source.relative_to(args.output).as_posix(), sha256=digest(data), size_bytes=len(data)))
    save_json(args.output / 'distribution-release.json', release)
    sign = ['gpg', '--no-options', '--homedir', str(args.signing_home), '--batch', '--digest-algo', 'SHA256',
        '--local-user', args.fingerprint, '--armor', '--detach-sign']
    subprocess.run(sign + ['--output', str(args.output / 'distribution-release.json.asc'),
        str(args.output / 'distribution-release.json')], capture_output=True, check=True)
    verify(args.output, args.fingerprint)
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for source in sorted(args.output.rglob('*')):
            if source.is_file():
                data = source.read_bytes()
                item = tarfile.TarInfo('jdu-web-distribution/' + source.relative_to(args.output).as_posix())
                item.size = len(data); item.mode = 0o600; item.mtime = 0
                tar.addfile(item, io.BytesIO(data))
    archive = Path(str(args.output) + '.tar.gz')
    data = gzip.compress(out.getvalue(), mtime=0)
    with archive.open('xb') as stream:
        stream.write(data)
    subprocess.run(sign + ['--output', str(archive) + '.asc', str(archive)], capture_output=True, check=True)
    save_json(Path(str(args.output) + '.public.json'), dict(distribution_id=args.distribution_id,
        archive_sha256=digest(data), archive_size_bytes=len(data), distribution_ready=True, class_ready=False,
        class_id=proof['class_id'], teacher_account=proof['teacher_account'], expires_at=release['expires_at'],
        core_manifest_sha256=checked['manifest_sha256'], immutable_core_preserved=True, credentials_included=False))
    print('SIGNED_D08_DISTRIBUTION_BUILT; immutable core preserved; full course remains pending')


if __name__ == '__main__':
    main()
