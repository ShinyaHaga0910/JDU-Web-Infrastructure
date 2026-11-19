#!/usr/bin/env python3
"""One teacher run and one student run for the S3-free Web Lab foundation."""

import argparse
import base64
from contextlib import contextmanager, suppress
import fcntl
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import termios
from threading import Event, Thread
import time
import tty
from unicodedata import east_asian_width
from urllib.parse import urlsplit
from urllib.request import urlopen
import uuid


REGION = 'us-east-1'
TEACHER_STACK = 'jdu-web-infrastructure-teacher'
STUDENT_STACK_PREFIX = 'jdu-web-infrastructure-student-'
REPO = 'https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure'
TOOLS = 'development/01_roles/cyber_security/tools'
BOOT = TOOLS + '/web_lab_bootstrap'
TEACHER = TOOLS + '/web_lab_teacher'
ASSESSMENT = TOOLS + '/web_lab_assessment'
LOCK = 'development/03_knowledge/aws_official/web_lab_packages_2026-10-15'
ROLES = {role.lower(): role for role in ('Bastion', 'Web', 'Dns', 'Db', 'Repo')}
IPS = dict(bastion='10.20.1.10', web='10.20.1.20', dns='10.20.2.10', db='10.20.2.20', repo='10.20.2.30')
ACCOUNT = re.compile('[0-9]{12}')
RELEASE = 'web-2026-10-r1'
GUEST_ROOT = '/var/lib/jdu-web-classroom'
PORT = 18974
MAX_ASSET = 200 * 1024 * 1024
AWS_PROGRESS_INTERVAL = 30
STAGES = {
    'teacher': ('aws', 'stack', 'invites', 'done'),
    'student': ('aws', 'session_tool', 'stack', 'waiting', 'assets', 'repo', 'nodes',
                'ssh', 'lessons', 'grading', 'done'),
    'reset-rdp': ('aws', 'reset_target', 'reset_password', 'reset_done'),
}

# UI messages follow the same order for all four languages.
LABELS = ('teacher', 'student', 'invite', 'share_code', 'paste_code', 'rdp_setup', 'password_reminder', 'password_masked',
          'password', 'password_again', 'password_invalid', 'password_mismatch', 'aws', 'stack', 'waiting',
          'invites', 'assets', 'repo', 'nodes', 'ssh', 'lessons', 'grading', 'done', 'tty', 'input_error', 'invitation_error', 'notice')
TEXT = {
    'en': ('Teacher setup', 'Student setup', 'Course enrollment code', 'Share this code with your students.',
           'Copy and paste the code you received from your teacher.',
           'Choose your own password. You will use it later to open the desktop of the lab’s bastion server (RDP).',
           'Remember this password. If you forget it, you cannot connect and continue the lab.',
           'Each character appears as *. Enter the same password twice.',
           'Choose a password (4–128 characters)', 'Enter the same password again',
           'Use 4–128 characters on one line.', 'The two entries do not match. Enter your password again.',
           'Checking the AWS account and prerequisites',
           'Deploying with CloudFormation', 'Waiting for the AWS resources', 'Preparing the shared course enrollment code',
           'Verifying and transferring dependencies', 'Building the signed internal package repository',
           'Preparing and checking the five servers', 'Verifying internal SSH', 'Staging lesson files', 'Registering and testing grading',
           'Foundation setup complete', 'Use an interactive CloudShell terminal.',
           'Check the values entered and the current AWS account.',
           'The course enrollment code is incorrect. Please restart the setup.',
           'Google login and browser grading require separate setup.'),
    'ja': ('教師側の構築', '学生側の構築', '授業の共通登録コード', 'このコードを学生に伝えてください。',
           '教師から教えられたコードをコピー＆ペーストで入力してください。',
           '自分でパスワードを決めてください。後で、演習用の踏み台サーバーのデスクトップを開くとき（RDP接続）に使います。',
           'このパスワードを忘れないでください。忘れると踏み台サーバーに接続できず、演習を進められません。',
           '入力した文字は1文字ずつ * で表示されます。同じパスワードを2回入力してください。',
           '自分で決めたパスワード（4〜128文字）', '同じパスワードをもう一度入力',
           'パスワードは1行で4〜128文字にしてください。', '2回の入力が一致しません。もう一度設定してください。',
           'AWSアカウントと前提条件を確認',
           'CloudFormationで構築', 'AWSリソースの準備を待機', '授業の共通登録コードを準備',
           '依存パッケージを検証・転送', '署名付きの内部パッケージ配布先を構築',
           'サーバー5台を準備・確認', '内部SSHを確認', '授業用ファイルを配置', '採点登録と試験送信', '基盤の構築・確認が完了',
           '対話型のCloudShellで実行してください。', '入力内容と現在のAWSアカウントを確認してください。',
           '共通登録コードが違います。最初からやり直してください。',
           'Googleログインとブラウザ採点には別途設定が必要です。'),
    'ru': ('Настройка преподавателя', 'Настройка студента', 'Код регистрации на курс', 'Передайте этот код студентам.',
           'Скопируйте и вставьте код, который вам дал преподаватель.',
           'Придумайте свой пароль. Позже он понадобится, чтобы открыть рабочий стол учебного сервера доступа (RDP).',
           'Запомните этот пароль. Если вы его забудете, то не сможете подключиться к серверу и продолжить практикум.',
           'Каждый введённый символ отображается как *. Введите один и тот же пароль дважды.',
           'Придуманный пароль (4–128 символов)', 'Введите тот же пароль ещё раз',
           'Введите от 4 до 128 символов в одной строке.', 'Введённые пароли не совпадают. Попробуйте ещё раз.',
           'Проверка аккаунта AWS и требований',
           'Развёртывание через CloudFormation', 'Ожидание ресурсов AWS', 'Подготовка общего кода регистрации на курс',
           'Проверка и передача зависимостей', 'Создание подписанного внутреннего репозитория пакетов',
           'Настройка и проверка пяти серверов', 'Проверка внутреннего SSH', 'Размещение учебных файлов', 'Регистрация и проверка оценивания',
           'Базовая настройка завершена', 'Используйте интерактивный терминал CloudShell.',
           'Проверьте введённые данные и текущий аккаунт AWS.',
           'Неверный код регистрации на курс. Запустите настройку заново.',
           'Вход через Google и проверку в браузере нужно настроить отдельно.'),
    'uz': ('O‘qituvchi muhiti', 'Talaba muhiti', 'Kursga ro‘yxatdan o‘tish kodi', 'Ushbu kodni talabalarga bering.',
           'O‘qituvchi bergan kodni nusxalab, kiritish maydoniga joylang.',
           'Parolni o‘zingiz tanlang. Keyin undan amaliyotdagi oraliq serverning ish stolini ochishda (RDP) foydalanasiz.',
           'Bu parolni unutmang. Parolni unutsangiz, serverga ulana olmaysiz va amaliyotni davom ettira olmaysiz.',
           'Har bir kiritilgan belgi * ko‘rinishida chiqadi. Bir xil parolni ikki marta kiriting.',
           'O‘zingiz tanlagan parol (4–128 belgi)', 'Xuddi shu parolni yana kiriting',
           'Parol bir qatorda 4–128 belgidan iborat bo‘lsin.', 'Parollar mos kelmadi. Qaytadan kiriting.',
           'AWS hisobi va talablarni tekshirish',
           'CloudFormation orqali yaratish', 'AWS resurslarini kutish', 'Kurs uchun umumiy ro‘yxatdan o‘tish kodini tayyorlash',
           'Bog‘liqliklarni tekshirish va uzatish', 'Imzolangan ichki paket repozitoriysini yaratish',
           'Beshta serverni tayyorlash va tekshirish', 'Ichki SSH aloqasini tekshirish', 'Dars fayllarini joylash', 'Ro‘yxatdan o‘tkazish va baholashni tekshirish',
           'Asosiy muhit tayyor', 'Interaktiv CloudShell terminalidan foydalaning.',
           'Kiritilgan ma’lumotlar va joriy AWS hisobini tekshiring.',
           'Kursga ro‘yxatdan o‘tish kodi noto‘g‘ri. Sozlashni boshidan boshlang.',
           'Google orqali kirish va brauzerda tekshirish alohida sozlanadi.'),
}
SERVER_NAMES = {
    'en': ('Bastion server', 'Web server', 'DNS server', 'Database server', 'Package server'),
    'ja': ('踏み台サーバー', 'Webサーバー', 'DNSサーバー', 'DBサーバー', '配布サーバー'),
    'ru': ('Сервер доступа', 'Веб-сервер', 'DNS-сервер', 'Сервер базы данных', 'Сервер пакетов'),
    'uz': ('Oraliq server', 'Veb-server', 'DNS serveri', 'Ma’lumotlar bazasi serveri', 'Paket tarqatish serveri'),
}
SESSION_TOOL = {
    'en': 'Preparing the AWS Session Manager plugin',
    'ja': 'AWS Session Managerプラグインを準備',
    'ru': 'Подготовка плагина AWS Session Manager',
    'uz': 'AWS Session Manager plaginini tayyorlash',
}
PROGRESS_TEXT = {
    'en': ('Total stages: {total}', 'This may take several minutes. Keep this terminal open.',
           'Waiting for AWS · elapsed {elapsed}'),
    'ja': ('全{total}工程', '数分かかることがあります。この画面を開いたままお待ちください。',
           'AWSで処理中です · 経過 {elapsed}'),
    'ru': ('Всего этапов: {total}', 'Это может занять несколько минут. Оставьте терминал открытым.',
           'Ожидание AWS · прошло {elapsed}'),
    'uz': ('Jami {total} bosqich', 'Bu bir necha daqiqa olishi mumkin. Terminalni ochiq qoldiring.',
           'AWS jarayoni davom etmoqda · o‘tgan vaqt {elapsed}'),
}
RESET_LABELS = ('reset-rdp', 'reset_target', 'reset_choice', 'reset_password', 'reset_done', 'reset_error')
RESET_TEXT = {
    'en': ('Reset your RDP password', 'Check your bastion server', 'Enter the number of your Lab',
           'Set a new password', 'RDP password reset complete',
           'Use the CloudShell where you set up this Lab. Check that the bastion is running and managed by Systems Manager.'),
    'ja': ('RDPパスワードの再設定', '自分の踏み台サーバーを確認', '対象のLabの番号を入力',
           '新しいパスワードを設定', 'RDPパスワードの再設定が完了しました',
           'このLabを構築したCloudShellを開き、踏み台サーバーが稼働中でSystems Managerに接続されていることを確認してください。'),
    'ru': ('Сброс пароля RDP', 'Проверка вашего сервера доступа', 'Введите номер вашей лабораторной среды',
           'Задайте новый пароль', 'Пароль RDP успешно изменён',
           'Откройте CloudShell, где вы настроили эту среду. Убедитесь, что сервер доступа запущен и подключён к Systems Manager.'),
    'uz': ('RDP parolini qayta o‘rnatish', 'Oraliq serveringizni tekshirish', 'Lab raqamingizni kiriting',
           'Yangi parolni tanlang', 'RDP paroli qayta o‘rnatildi',
           'Lab muhitini sozlagan CloudShell’ni oching. Oraliq server ishlayotganini va Systems Manager’ga ulanganini tekshiring.'),
}
STUDENT_WAIT_TEXT = {
    'en': ('CloudFormation finished. Waiting for all five servers to connect to Systems Manager.',
           'All five servers are connected. Installing the setup helpers.'),
    'ja': ('CloudFormationの構築が完了しました。5台のサーバーがSystems Managerに接続するのを待っています。',
           '5台すべてが接続しました。サーバーにセットアップ用のファイルを配置しています。'),
    'ru': ('CloudFormation завершил развёртывание. Ожидается подключение всех пяти серверов к Systems Manager.',
           'Все пять серверов подключены. Размещаются файлы для настройки.'),
    'uz': ('CloudFormation muhitni yaratdi. Beshta serverning Systems Manager’ga ulanishi kutilmoqda.',
           'Beshta serverning barchasi ulandi. Sozlash fayllari joylanmoqda.'),
}


class Screen:
    def __init__(self, language, role):
        self.text = dict(zip(LABELS, TEXT[language]))
        self.text.update(zip(RESET_LABELS, RESET_TEXT[language]))
        self.text.update(zip(('wait_for_ssm', 'deploy_helpers'), STUDENT_WAIT_TEXT[language]))
        self.text['session_tool'] = SESSION_TOOL[language]
        self.stages = STAGES[role]
        self.total = len(self.stages)
        total_label, self.wait_hint, self.wait_update = PROGRESS_TEXT[language]
        self.servers = dict(zip(ROLES, SERVER_NAMES[language]))
        print('\n' + '═' * 56 + f'\n  JDU WEB INFRASTRUCTURE  /  {self.text[role]}\n'
              f'  {total_label.format(total=self.total)}\n' + '═' * 56)

    def step(self, key):
        number = self.stages.index(key) + 1
        print(f'\n┌─ {number:02d}/{self.total:02d}  {self.text[key]}', flush=True)

    def record(self, value):
        print(f'│  {value}', flush=True)

    @contextmanager
    def aws_wait(self, total=None):
        self.record(self.wait_hint)
        started = time.monotonic()
        finished = Event()
        completed = 0

        def update_count(number):
            nonlocal completed
            completed = number

        def show_elapsed():
            while not finished.wait(AWS_PROGRESS_INTERVAL):
                minutes, seconds = divmod(int(time.monotonic() - started), 60)
                count = f' ({completed}/{total})' if total is not None else ''
                self.record(self.wait_update.format(elapsed=f'{minutes:02d}:{seconds:02d}') + count)

        reporter = Thread(target=show_elapsed, daemon=True)
        reporter.start()
        try:
            yield update_count
        finally:
            finished.set()
            reporter.join()

    def prompt(self, key, secret=False):
        prompt = f'  ▸ {self.text[key]}: '
        return masked_password(prompt) if secret else input(prompt)


def masked_password(prompt):
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    characters = []
    escape = ''

    try:
        tty.setcbreak(fd)
        print(prompt, end='', file=sys.stderr, flush=True)
        while True:
            char = sys.stdin.read(1)
            if not char or char == '\x04':
                raise EOFError
            if char in '\r\n':
                return ''.join(characters)
            if char == '\x1b':
                escape = char
                continue
            if escape == '\x1b':
                escape = char if char in '[O' else ''
                if escape:
                    continue
            elif escape:
                if '@' <= char <= '~':
                    escape = ''
                continue
            if char in ('\x7f', '\b') and characters:
                characters.pop()
                print('\b \b', end='', file=sys.stderr, flush=True)
            elif char.isprintable():
                characters.append(char)
                print('*', end='', file=sys.stderr, flush=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
        print(file=sys.stderr, flush=True)


def encoded(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode()


def summary(path):
    with path.open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(data)


def remote_source(ref, path):
    with urlopen(f'{REPO}/{ref}/{path}', timeout=35) as response:
        data = response.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('SOURCE_SIZE')
    return data


def ensure_session_plugin(ref):
    if shutil.which('session-manager-plugin'):
        return
    platform_name = {'x86_64': 'linux_64bit', 'aarch64': 'linux_arm64'}.get(platform.machine())
    if not platform_name or not shutil.which('rpm'):
        raise ValueError('SSM_PLUGIN_PLATFORM')
    url = ('https://s3.amazonaws.com/session-manager-downloads/plugin/latest/'
           f'{platform_name}/session-manager-plugin.rpm')
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        key = root / 'aws.asc'
        key.write_bytes(remote_source(ref, BOOT + '/session-manager-signer.asc'))
        package = root / 'session-manager-plugin.rpm'
        signature = root / 'session-manager-plugin.rpm.sig'
        for path, address, limit in ((package, url, 32 * 1024 * 1024), (signature, url + '.sig', 8192)):
            with urlopen(address, timeout=40) as response:
                data = response.read(limit + 1)
            if not 0 < len(data) <= limit:
                raise ValueError('SSM_PLUGIN_SIZE')
            path.write_bytes(data)
        gpg = ['gpg', '--homedir', scratch, '--batch', '--no-options']
        subprocess.run(gpg + ['--import', str(key)], check=True, capture_output=True)
        status = subprocess.check_output(gpg + ['--status-fd', '1', '--verify', str(signature), str(package)],
                                         stderr=subprocess.DEVNULL, text=True)
        fingerprint = '7959637124CE093AD501D47A2C4D4AFF6F6757EE'
        if not any(line.startswith(f'[GNUPG:] VALIDSIG {fingerprint} ') for line in status.splitlines()):
            raise ValueError('SSM_PLUGIN_SIGNATURE')
        subprocess.run(['sudo', '-n', 'rpm', '-U', str(package)], capture_output=True, check=True)
    if not shutil.which('session-manager-plugin'):
        raise ValueError('SSM_PLUGIN_MISSING')


def invitation(value):
    prefix = 'jdu2.' if 'enrollment_token' in value else 'jdu1.'
    return prefix + base64.urlsafe_b64encode(encoded(value)).decode().rstrip('=')


def parse_invitation(value, account):
    if len(value) > 2048 or not re.fullmatch(r'jdu[12]\.[A-Za-z0-9_-]+', value):
        raise ValueError('INVITATION_FORMAT')
    body = value[5:]
    try:
        info = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
    except ValueError:
        raise ValueError('INVITATION_FORMAT') from None
    fields = {'teacher_account', 'api_base_url', 'fixed_ingress_ipv4', 'release_id', 'schema_version'}
    shared = value.startswith('jdu2.')
    fields |= {'enrollment_token'} if shared else {'student_account', 'lab_id', 'lab_token'}
    if (not isinstance(info, dict) or set(info) != fields
            or not all(isinstance(info[k], str) for k in fields - {'schema_version'})
            or not ACCOUNT.fullmatch(info['teacher_account']) or info['teacher_account'] == account
            or not re.fullmatch(r'[A-Za-z0-9_-]{43}', info['enrollment_token' if shared else 'lab_token'])
            or info['release_id'] != RELEASE or info['schema_version'] != 1):
        raise ValueError('INVITATION_ACCOUNT_OR_SCOPE')
    if not shared and (info['student_account'] != account or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', info['lab_id'])):
        raise ValueError('INVITATION_ACCOUNT_OR_SCOPE')
    return info


def classroom_template(base):
    removed = {'S3Endpoint', 'RepoHandleC3', 'AllNodesHandleC3', 'RepoReadyC3', 'AllNodesReadyC3'}
    for name in removed:
        del base['Resources'][name]
    parameters = {'AvailabilityZone', 'StudentKeyName', 'RdpPasswordHash', 'LabId', 'DeploymentId',
                  'GradingIpv4', 'BastionInstanceType', 'SmallInstanceType', 'DnsInstanceType'}
    base['Parameters'] = {k: {p: v for p, v in value.items() if p != 'Default'}
                          for k, value in base['Parameters'].items() if k in parameters}
    del base['Conditions']
    base['Outputs'].pop('S3Endpoint', None)
    resources = base['Resources']
    resources['BootstrapSg']['Properties']['GroupDescription'] = 'Classroom SSM only'
    resources['BootstrapSg']['Properties']['SecurityGroupEgress'] = [{'IpProtocol': '-1', 'CidrIp': '127.0.0.1/32'}]
    resources['BastionSsmOut']['Properties']['GroupId'] = {'Ref': 'BootstrapSg'}
    resources['SsmSg']['Properties']['SecurityGroupIngress'][0]['SourceSecurityGroupId'] = {'Ref': 'BootstrapSg'}
    for label in ROLES.values():
        resource = resources[label + 'Instance']
        dependencies = [n for n in resource['DependsOn'] if n not in removed]
        resource['DependsOn'] = sorted(set(dependencies) | {'SsmEndpoint', 'SsmMessagesEndpoint', 'BastionSsmOut'})
        properties = resource['Properties']
        properties.pop('UserData')
        properties['IamInstanceProfile'] = 'LabInstanceProfile'
        if label == 'Bastion':
            data = {'write_files': [{'path': '/var/lib/jdu-web-classroom/rdp.hash', 'permissions': '0600',
                                     'content': '${RdpPasswordHash}'}]}
            properties['UserData'] = {'Fn::Base64': {'Fn::Sub': '#cloud-config\n' + json.dumps(data) + '\n'}}
    base['Description'] = 'Five Web Lab nodes with private Systems Manager delivery.'
    return base


def assessment_api_source(ref):
    from build_teacher import inline_source

    sources = {name: remote_source(ref, f'{ASSESSMENT}/{name}.py').decode()
               for name in ('registry', 'grading', 'dashboard', 'progress_api_v2')}
    sources['progress_api'] = remote_source(ref, TEACHER + '/progress_api.py').decode()
    sources['registry_data'] = remote_source(ref, ASSESSMENT + '/assessment-registry.json').decode()
    return inline_source(sources)


def teacher_run(args, screen, session, account, work):
    import install_teacher

    key_path = work / 'enrollment.private.json'
    if not key_path.exists():
        write(key_path, encoded({'token': secrets.token_urlsafe(32)}))
    token = install_teacher.read_private(key_path)['token']
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise ValueError('ENROLLMENT_KEY')
    enrollment = (assessment_api_source(args.ref), hashlib.sha256(token.encode()).hexdigest())
    screen.step('stack')
    name = TEACHER_STACK
    with screen.aws_wait():
        credentials = install_teacher.install(session, session.client('cloudformation'), session.client('ec2'), account,
                                              name, work, distribution_bucket=False, inform=lambda *_, **__: None,
                                              enrollment=enrollment)
    screen.record(name)
    screen.step('invites')
    info = {k: credentials[k] for k in ('schema_version', 'api_base_url', 'fixed_ingress_ipv4', 'release_id')}
    code = work / 'classroom.invitation.txt'
    data = (invitation(dict(info, teacher_account=account, enrollment_token=token)) + '\n').encode()
    if not code.exists():
        write(code, data)
    elif code.is_symlink() or code.stat().st_mode & 0o077 or code.read_bytes() != data:
        raise ValueError('EXISTING_INVITATION_DIFFERS')
    return data.decode().strip()


def capacity(ec2):
    zones = {x['ZoneName'] for x in ec2.describe_availability_zones(Filters=[
        {'Name': 'zone-type', 'Values': ['availability-zone']}, {'Name': 'state', 'Values': ['available']},
    ])['AvailabilityZones']}
    families = ('t3a', 't3')
    sizes = ('micro', 'small', 'medium')
    offers = ec2.get_paginator('describe_instance_type_offerings').paginate(LocationType='availability-zone', Filters=[
        {'Name': 'instance-type', 'Values': [f'{f}.{s}' for f in families for s in sizes]},
    ])
    available = {(o['Location'], o['InstanceType']) for page in offers for o in page['InstanceTypeOfferings']}
    for family in families:
        for zone in sorted(zones):
            if all((zone, f'{family}.{size}') in available for size in sizes):
                return zone, family
    raise ValueError('EC2_CAPACITY')


def rdp_password_hash(screen):
    screen.record(screen.text['rdp_setup'])
    screen.record(screen.text['password_reminder'])
    screen.record(screen.text['password_masked'])
    while True:
        password = screen.prompt('password', secret=True)
        if not 4 <= len(password) <= 128 or any(ch in password for ch in '\r\n\0'):
            screen.record(screen.text['password_invalid'])
            continue
        if password != screen.prompt('password_again', secret=True):
            screen.record(screen.text['password_mismatch'])
            continue
        return subprocess.check_output(
            ['openssl', 'passwd', '-6', '-stdin'], input=(password + '\n').encode()
        ).decode().strip()


def stack_setup(cfn, ec2, account, invite, work, ref, screen):
    import install_teacher
    name = STUDENT_STACK_PREFIX + invite['lab_id']
    # Validate bytes even on resume. A changed installer revision must not adopt a different stack.
    body = json.dumps(classroom_template(json.loads(remote_source(ref, 'development/templates/web-lab-student.template.json'))), separators=(',', ':'))
    intent_path = work / 'deployment.json'
    receipt = work / 'stack.json'
    stack = install_teacher.find_stack(cfn, name)
    if receipt.exists() and not stack:
        raise ValueError('STACK_MISSING')
    if intent_path.exists():
        state = install_teacher.read_private(intent_path)
        if (state['account'], state['name'], state['ref']) != (account, name, ref):
            raise ValueError('DEPLOYMENT_IDENTITY')
    elif stack:
        raise ValueError('UNOWNED_STACK')
    else:
        nodes = ec2.get_paginator('describe_instances').paginate(Filters=[
            {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped', 'shutting-down']},
        ])
        if sum(len(r['Instances']) for page in nodes for r in page['Reservations']) + 5 > 9:
            raise ValueError('EC2_BUDGET')
        zone, family = capacity(ec2)
        key = ec2.describe_key_pairs(KeyNames=['vockey'], IncludePublicKey=True)['KeyPairs'][0]
        public = ' '.join(key['PublicKey'].split()[:2])
        if not re.fullmatch(r'ssh-(rsa|ed25519) [A-Za-z0-9+/=]+', public):
            raise ValueError('ACADEMY_PUBLIC_KEY')
        cfn.validate_template(TemplateBody=body)
        state = dict(account=account, name=name, ref=ref, deployment_id=str(uuid.uuid4()), public_key=public, zone=zone, family=family)
        write(intent_path, encoded(state))
    if not stack:
        password_hash = rdp_password_hash(screen)
        values = dict(AvailabilityZone=state['zone'], StudentKeyName='vockey', RdpPasswordHash=password_hash,
                      LabId=invite['lab_id'], DeploymentId=state['deployment_id'], GradingIpv4=invite['fixed_ingress_ipv4'])
        for field, size in (('Bastion', 'medium'), ('Small', 'small'), ('Dns', 'micro')):
            values[field+'InstanceType'] = state['family'] + '.' + size
        stack_id = cfn.create_stack(StackName=name, TemplateBody=body, DisableRollback=True, ClientRequestToken=state['deployment_id'],
                                    Parameters=[{'ParameterKey': k, 'ParameterValue': v} for k, v in values.items()])['StackId']
    else:
        ids = {p['ParameterKey']: p['ParameterValue'] for p in stack['Parameters']}
        if ids['DeploymentId'] != state['deployment_id'] or ids['LabId'] != invite['lab_id']:
            raise ValueError('WRONG_STACK')
        stack_id = stack['StackId']
        live = cfn.get_template(StackName=stack_id, TemplateStage='Original')['TemplateBody']
        if (json.loads(live) if isinstance(live, str) else live) != json.loads(body):
            raise ValueError('STACK_TEMPLATE_CHANGED')
    if receipt.exists() and install_teacher.read_private(receipt)['id'] != stack_id:
        raise ValueError('STACK_REPLACED')
    if not receipt.exists():
        write(receipt, encoded({'id': stack_id}))
    return state, stack_id


def wait_online(ssm, nodes):
    for _ in range(60):
        info = ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds', 'Values': list(nodes.values())}])
        if {i['InstanceId'] for i in info['InstanceInformationList'] if i['PingStatus'] == 'Online'} == set(nodes.values()):
            return
        time.sleep(10)
    raise ValueError('SSM_ONLINE')


def command(ssm, node, shell, seconds=300):
    request = ssm.send_command(InstanceIds=[node], DocumentName='AWS-RunShellScript',
                               Parameters={'commands': [shell], 'executionTimeout': [str(seconds)]})['Command']['CommandId']
    end = time.monotonic() + seconds + 45
    while time.monotonic() < end:
        try:
            state = ssm.get_command_invocation(CommandId=request, InstanceId=node)
        except ssm.exceptions.InvocationDoesNotExist:
            time.sleep(2)
            continue
        if state['Status'] == 'Success':
            return state['StandardOutputContent'].strip()
        if state['Status'] not in ('Pending', 'InProgress', 'Delayed'):
            diagnostics = state.get('StandardErrorContent', '')
            last = diagnostics.rstrip().splitlines()[-1:] if diagnostics else []
            # Include only the Python exception type, never remote stdout, argv or input.
            failure = last[0].split(':', 1)[0] if last else ''
            detail = failure if re.fullmatch('[A-Za-z][A-Za-z0-9.]{1,45}', failure) else state['Status']
            raise ValueError(f'SSM_{detail} {request}')
        time.sleep(4)
    raise ValueError(f'SSM_TIMEOUT {request}')


def deploy_guest(ref, ssm, nodes):
    files = ('classroom_guest.py', 'node_bootstrap.py', 'payload_runtime.py', 'release_validation.py', 'internal_ssh_guest.py')
    encoded_files = {name: base64.b64encode(remote_source(ref, BOOT + '/' + name)).decode() for name in files}
    for node in nodes.values():
        # Separate invocations keep every command comfortably below the SSM input limit.
        for name, data in encoded_files.items():
            command(ssm, node, f'install -d -m 0755 {GUEST_ROOT} && printf %s {shlex.quote(data)} | base64 -d > {GUEST_ROOT}/{name}')
    for name in ('progress_enrollment_guest.py', 'web_progress.py'):
        data = base64.b64encode(remote_source(ref, TEACHER + '/' + name)).decode()
        command(ssm, nodes['bastion'], f'printf %s {shlex.quote(data)} | base64 -d > {GUEST_ROOT}/{name}')


def guest(ssm, node, config, file='classroom_guest.py', seconds=900):
    data = base64.b64encode(encoded(config)).decode()
    return json.loads(command(ssm, node, f'printf %s {shlex.quote(data)} | base64 -d | python3 -B {GUEST_ROOT}/{file}', seconds))


def register_bastion(ref, ssm, bastion, config, deployment):
    from enroll_five_node_progress import encrypt

    helper = 'progress_enrollment_guest.py'
    binding = dict(lab_id=config['lab_id'], release_id=RELEASE, deployment_id=deployment, instance_id=bastion)
    status = guest(ssm, bastion, dict(binding, command='status'), helper)
    source = remote_source(ref, TEACHER + '/web_progress.py')
    request = dict(binding, client_source_b64=base64.b64encode(source).decode(),
                   client_sha256=hashlib.sha256(source).hexdigest())
    if status['credential_present']:
        request['command'] = 'complete' if status['transport_private_key_present'] else 'verify'
    else:
        cert = guest(ssm, bastion, dict(binding, command='recipient'), helper)
        certificate = cert['certificate_pem'].encode()
        if hashlib.sha256(certificate).hexdigest() != cert['certificate_sha256']:
            raise ValueError('GRADING_CERTIFICATE')
        envelope = encoded(dict(binding, schema_version=1, purpose='progress_registration', credentials=config))
        request.update(command='register', ciphertext_b64=base64.b64encode(encrypt(certificate, envelope)).decode())
    result = guest(ssm, bastion, request, helper)
    if not result['registered'] or not result['transport_private_key_retired'] or result['instance_count'] != 5:
        raise ValueError('GRADING_REGISTRATION')


def stage_lessons(ref, ssm, nodes, common):
    base = 'course/labs/resources'
    signed_resources = LOCK + '/web-course-class193548-20261103-r3/assessment'
    files = {name: remote_source(ref, signed_resources + '/' + name)
             for name in ('catalog-app.tar.gz', 'registry.py', 'assessment-registry.json', 'database_secret.py')}
    files['offline_assets.py'] = remote_source(ref, base + '/offline_assets.py')
    files['classroom-python-packages.json'] = remote_source(ref, LOCK + '/python-packages.json')
    files['classroom-requirements.lock'] = remote_source(ref, LOCK + '/requirements.lock')
    with tempfile.TemporaryDirectory() as scratch:
        helper_path = Path(scratch) / 'stage_resources.py'
        helper_path.write_bytes(remote_source(ref, base + '/stage_resources.py'))
        spec = importlib.util.spec_from_file_location('stage_resources', helper_path)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        for role in ('web', 'db'):
            request = {k: common[k] for k in ('lab_id', 'deployment_id')}
            request.update(role=role, instance_id=nodes[role],
                           files={name: base64.b64encode(data).decode() for name, data in files.items()})
            outcome = helper.send_stage(ssm, nodes[role], request)
            if not outcome['public_resources_ready'] or outcome['role'] != role:
                raise ValueError('LESSON_RESOURCES')


def assets(ref):
    definition = json.loads(remote_source(ref, BOOT + '/classroom-dependencies.json'))
    debs = json.loads(remote_source(ref, LOCK + '/deb-packages.json'))
    wheels = json.loads(remote_source(ref, LOCK + '/python-packages.json'))
    profile = json.loads(remote_source(ref, BOOT + '/package-profile.json'))
    index = {}
    versions = {}
    for row in debs:
        if row['package'] == 'firefox':
            continue
        name = Path(row['path']).name
        path = urlsplit(row['source']).path.removeprefix('/ubuntu')
        index[name] = (f'https://snapshot.ubuntu.com/ubuntu/{definition["ubuntu_snapshot"]}{path}', row['sha256'])
        versions[row['package']] = row['version']
    for wheel in wheels:
        with urlopen(f'https://pypi.org/pypi/{wheel["name"]}/{wheel["version"]}/json', timeout=30) as response:
            matches = [r for r in json.load(response)['urls'] if r['filename'] == wheel['filename']
                       and r['digests']['sha256'] == wheel['sha256'] and urlsplit(r['url']).hostname == 'files.pythonhosted.org']
        if len(matches) != 1:
            raise ValueError('PYTHON_DEPENDENCY_LOCK')
        index[wheel['filename']] = (matches[0]['url'], wheel['sha256'])
    firefox = definition['firefox']
    index[firefox['filename']] = (firefox['url'], firefox['sha256'])
    if not all(re.fullmatch(r'[a-zA-Z0-9_.+%~:-]{1,200}', k) and re.fullmatch('[a-f0-9]{64}', v[1]) for k, v in index.items()):
        raise ValueError('DEPENDENCY_LOCK')
    return index, versions, profile['roles'], definition, remote_source(ref, LOCK + '/requirements.lock').decode()


def exchange(port, method, name, digest, path=None):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=180)
    try:
        headers = {'X-Asset-SHA256': digest}
        if path is None:
            conn.request(method, '/' + name, headers=headers)
        else:
            headers['Content-Length'] = str(path.stat().st_size)
            with path.open('rb') as stream:
                conn.request(method, '/' + name, stream, headers)
        response = conn.getresponse()
        response.read()
        return response.status
    finally:
        conn.close()


def transfer(ssm, node, index, recipe, screen, update_count):
    command(ssm, node, 'systemctl stop jdu-classroom-receiver.service 2>/dev/null || true; '
            f'systemd-run --unit=jdu-classroom-receiver --property=RuntimeMaxSec=3600 python3 -B {GUEST_ROOT}/classroom_guest.py receive')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    params = json.dumps({'portNumber': [str(PORT)], 'localPortNumber': [str(port)]})
    process = None
    try:
        process = subprocess.Popen(['aws', 'ssm', 'start-session', '--region', REGION, '--target', node,
                                    '--document-name', 'AWS-StartPortForwardingSession', '--parameters', params],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            if process.poll() is not None:
                raise ValueError('SSM_PORT_FORWARD')
            try:
                if exchange(port, 'HEAD', 'ready', '0' * 64) == 404:
                    break
            except (OSError, http.client.HTTPException):
                time.sleep(2)
        else:
            raise ValueError('SSM_PORT_FORWARD_TIMEOUT')
        with tempfile.TemporaryDirectory() as scratch:
            temp = Path(scratch) / 'asset'
            for number, (name, (url, expected)) in enumerate(index.items(), 1):
                if exchange(port, 'HEAD', name, expected) != 200:
                    digest = hashlib.sha256()
                    size = 0
                    with urlopen(url, timeout=45) as response, temp.open('wb') as stream:
                        while chunk := response.read(1024 * 1024):
                            size += len(chunk)
                            if size > MAX_ASSET:
                                raise ValueError(f'ASSET_SIZE {name}')
                            digest.update(chunk)
                            stream.write(chunk)
                    if digest.hexdigest() != expected or exchange(port, 'PUT', name, expected, temp) != 201:
                        raise ValueError(f'ASSET_VERIFICATION {name}')
                    temp.unlink()
                update_count(number)
                if number % 50 == 0 or number == len(index):
                    screen.record(f'{number}/{len(index)}')
            temp.write_bytes(encoded(recipe))
            expected = summary(temp)
            if exchange(port, 'PUT', 'recipe.json', expected, temp) != 201:
                raise ValueError('RECIPE_TRANSFER')
            return expected
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        command(ssm, node, 'systemctl stop jdu-classroom-receiver.service')


def student_credentials(invite, parent):
    import install_teacher
    import web_progress

    config = {k: invite[k] for k in ('schema_version', 'api_base_url', 'fixed_ingress_ipv4', 'release_id')}
    if 'enrollment_token' not in invite:
        config.update(lab_id=invite['lab_id'], lab_token=invite['lab_token'])
        web_progress.request(config, '/api/web/student/session', {'lab_id': config['lab_id']}, config['lab_token'])
        return config

    endpoint = hashlib.sha256(config['api_base_url'].rstrip('/').encode()).hexdigest()
    identity = parent / f'enrollment-{endpoint}.json'
    if not identity.exists():
        write(identity, encoded({'lab_id': 'lab-' + secrets.token_hex(10), 'lab_token': secrets.token_urlsafe(32)}))
    lab = install_teacher.read_private(identity)
    config.update(lab_id=lab['lab_id'], lab_token=lab['lab_token'])
    request = {k: config[k] for k in ('lab_id', 'lab_token', 'release_id')}
    result = web_progress.request(config, '/api/web/enroll', request, invite['enrollment_token'])
    if result.get('ok') is not True or any(result.get(k) != config[k] for k in ('lab_id', 'release_id')):
        raise ValueError('ENROLLMENT_RECEIPT')
    return config


def student_run(args, screen, session, account, parent):
    import install_teacher

    screen.record(screen.text['paste_code'])
    invite = parse_invitation(screen.prompt('invite').strip(), account)
    if not shutil.which('aws'):
        raise ValueError('SSM_CLIENT')
    with os.fdopen(os.open(parent / 'install.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from web_progress import ProgressHttpError

        try:
            config = student_credentials(invite, parent)
        except ProgressHttpError as exc:
            if exc.status == 401:
                raise ValueError('INVITATION_REJECTED') from None
            raise
        screen.step('session_tool')
        ensure_session_plugin(args.ref)
        screen.step('stack')
        work = parent / config['lab_id']
        work.mkdir(mode=0o700, exist_ok=True)
        credential_path = work / 'student.credentials.json'
        if not credential_path.exists():
            write(credential_path, encoded(config))
        elif install_teacher.read_private(credential_path) != config:
            raise ValueError('OLD_STUDENT_CREDENTIAL_DIFFERS')
        setup_student(args, screen, session, account, config, work)


def setup_student(args, screen, session, account, config, work):
    import install_teacher

    intent = work / 'deployment.json'
    ref = install_teacher.read_private(intent)['ref'] if intent.exists() else args.ref
    if not re.fullmatch('[a-f0-9]{40}', ref):
        raise ValueError('SOURCE_REVISION')
    cfn = session.client('cloudformation')
    ssm = session.client('ssm')
    index, versions, roles, definitions, requirements = assets(ref)
    state, stack_id = stack_setup(cfn, session.client('ec2'), account, config, work, ref, screen)
    screen.step('waiting')
    with screen.aws_wait():
        cfn.get_waiter('stack_create_complete').wait(StackName=stack_id)
        result = cfn.describe_stacks(StackName=stack_id)['Stacks'][0]
        output = {x['OutputKey']: x['OutputValue'] for x in result['Outputs']}
        nodes = {role: output[label + 'InstanceId'] for role, label in ROLES.items()}
        screen.record(screen.text['wait_for_ssm'])
        wait_online(ssm, nodes)
        screen.record(screen.text['deploy_helpers'])
        deploy_guest(ref, ssm, nodes)
    common = dict(lab_id=config['lab_id'], deployment_id=state['deployment_id'], release_id=RELEASE,
                  student_public_key=state['public_key'], grading_api_url=config['api_base_url'],
                  grading_ipv4=config['fixed_ingress_ipv4'], instances=nodes)

    def pinned(packages):
        return [f'{n}={versions[n]}' for n in sorted(set(packages) - {'firefox'})]

    screen.step('assets')
    recipe = dict(assets={n: item[1] for n, item in index.items()}, requirements=requirements,
                  packages=pinned(roles['common'] + roles['repo']))
    with screen.aws_wait(total=len(index)) as update_count:
        repo_hash = transfer(ssm, nodes['repo'], index, recipe, screen, update_count)
    screen.step('repo')
    public_key = guest(ssm, nodes['repo'], {'operation': 'repo', 'recipe_sha256': repo_hash})['key']
    screen.step('nodes')
    roles_checked = {}
    for role, node in nodes.items():
        packages = roles['common'] + roles.get(role, [])
        if role == 'bastion':
            packages += definitions['firefox_libraries'] + definitions['desktop_tools']
        request = dict(common, operation='configure', role=role, instance_id=node, public_key=public_key,
                       packages=pinned(packages), firefox=definitions['firefox'])
        check = guest(ssm, node, request)
        if check['role'] != role or check['instance_id'] != node or not all(check['checks'].values()):
            raise ValueError('ROLE_VERIFICATION')
        roles_checked[role] = check
        screen.record(f'✓  {screen.servers[role]}  {node}')

    screen.step('ssh')
    peers = {r: dict(private_ip=IPS[r], instance_id=node,
                     host_key=command(ssm, node, "cut -d ' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub"))
             for r, node in nodes.items() if r != 'bastion'}
    bastion = nodes['bastion']
    ssh_id = dict(lab_id=config['lab_id'], deployment_id=state['deployment_id'])
    helper = 'internal_ssh_guest.py'
    local_key = guest(ssm, bastion, dict(ssh_id, command='init', instance_id=bastion, peers=peers), helper)['public_key']
    for role, peer in peers.items():
        guest(ssm, peer['instance_id'], dict(ssh_id, command='authorize', role=role, instance_id=peer['instance_id'], public_key=local_key), helper)
        command(ssm, bastion, f'sudo -u labuser timeout 15 /usr/local/bin/lab-ssh {role} < /dev/null')
    screen.step('lessons')
    stage_lessons(ref, ssm, nodes, common)

    screen.step('grading')
    register_bastion(ref, ssm, bastion, config, state['deployment_id'])
    request_path = work / 'foundation-request.json'
    if not request_path.exists():
        write(request_path, encoded({'id': str(uuid.uuid4())}))
    report = dict(schema_version=1, kind='bootstrap', lab_id=config['lab_id'], release_id=RELEASE,
                  deployment_id=state['deployment_id'], request_id=install_teacher.read_private(request_path)['id'], checks=[
                      dict(id=f'CLASSROOM_{r.upper()}', role=r, instance_id=nodes[r], status='PASS') for r in roles_checked])
    receipt = guest(ssm, bastion, {'operation': 'submit', 'report': report})
    screen.record('✓  ' + receipt['received_at'])
    screen.record(f'RDP: {output["BastionPublicIp"]}  /  labuser')


def reset_labs(cfn, account, parent):
    from install_teacher import find_stack, read_private

    candidates = {}
    for directory in sorted(parent.glob('lab-*')):
        lab_id = directory.name
        if directory.is_symlink() or not directory.is_dir() or not re.fullmatch(r'lab-[a-z0-9-]{1,28}', lab_id):
            continue
        info = directory.stat()
        if info.st_mode & 0o077 or info.st_uid != os.getuid():
            continue
        intent, receipt = directory / 'deployment.json', directory / 'stack.json'
        if not intent.is_file() or not receipt.is_file():
            continue
        try:
            state = read_private(intent)
            stack_id = read_private(receipt)['id']
            deployment = str(uuid.UUID(state['deployment_id']))
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            continue
        name = STUDENT_STACK_PREFIX + lab_id
        expected_arn = f'arn:aws:cloudformation:{REGION}:{account}:stack/{name}/'
        if (state.get('account') != account or state.get('name') != name or not isinstance(stack_id, str)
                or not stack_id.startswith(expected_arn) or deployment != state['deployment_id']):
            continue
        stack = find_stack(cfn, stack_id)
        if (not stack or stack['StackId'] != stack_id or stack['StackName'] != name
                or stack['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE')):
            continue
        parameters = {item['ParameterKey']: item['ParameterValue'] for item in stack['Parameters']}
        if (parameters.get('LabId'), parameters.get('DeploymentId')) == (lab_id, deployment):
            candidates[lab_id] = (stack, deployment)
    return candidates


def reset_bastion(cfn, ec2, ssm, account, lab_id, stack, deployment):
    resource = cfn.describe_stack_resource(StackName=stack['StackId'],
                                           LogicalResourceId='BastionInstance')['StackResourceDetail']
    node = resource['PhysicalResourceId']
    output = {item['OutputKey']: item['OutputValue'] for item in stack['Outputs']}
    if (resource['ResourceType'] != 'AWS::EC2::Instance' or resource['StackId'] != stack['StackId']
            or resource['ResourceStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE')
            or not re.fullmatch(r'i-[0-9a-f]{8}(?:[0-9a-f]{9})?', node) or output.get('BastionInstanceId') != node):
        raise ValueError('RDP_RESET_TARGET')
    reservations = ec2.describe_instances(InstanceIds=[node])['Reservations']
    instances = [instance for reservation in reservations if reservation['OwnerId'] == account
                 for instance in reservation['Instances'] if instance['InstanceId'] == node]
    if len(instances) != 1:
        raise ValueError('RDP_RESET_TARGET')
    instance, = instances
    tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
    if ((tags.get('LabId'), tags.get('DeploymentId'), tags.get('Name')) !=
            (lab_id, deployment, stack['StackName'] + '-bastion') or instance['PrivateIpAddress'] != IPS['bastion']):
        raise ValueError('RDP_RESET_TARGET')
    if instance['State']['Name'] != 'running':
        raise ValueError('RDP_RESET_BASTION_NOT_RUNNING')
    records = ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds', 'Values': [node]}])
    if not any(record['InstanceId'] == node and record['PingStatus'] == 'Online'
               for record in records['InstanceInformationList']):
        raise ValueError('RDP_RESET_SSM_OFFLINE')
    return instance


def reset_rdp(args, screen, session, account, parent):
    from enroll_five_node_progress import encrypt

    screen.step('reset_target')
    cfn, ec2, ssm = (session.client(service) for service in ('cloudformation', 'ec2', 'ssm'))
    with os.fdopen(os.open(parent / 'install.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        candidates = reset_labs(cfn, account, parent)
        if not candidates:
            raise ValueError('RDP_RESET_NO_LAB')
        labs = list(candidates)
        lab_id = labs[0]
        if len(labs) > 1:
            choices = {str(index): lab for index, lab in enumerate(labs, 1)}
            for number, lab in choices.items():
                screen.record(f'{number}. {lab}')
            while True:
                selection = screen.prompt('reset_choice').strip()
                if selection in choices:
                    lab_id = choices[selection]
                    break
        stack, deployment = candidates[lab_id]
        instance = reset_bastion(cfn, ec2, ssm, account, lab_id, stack, deployment)
        node = instance['InstanceId']
        screen.record(f'{lab_id} / {node}')
        screen.step('reset_password')
        binding = dict(lab_id=lab_id, deployment_id=deployment, instance_id=node, nonce=secrets.token_hex(16))
        source = base64.b64encode(remote_source(args.ref, BOOT + '/rdp_reset_guest.py')).decode()
        program = ('import base64,sys; '
                   f'sys.path.insert(0,{GUEST_ROOT!r}); exec(base64.b64decode({source!r}))')

        def request(phase, **fields):
            payload = base64.b64encode(encoded(dict(binding, phase=phase, **fields))).decode()
            shell = f'printf %s {shlex.quote(payload)} | base64 -d | python3 -B -c {shlex.quote(program)}'
            return json.loads(command(ssm, node, shell, seconds=25 if phase == 'cancel' else 90))

        envelope = encoded(dict(binding, purpose='rdp-password-reset', password_hash=rdp_password_hash(screen)))
        try:
            recipient = request('prepare')
            certificate = recipient['certificate_pem'].encode()
            if (recipient['nonce'] != binding['nonce'] or not certificate.startswith(b'-----BEGIN CERTIFICATE-----')
                    or hashlib.sha256(certificate).hexdigest() != recipient['certificate_sha256']):
                raise ValueError('RDP_RESET_CERTIFICATE')
            ciphertext = base64.b64encode(encrypt(certificate, envelope)).decode()
            if request('apply', ciphertext=ciphertext) != dict(binding, applied=True):
                raise ValueError('RDP_RESET_RECEIPT')
        except (Exception, KeyboardInterrupt):
            with suppress(Exception):
                request('cancel')
            raise
    screen.step('reset_done')
    if instance.get('PublicIpAddress'):
        screen.record(f'RDP: {instance["PublicIpAddress"]}  /  labuser')


def main():
    try:
        return run_cli()
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130


def run_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=STAGES)
    parser.add_argument('--ref', required=True, help='Exact GitHub commit for the installer and accompanying source files.')
    parser.add_argument('--lang', choices=TEXT)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        print(dict(zip(LABELS, TEXT[args.lang or 'en']))['tty'], file=sys.stderr)
        return 2
    if not args.lang:
        lines = (
            'JDU WEB INFRASTRUCTURE',
            '',
            'Choose your language',
            'Enter one number from 1 to 4, then press Enter.',
            '',
            '[1] English',
            '[2] Japanese',
            '[3] Русский',
            '[4] O‘zbekcha',
        )
        width = 52
        border = '─' * (width + 4)
        print(f'\n┌{border}┐')
        for line in lines:
            columns = sum(2 if east_asian_width(char) in ('W', 'F') else 1 for char in line)
            print(f'│  {line}{" " * (width - columns)}  │')
        print(f'└{border}┘')
        selections = dict(zip('1234', TEXT))
        answer = input('  Enter your number (1-4): ').strip()
        while answer not in selections:
            answer = input('  Please enter 1, 2, 3, or 4: ').strip()
        args.lang = selections[answer]
    screen = Screen(args.lang, args.role)
    try:
        screen.step('aws')
        if not re.fullmatch('[a-f0-9]{40}', args.ref):
            raise ValueError('SOURCE_REVISION')
        os.umask(0o077)
        sys.dont_write_bytecode = True
        with tempfile.TemporaryDirectory() as temp:
            sys.path.insert(0, temp)
            for name in ('install_teacher.py', 'web_progress.py', 'enroll_five_node_progress.py'):
                Path(temp, name).write_bytes(remote_source(args.ref, TEACHER + '/' + name))
            if args.role == 'teacher':
                Path(temp, 'build_teacher.py').write_bytes(remote_source(args.ref, ASSESSMENT + '/build_teacher.py'))
            import boto3
            session = boto3.Session(region_name=REGION)
            account = session.client('sts').get_caller_identity()['Account']
            if not ACCOUNT.fullmatch(account):
                raise ValueError('AWS_ACCOUNT')
            screen.record(f'{account} / {REGION}')
            role_dir = 'teacher' if args.role == 'teacher' else 'student'
            work = Path.home() / '.local/share/jdu-web-classroom' / account / role_dir
            if args.role != 'reset-rdp':
                work.mkdir(parents=True, mode=0o700, exist_ok=True)
            if args.role == 'reset-rdp' and not work.exists():
                raise ValueError('RDP_RESET_NO_LAB')
            if work.is_symlink() or not work.is_dir() or work.stat().st_mode & 0o077 or work.stat().st_uid != os.getuid():
                raise ValueError('PRIVATE_WORKSPACE')
            if args.role == 'teacher':
                with os.fdopen(os.open(work / 'install.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)) as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    enrollment_code = teacher_run(args, screen, session, account, work)
            elif args.role == 'student':
                student_run(args, screen, session, account, work)
            else:
                reset_rdp(args, screen, session, account, work)
                return 0
        screen.step('done')
        screen.record(screen.text['notice'])
        if args.role == 'teacher':
            print(f'\n{screen.text["invite"]}\n{screen.text["share_code"]}\n{enrollment_code}', flush=True)
        return 0
    except Exception as exc:
        code = getattr(exc, 'response', {}).get('Error', {}).get('Code', type(exc).__name__)
        if type(exc) is ValueError and re.fullmatch('[A-Za-z0-9_.+%~: -]{1,220}', str(exc)):
            code = str(exc)
        guidance = 'reset_error' if args.role == 'reset-rdp' else 'input_error'
        if code in ('INVITATION_FORMAT', 'INVITATION_ACCOUNT_OR_SCOPE', 'INVITATION_REJECTED'):
            guidance = 'invitation_error'
        print(f'\nError: [{code}]\n{screen.text[guidance]}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
