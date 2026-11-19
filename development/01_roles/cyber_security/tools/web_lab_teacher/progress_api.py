"""Separate Web Lab progress API. No Linux tables, functions or keys are used.

Stores anonymous Lab IDs and authenticated reports, not authoritative exam grades.
An individual credential is required to bind a five-node lab and submit reports.
"""

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import time
import uuid
from urllib.parse import quote


LAB_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,31}")
RELEASE_RE = re.compile(r"web-[0-9]{4}-[0-9]{2}-r[1-9][0-9]*")
INSTANCE_RE = re.compile(r"i-[0-9a-f]{17}")
ROLES = {"bastion", "repo", "dns", "db", "web"}
STATUSES = {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}
MAX_BODY = 96 * 1024


def result_key(report):
    return 'LATEST#' + ('BOOTSTRAP' if report['kind'] == 'bootstrap' else report['mission_id'])


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def require_keys(body, required, optional=()):
    if type(body) is not dict or not set(required) <= body.keys() or body.keys() - set(required) - set(optional):
        raise ApiError(400, "invalid fields")


def field(body, name, pattern=None, minimum=1, maximum=256):
    value = body.get(name)
    if type(value) is not str or not minimum <= len(value) <= maximum or (pattern and not pattern.fullmatch(value)):
        raise ApiError(400, "invalid " + name)
    return value


def uuid_field(body, name):
    value = field(body, name, maximum=36)
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise ApiError(400, "invalid " + name)
    if str(parsed) != value or parsed.version != 4:
        raise ApiError(400, "invalid " + name)
    return value


def parse_body(event):
    text = event.get("body", "") or ""
    if not isinstance(text, str) or len(text) > MAX_BODY * 2:
        raise ApiError(413, "request too large")
    try:
        raw = base64.b64decode(text, validate=True) if event.get("isBase64Encoded") else text.encode()
        if len(raw) > MAX_BODY:
            raise ApiError(413, "request too large")
        def pairs(values):
            result = {}
            for key, value in values:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result
        body = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(body) is not dict:
            raise ValueError()
        return body
    except (ValueError, UnicodeError, RecursionError):
        raise ApiError(400, "invalid JSON")


def authorization(event):
    headers = {str(k).lower(): v for k, v in event.get("headers", {}).items()}
    value = headers.get("authorization", "")
    return value[7:] if isinstance(value, str) and value.startswith("Bearer ") else ""


def response(status, body, content_type="application/json; charset=utf-8"):
    return {"statusCode": status, "headers": {
        "Content-Type": content_type, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"},
        "body": encoded(body) if not isinstance(body, str) else body}


class DynamoStore:
    """Conditional operations keep credential binding and report writes atomic."""
    def __init__(self, table_name):
        import boto3
        from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
        self.client = boto3.client("dynamodb")
        self.table = table_name
        self.serializer, self.deserializer = TypeSerializer(), TypeDeserializer()

    def pack(self, row):
        return {k: self.serializer.serialize(v) for k, v in row.items()}

    def get(self, pk, sk):
        row = self.client.get_item(TableName=self.table, Key=self.pack({"pk": pk, "sk": sk}), ConsistentRead=True).get("Item")
        return {k: self.deserializer.deserialize(v) for k, v in row.items()} if row else None

    def put_new(self, row):
        try:
            self.client.put_item(TableName=self.table, Item=self.pack(row), ConditionExpression="attribute_not_exists(pk)")
        except self.client.exceptions.ConditionalCheckFailedException:
            return False
        return True

    def bind(self, pk, token_hash, release_id, deployment_id, instances):
        try:
            self.client.update_item(TableName=self.table, Key=self.pack({"pk": pk, "sk": "META"}),
                UpdateExpression="SET deployment_id=:deployment, #instances=:instances, updated_at=:now",
                ConditionExpression="token_hash=:token AND release_id=:release AND #active=:active AND (attribute_not_exists(deployment_id) OR (deployment_id=:deployment AND #instances=:instances))",
                ExpressionAttributeNames={"#active":"active","#instances":"instances"},
                ExpressionAttributeValues=self.pack({":token": token_hash, ":release": release_id, ":deployment": deployment_id,
                    ":instances": instances, ":active": True, ":now": now_iso()}))
        except self.client.exceptions.ConditionalCheckFailedException:
            raise ApiError(409, "lab binding conflict")

    def submit(self, meta, attempt, summary):
        latest = dict(summary, pk=meta['pk'], sk=result_key(attempt['report']),
                      checks=attempt['report']['checks'])
        try:
            self.client.transact_write_items(TransactItems=[
                {"Put": {"TableName": self.table, "Item": self.pack(attempt), "ConditionExpression": "attribute_not_exists(pk)"}},
                {"Put": {"TableName": self.table, "Item": self.pack(latest),
                    "ConditionExpression": "attribute_not_exists(received_at) OR received_at<=:now",
                    "ExpressionAttributeValues": self.pack({':now': attempt['received_at']})}},
                {"Update": {"TableName": self.table, "Key": self.pack({"pk": meta["pk"], "sk": "META"}),
                    "UpdateExpression": "SET last_result=:summary, updated_at=:now",
                    "ConditionExpression": "token_hash=:token AND deployment_id=:deployment AND #active=:active AND updated_at<=:now",
                    "ExpressionAttributeNames":{"#active":"active"},
                    "ExpressionAttributeValues": self.pack({":summary": summary, ":now": attempt["received_at"],
                        ":token": meta["token_hash"], ":deployment": meta["deployment_id"], ":active": True})}}])
        except self.client.exceptions.TransactionCanceledException:
            existing = self.get(attempt["pk"], attempt["sk"])
            if existing and existing["body_sha256"] == attempt["body_sha256"]:
                return existing["receipt"]
            raise ApiError(409, "request conflict or credentials changed")
        return attempt["receipt"]

    def link_email(self, meta, email):
        self.client.update_item(TableName=self.table, Key=self.pack({'pk': meta['pk'], 'sk': 'META'}),
            UpdateExpression='SET student_email=:email, identity_updated_at=:now',
            ConditionExpression='token_hash=:token AND #active=:active',
            ExpressionAttributeNames={'#active': 'active'},
            ExpressionAttributeValues=self.pack({':email': email, ':now': now_iso(),
                                                ':token': meta['token_hash'], ':active': True}))

    def labs(self, only_lab=None):
        if only_lab:
            row = self.get("LAB#" + only_lab, "META")
            if not row:
                return []
            row['results'] = []
            cursor = None
            while True:
                args = dict(TableName=self.table, KeyConditionExpression='pk=:pk AND begins_with(sk,:prefix)',
                    ExpressionAttributeValues=self.pack({':pk': row['pk'], ':prefix': 'LATEST#'}), ConsistentRead=True)
                if cursor: args['ExclusiveStartKey'] = cursor
                data = self.client.query(**args)
                row['results'].extend({k: self.deserializer.deserialize(v) for k, v in item.items()} for item in data.get('Items', []))
                cursor = data.get('LastEvaluatedKey')
                if not cursor: break
            return [row]
        rows, cursor = [], None
        while True:
            args = {"TableName": self.table, "FilterExpression": "sk=:meta OR begins_with(sk,:prefix)",
                    "ExpressionAttributeValues": self.pack({":meta": "META", ':prefix': 'LATEST#'})}
            if cursor:
                args["ExclusiveStartKey"] = cursor
            data = self.client.scan(**args)
            rows.extend({k: self.deserializer.deserialize(v) for k, v in row.items()} for row in data.get("Items", []))
            if len(rows) > 100000:
                raise ApiError(503, "dashboard capacity exceeded")
            cursor = data.get("LastEvaluatedKey")
            if not cursor:
                break
        labs = [r for r in rows if r['sk'] == 'META']
        if len(labs) > 1000:
            raise ApiError(503, 'dashboard capacity exceeded')
        by_pk = {}
        for r in rows:
            if r['sk'].startswith('LATEST#'):
                by_pk.setdefault(r['pk'], []).append(r)
        for lab in labs: lab['results'] = by_pk.get(lab['pk'], [])
        return labs


class ProgressService:
    def __init__(self, store, admin_hash, api_base_url, enrollment_hash=""):
        self.store, self.admin_hash, self.base_url = store, admin_hash, api_base_url
        self.enrollment_hash = enrollment_hash

    def admin(self, event):
        token = authorization(event)
        if len(token) < 32 or not hmac.compare_digest(digest(token), self.admin_hash):
            raise ApiError(401, "unauthorized")

    def lab(self, event, body):
        lab_id = field(body, "lab_id", LAB_RE, maximum=32)
        token = authorization(event)
        row = self.store.get("LAB#" + lab_id, "META")
        expected = row.get("token_hash", "") if row else "0" * 64
        if len(token) < 32 or not hmac.compare_digest(digest(token), expected) or not row or not row.get("active"):
            raise ApiError(401, "unauthorized")
        return row

    def issue(self, event):
        self.admin(event)
        return self.create_lab(parse_body(event))

    def enroll(self, event):
        token = authorization(event)
        if len(token) != 43 or not self.enrollment_hash or not hmac.compare_digest(digest(token), self.enrollment_hash):
            raise ApiError(401, "unauthorized")
        body = parse_body(event)
        if body.get("lab_token") == token:
            raise ApiError(400, "an individual token is required")
        return self.create_lab(body)

    def create_lab(self, body):
        require_keys(body, ("lab_id", "release_id", "lab_token"))
        lab_id = field(body, "lab_id", LAB_RE, maximum=32)
        release_id = field(body, "release_id", RELEASE_RE, maximum=64)
        token = field(body, "lab_token", re.compile(r"[A-Za-z0-9_-]+"), minimum=43, maximum=128)
        row = {"pk": "LAB#" + lab_id, "sk": "META", "lab_id": lab_id, "release_id": release_id,
               "token_hash": digest(token), "active": True, "created_at": now_iso(), "updated_at": now_iso()}
        if not self.store.put_new(row):
            old = self.store.get(row["pk"], "META")
            if not old or old["token_hash"] != row["token_hash"] or old["release_id"] != release_id or not old.get("active"):
                raise ApiError(409, "lab already exists; credential replacement is not automatic")
        return response(200, {"ok": True, "lab_id": lab_id, "release_id": release_id})

    def register(self, event):
        body = parse_body(event)
        require_keys(body, ("lab_id", "release_id", "deployment_id", "instances"))
        row = self.lab(event, body)
        deployment_id = uuid_field(body, "deployment_id")
        if field(body, "release_id", RELEASE_RE, maximum=64) != row["release_id"]:
            raise ApiError(409, "release mismatch")
        instances = body["instances"]
        if type(instances) is not dict or set(instances) != ROLES or any(type(v) is not str or not INSTANCE_RE.fullmatch(v) for v in instances.values()) or len(set(instances.values())) != 5:
            raise ApiError(400, "five distinct role instance IDs are required")
        if row.get("deployment_id") and (row["deployment_id"] != deployment_id or row.get("instances") != instances):
            raise ApiError(409, "existing deployment must be retained")
        self.store.bind(row["pk"], row["token_hash"], row["release_id"], deployment_id, instances)
        return response(200, {"ok": True, "lab_id": row["lab_id"], "deployment_id": deployment_id,
                              "release_id": row["release_id"], "registered": True})

    def submit(self, event):
        body = parse_body(event)
        require_keys(body, ("schema_version", "kind", "lab_id", "release_id", "deployment_id", "request_id", "checks"), ("mission_id",))
        row = self.lab(event, body)
        deployment_id = uuid_field(body, "deployment_id")
        request_id = uuid_field(body, "request_id")
        if type(body["schema_version"]) is not int or body["schema_version"] != 1 or body["kind"] not in ("bootstrap", "assessment"):
            raise ApiError(400, "invalid report type")
        if row.get("deployment_id") != deployment_id or body["release_id"] != row["release_id"]:
            raise ApiError(409, "unregistered or mismatched deployment")
        if body["kind"] == "assessment":
            field(body, "mission_id", re.compile(r"[PM][0-9]{1,2}"), maximum=3)
        elif "mission_id" in body:
            raise ApiError(400, "bootstrap reports do not award mission points")
        checks = body["checks"]
        if type(checks) is not list or not 1 <= len(checks) <= 100:
            raise ApiError(400, "invalid checks")
        seen = set()
        for check in checks:
            require_keys(check, ("id", "role", "instance_id", "status"))
            identity = field(check, "id", re.compile(r"[A-Z][A-Z0-9_-]{1,47}"), maximum=48)
            role = check["role"]
            if type(role) is not str or role not in ROLES or check["instance_id"] != row["instances"][role] or type(check["status"]) is not str or check["status"] not in STATUSES:
                raise ApiError(400, "check role, instance or status mismatch")
            if (role, identity) in seen:
                raise ApiError(400, "duplicate check")
            seen.add((role, identity))
        stamp = now_iso()
        receipt = {"ok": True, "lab_id": row["lab_id"], "deployment_id": deployment_id, "release_id": row["release_id"],
                   "request_id": request_id, "received_at": stamp, "kind": body["kind"], "stored": True}
        attempt = {"pk": row["pk"], "sk": "REQUEST#" + request_id, "body_sha256": digest(encoded(body)),
                   "received_at": stamp, "report": body, "receipt": receipt}
        summary = {"kind": body["kind"], "mission_id": body.get("mission_id", ""), "request_id": request_id,
                   "received_at": stamp, "passed": sum(c["status"] == "PASS" for c in checks), "total": len(checks),
                   "unknown": sum(c["status"] == "UNKNOWN" for c in checks)}
        return response(200, self.store.submit(row, attempt, summary))

    def link_email(self, event):
        body = parse_body(event)
        require_keys(body, ('lab_id', 'student_email'))
        row = self.lab(event, body)
        email = field(body, 'student_email', maximum=254).strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@jdu[.]uz", email):
            raise ApiError(400, 'use the confirmed JDU classroom email')
        self.store.link_email(row, email)
        return response(200, dict(ok=True, lab_id=row['lab_id'], email_linked=True))

    def session(self, event, teacher=False):
        body = parse_body(event)
        require_keys(body, () if teacher else ("lab_id",))
        if teacher:
            self.admin(event)
            lab_id, token_hash = "", ""
        else:
            row = self.lab(event, body)
            lab_id, token_hash = row["lab_id"], row["token_hash"]
        token = secrets.token_urlsafe(32)
        expiry = int(time.time()) + (1800 if teacher else 900)
        self.store.put_new({"pk": "SESSION#" + digest(token), "sk": "SESSION", "role": "teacher" if teacher else "student",
                            "lab_id": lab_id, "token_hash": token_hash, "expires_at": expiry})
        return response(200, {"url": self.base_url + "/dashboard?session=" + quote(token), "expires_at": expiry})

    def dashboard(self, event):
        token = (event.get("queryStringParameters") or {}).get("session", "")
        if type(token) is not str or not 40 <= len(token) <= 128:
            raise ApiError(401, "session expired")
        session = self.store.get("SESSION#" + digest(token), "SESSION")
        if not session or session["expires_at"] <= int(time.time()) or session["role"] not in ("teacher", "student"):
            raise ApiError(401, "session expired")
        if session["role"] == "student":
            meta = self.store.get("LAB#" + session["lab_id"], "META")
            if not meta or not meta.get("active") or not hmac.compare_digest(meta["token_hash"], session["token_hash"]):
                raise ApiError(401, "session expired")
        labs = self.store.labs(session["lab_id"] if session["role"] == "student" else None)
        query = event.get('queryStringParameters') or {}
        return response(200, render_dashboard(labs, session['role'], token, query.get('lang', 'ja')), 'text/html; charset=utf-8')

    def handle(self, event):
        try:
            route = event.get("routeKey", "")
            if route == "GET /healthz":
                return response(200, {"ok": True, "service": "jdu-web-progress", "schema_version": 1})
            if route == "POST /api/web/admin/issue":
                return self.issue(event)
            if route == "POST /api/web/enroll":
                return self.enroll(event)
            if route == "POST /api/web/register":
                return self.register(event)
            if route == "POST /api/web/submit":
                return self.submit(event)
            if route == 'POST /api/web/link-email':
                return self.link_email(event)
            if route == "POST /api/web/admin/session":
                return self.session(event, teacher=True)
            if route == "POST /api/web/student/session":
                return self.session(event)
            if route == "GET /dashboard":
                return self.dashboard(event)
            return response(404, {"error": "not found"})
        except ApiError as exc:
            return response(exc.status, {"error": exc.message})
        except Exception:
            # Never log request bodies, bearer tokens, identities or full exceptions.
            return response(503, {"error": "service unavailable"})


LABELS = {
    'ja': dict(teacher='Web実習・教師用進捗', student='Web実習・自分の進捗', language='表示言語',
        intro='学生が確認コマンドで送信した最新の結果です。30秒ごとに更新します。',
        table='学生ごとの進捗', identity='学生メール / Lab ID', missing_email='メール未登録',
        foundation='基盤確認', completed='完了 / 提出済み課題', updated='最終受信（UTC）',
        none='未提出', unknown='確認不能', details='確認項目', empty='登録されたLabはありません。',
        note='基盤確認は課題完了数に含めません。過去の最高結果ではなく、課題ごとの最新結果を表示します。',
        footer='閲覧URLは一定時間で失効します。他の人へ共有せず、共用PCでは閲覧後に閉じてください。'),
    'uz': dict(teacher='Web amaliyoti — o‘qituvchi', student='Web amaliyoti — mening natijalarim', language='Til',
        intro='Talaba tekshiruv buyrug‘i orqali yuborgan so‘nggi natijalar. Har 30 soniyada yangilanadi.',
        table='Talabalar natijalari', identity='Talaba emaili / Lab ID', missing_email='Email kiritilmagan',
        foundation='Muhit tekshiruvi', completed='Bajarilgan / yuborilgan topshiriqlar', updated='So‘nggi qabul (UTC)',
        none='Yuborilmagan', unknown='Tekshirib bo‘lmadi', details='Tekshiruvlar', empty='Lab ro‘yxatdan o‘tmagan.',
        note='Muhit tekshiruvi topshiriq soniga kirmaydi. Har bir topshiriqning eng yaxshi emas, eng so‘nggi natijasi ko‘rsatiladi.',
        footer='Havola muddati cheklangan. Uni ulashmang va umumiy kompyuterda ko‘rgach sahifani yoping.'),
    'ru': dict(teacher='Web-практикум — преподаватель', student='Web-практикум — мой прогресс', language='Язык',
        intro='Последние результаты, отправленные командой проверки. Обновление каждые 30 секунд.',
        table='Прогресс студентов', identity='Email студента / Lab ID', missing_email='Email не зарегистрирован',
        foundation='Проверка среды', completed='Завершено / отправлено заданий', updated='Последнее получение (UTC)',
        none='Не отправлено', unknown='Не удалось проверить', details='Проверки', empty='Нет зарегистрированных Lab.',
        note='Проверка среды не входит в число заданий. Показаны последние, а не лучшие результаты каждого задания.',
        footer='Ссылка действует ограниченное время. Не передавайте её другим и закройте страницу на общем компьютере.'),
}


def render_dashboard(labs, role, token, language='ja'):
    language = language if language in LABELS else 'ja'
    labels = LABELS[language]
    title = labels['teacher' if role == 'teacher' else 'student']
    esc = lambda v: html.escape(str(v), quote=True)
    results = {}
    missions = set()
    for lab in labs:
        latest = {r['sk'].removeprefix('LATEST#'): r for r in lab.get('results', [])}
        old = lab.get('last_result')
        if old:
            latest.setdefault('BOOTSTRAP' if old['kind'] == 'bootstrap' else old['mission_id'], old)
        results[lab['lab_id']] = latest
        missions.update(k for k in latest if re.fullmatch(r'[PM][0-9]{1,2}', k))
    missions = sorted(missions, key=lambda k: (int(k[1:]), k[0] != 'P'))

    def cell(value):
        if not value:
            return '<td class="missing">' + esc(labels['none']) + '</td>'
        passed, total, unknown = (int(value.get(k, 0)) for k in ('passed', 'total', 'unknown'))
        status = 'done' if total > 0 and passed == total and unknown == 0 else 'partial'
        items = ''.join('<li>' + esc(c['role']) + ' · ' + esc(c['id']) + ': <strong>' + esc(c['status']) + '</strong></li>'
                        for c in value.get('checks', []) if c['status'] != 'PASS')
        details = '<details><summary>' + esc(labels['details']) + '</summary><ul>' + items + '</ul></details>' if items else ''
        return '<td class="' + status + '"><strong>' + str(passed) + ' / ' + str(total) + '</strong>' + (
            '<br><small>' + esc(labels['unknown']) + ': ' + str(unknown) + '</small>' if unknown else '') + details + '</td>'

    rows = []
    for lab in sorted(labs, key=lambda r: (r.get('student_email', ''), r['lab_id'])):
        latest = results[lab['lab_id']]
        submitted = [latest[m] for m in missions if m in latest]
        completed = sum(int(v['total']) > 0 and int(v['passed']) == int(v['total']) and int(v['unknown']) == 0 for v in submitted)
        identity = esc(lab.get('student_email') or labels['missing_email'])
        rows.append('<tr><th scope="row">' + identity + '<br><small>Lab ID: ' + esc(lab['lab_id']) + '</small></th>'
            + cell(latest.get('BOOTSTRAP')) + ''.join(cell(latest.get(m)) for m in missions)
            + '<td>' + str(completed) + ' / ' + str(len(submitted)) + '</td><td>'
            + esc(lab.get('last_result', {}).get('received_at', '—')) + '</td></tr>')
    buttons = ''.join('<button type="submit" name="lang" value="' + code + '" aria-pressed="'
        + str(code == language).lower() + '">' + text + '</button>'
        for code, text in [('ja', '日本語'), ('uz', 'O‘zbekcha'), ('ru', 'Русский')])
    headers = [labels['identity'], labels['foundation'], *missions, labels['completed'], labels['updated']]
    head = ''.join('<th scope="col">' + esc(h) + '</th>' for h in headers)
    body = ''.join(rows) or '<tr><td colspan="' + str(len(headers)) + '">' + esc(labels['empty']) + '</td></tr>'
    return '''<!doctype html><html lang="''' + language + '''"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30"><title>''' + esc(title) + '''</title><style>
body{font:1rem/1.6 system-ui,sans-serif;margin:0;background:#f4f6fa;color:#172338}main,header,footer{max-inline-size:90rem;margin:auto;padding:1rem 2rem}h1{font-size:1.7rem}form{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}button{font:inherit;min-block-size:2.5rem;border:1px solid #71839d;border-radius:.4rem;background:white;padding:.4rem .8rem;color:#172338;cursor:pointer}button[aria-pressed=true]{background:#174f83;color:white}button:focus-visible,summary:focus-visible,.wrap:focus-visible{outline:3px solid #a04400;outline-offset:3px}.wrap{overflow:auto;max-block-size:70vh;container-type:inline-size;background:white;border:1px solid #c7d0de;border-radius:.5rem}table{border-collapse:separate;border-spacing:0;min-inline-size:60rem;inline-size:100%}th,td{text-align:start;padding:.8rem 1rem;border-block-end:1px solid #d8deea;vertical-align:top}thead th{position:sticky;inset-block-start:0;background:#e8eef7;z-index:2}tbody th{position:sticky;inset-inline-start:0;background:white;z-index:1;min-inline-size:13rem}thead th:first-child{inset-inline-start:0;z-index:3}caption{text-align:start;padding:1rem;font-weight:600}.done{background:#e6f5eb;color:#175c31}.partial{background:#fff2d5;color:#714900}.missing,small,footer{color:#43516a}details{max-inline-size:24rem;overflow-wrap:anywhere}summary{cursor:pointer}ul{padding-inline-start:1.2rem}@container(width < 45rem){th,td{padding:.6rem}}
</style></head><body><header><nav aria-label="''' + esc(labels['language']) + '''"><form method="get"><span>''' + esc(labels['language']) + '''</span><input type="hidden" name="session" value="''' + esc(token) + '''">''' + buttons + '''</form></nav></header><main><h1>''' + esc(title) + '''</h1><p>''' + esc(labels['intro']) + '''</p><div class="wrap" role="region" aria-label="''' + esc(labels['table']) + '''" tabindex="0"><table><caption>''' + esc(labels['table']) + '''</caption><thead><tr>''' + head + '''</tr></thead><tbody>''' + body + '''</tbody></table></div><p>''' + esc(labels['note']) + '''</p></main><footer>''' + esc(labels['footer']) + '''</footer></body></html>'''


_service = None


def handler(event, context):
    global _service
    if _service is None:
        _service = ProgressService(DynamoStore(os.environ["TABLE_NAME"]), os.environ["ADMIN_KEY_HASH"],
                                   os.environ["API_BASE_URL"], os.environ.get("ENROLLMENT_KEY_HASH", ""))
    return _service.handle(event)
