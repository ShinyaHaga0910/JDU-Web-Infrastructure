"""Business-rule tests; AWS acceptance is a separate live test."""
import copy
import json
import secrets
import time
import unittest
import uuid
from urllib.parse import urlsplit, parse_qs

import progress_api as api
import build_template


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def get(self, pk, sk):
        return copy.deepcopy(self.rows.get((pk, sk)))

    def put_new(self, row):
        key = row["pk"], row["sk"]
        if key in self.rows:
            return False
        self.rows[key] = copy.deepcopy(row)
        return True

    def record_classroom_lab(self, scope, lab_id, token_hash):
        row = self.rows[("LAB#" + lab_id, "META")]
        if row["token_hash"] != token_hash or not row["active"] or row.get("classroom_scope", scope) != scope:
            raise api.ApiError(409, "classroom enrollment conflict")
        row["classroom_scope"] = scope

    def bind(self, pk, token_hash, release_id, deployment_id, instances):
        row = self.rows[(pk, "META")]
        if row["token_hash"] != token_hash or row["release_id"] != release_id or not row["active"]:
            raise api.ApiError(409, "conflict")
        if row.get("deployment_id") and (row["deployment_id"] != deployment_id or row["instances"] != instances):
            raise api.ApiError(409, "conflict")
        row.update(deployment_id=deployment_id, instances=copy.deepcopy(instances))

    def submit(self, meta, attempt, summary):
        key = attempt["pk"], attempt["sk"]
        if key in self.rows:
            old = self.rows[key]
            if old["body_sha256"] != attempt["body_sha256"]:
                raise api.ApiError(409, "conflict")
            return copy.deepcopy(old["receipt"])
        self.rows[key] = copy.deepcopy(attempt)
        latest = dict(copy.deepcopy(summary), pk=meta['pk'], sk=api.result_key(attempt['report']),
                      checks=copy.deepcopy(attempt['report']['checks']))
        self.rows[(latest['pk'], latest['sk'])] = latest
        self.rows[(meta["pk"], "META")]["last_result"] = copy.deepcopy(summary)
        return attempt["receipt"]

    def link_email(self, meta, email):
        self.rows[(meta['pk'], 'META')]['student_email'] = email

    def labs(self, only_lab=None):
        rows = [copy.deepcopy(v) for (pk, sk), v in self.rows.items()
                if sk == "META" and (not only_lab or v["lab_id"] == only_lab)]
        for row in rows:
            row['results'] = [copy.deepcopy(v) for (pk, sk), v in self.rows.items()
                              if pk == row['pk'] and sk.startswith('LATEST#')]
        return rows


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.admin = secrets.token_urlsafe(32)
        self.token = secrets.token_urlsafe(32)
        self.app = api.ProgressService(self.store, api.digest(self.admin), "https://unit.invalid")
        self.instances = {role: "i-" + format(i, "017x") for i, role in enumerate(sorted(api.ROLES), 1)}
        self.deployment = str(uuid.uuid4())
        self.call("POST /api/web/admin/issue", {"lab_id":"test-lab","release_id":"web-2026-10-r1","lab_token":self.token}, self.admin)
        self.registration = {"lab_id":"test-lab","release_id":"web-2026-10-r1","deployment_id":self.deployment,"instances":self.instances}
        self.call("POST /api/web/register", self.registration)

    def call(self, route, body=None, token=None, query=None):
        return self.app.handle({"routeKey":route, "body":json.dumps(body if body is not None else {}),
            "headers":{"authorization":"Bearer " + (self.token if token is None else token)},
            "queryStringParameters":query})

    def report(self):
        return {"schema_version":1,"kind":"bootstrap","lab_id":"test-lab","release_id":"web-2026-10-r1",
                "deployment_id":self.deployment,"request_id":str(uuid.uuid4()),
                "checks":[{"id":"PKG_01","role":"repo","instance_id":self.instances["repo"],"status":"PASS"}]}

    def test_issue_requires_teacher(self):
        self.assertEqual(self.call("POST /api/web/admin/issue", {}, self.token)["statusCode"],401)

    def test_shared_enrollment_code_admits_multiple_labs_but_cannot_submit_or_replace_tokens(self):
        shared = secrets.token_urlsafe(32)
        self.app.enrollment_hash = api.digest(shared)
        body = dict(lab_id="new-lab", release_id="web-2026-10-r1", lab_token=secrets.token_urlsafe(32))
        route = "POST /api/web/enroll"
        self.assertEqual(self.call(route, body, self.token)["statusCode"], 401)
        self.assertEqual(self.call(route, dict(body, lab_token=shared), shared)["statusCode"], 400)
        self.assertEqual(self.call(route, body, shared)["statusCode"], 200)
        self.assertEqual(self.call(route, body, shared)["statusCode"], 200)
        self.assertEqual(self.call(route, dict(body, lab_token=secrets.token_urlsafe(32)), shared)["statusCode"], 409)
        self.assertEqual(self.call(route, dict(body, lab_id="another-lab", lab_token=secrets.token_urlsafe(32)), shared)["statusCode"], 200)
        registration = dict(self.registration, lab_id=body['lab_id'])
        self.assertEqual(self.call("POST /api/web/register", registration, shared)["statusCode"], 401)
        self.assertEqual(self.call("POST /api/web/register", registration, body['lab_token'])["statusCode"], 200)
        self.assertEqual(self.call("POST /api/web/submit", dict(self.report(), lab_id=body['lab_id']), shared)["statusCode"], 401)
        self.assertNotIn("lab_token", self.store.get("LAB#new-lab", "META"))

    def test_issue_cannot_replace_credentials(self):
        body={"lab_id":"test-lab","release_id":"web-2026-10-r1","lab_token":secrets.token_urlsafe(32)}
        self.assertEqual(self.call("POST /api/web/admin/issue",body,self.admin)["statusCode"],409)
        self.assertNotIn("lab_token", self.store.get("LAB#test-lab","META"))

    def test_issue_retry_keeps_binding(self):
        body={"lab_id":"test-lab","release_id":"web-2026-10-r1","lab_token":self.token}
        self.assertEqual(self.call("POST /api/web/admin/issue",body,self.admin)["statusCode"],200)
        self.assertEqual(self.store.get("LAB#test-lab","META")["deployment_id"],self.deployment)

    def test_registration_retry_idempotent(self):
        self.assertEqual(self.call("POST /api/web/register",self.registration)["statusCode"],200)

    def test_registration_cannot_rebind(self):
        body=copy.deepcopy(self.registration); body["deployment_id"]=str(uuid.uuid4())
        self.assertEqual(self.call("POST /api/web/register",body)["statusCode"],409)
        body=copy.deepcopy(self.registration); body["instances"]["web"]="i-"+"f"*17
        self.assertEqual(self.call("POST /api/web/register",body)["statusCode"],409)

    def test_registration_requires_five_unique_instances(self):
        body=copy.deepcopy(self.registration); body["instances"]["web"]=body["instances"]["db"]
        self.assertEqual(self.call("POST /api/web/register",body)["statusCode"],400)

    def test_bad_token_and_other_lab(self):
        body=self.report()
        self.assertEqual(self.call("POST /api/web/submit",body,"x"*43)["statusCode"],401)
        body["lab_id"]="other-lab"
        self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],401)

    def test_report_does_not_mix_deployment_release_or_host(self):
        for key,value in [("deployment_id",str(uuid.uuid4())),("release_id","web-2026-10-r2")]:
            body=self.report(); body[key]=value
            self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],409)
        body=self.report(); body["checks"][0]["instance_id"]=self.instances["web"]
        self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],400)

    def test_immutable_request_receipt(self):
        body=self.report()
        first=self.call("POST /api/web/submit",body)
        self.assertEqual(first["statusCode"],200)
        self.assertEqual(first,self.call("POST /api/web/submit",body))
        body["checks"][0]["status"]="FAIL"
        self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],409)

    def test_latest_failure_replaces_previous_pass(self):
        self.call("POST /api/web/submit",self.report())
        body=self.report(); body["checks"][0]["status"]="UNKNOWN"
        self.call("POST /api/web/submit",body)
        last=self.store.get("LAB#test-lab","META")["last_result"]
        self.assertEqual((last["passed"],last["unknown"]),(0,1))

    def test_duplicate_unknown_or_malformed_checks(self):
        body=self.report(); body["checks"]*=2
        self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],400)
        for name,value in [("status",[]),("role",[]),("status","COMPLETE")]:
            body=self.report(); body["checks"][0][name]=value
            self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],400)

    def test_no_points_or_boolean_schema_version(self):
        body=self.report(); body["points"]=25
        self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],400)
        body=self.report(); body["schema_version"]=True
        self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],400)
        body=self.report(); body["mission_id"]="P1"
        self.assertEqual(self.call("POST /api/web/submit",body)["statusCode"],400)

    def test_duplicate_json_and_oversize(self):
        event={"routeKey":"POST /api/web/register","headers":{},"body":'{"lab_id":"one","lab_id":"two"}'}
        self.assertEqual(self.app.handle(event)["statusCode"],400)
        event["body"]="x"*(api.MAX_BODY*2+1)
        self.assertEqual(self.app.handle(event)["statusCode"],413)

    def test_student_session_scope_and_expiry(self):
        session=self.call("POST /api/web/student/session",{"lab_id":"test-lab"})
        token=parse_qs(urlsplit(json.loads(session["body"])["url"]).query)["session"][0]
        query={"session":token}
        result=self.call("GET /dashboard",query=query)
        self.assertEqual(result["statusCode"],200)
        self.assertIn("test-lab",result["body"])
        self.assertNotIn(self.token,result["body"])
        self.assertNotIn(self.admin,result["body"])
        self.store.put_new({"pk":"LAB#other-lab","sk":"META","lab_id":"other-lab","release_id":"web-2026-10-r1","active":True})
        self.assertNotIn("other-lab",self.call("GET /dashboard",query=query)["body"])
        self.store.rows[("SESSION#"+api.digest(token),"SESSION")]["expires_at"]=int(time.time())-1
        self.assertEqual(self.call("GET /dashboard",query=query)["statusCode"],401)

    def test_student_session_revoked_with_lab(self):
        result=self.call("POST /api/web/student/session",{"lab_id":"test-lab"})
        token=parse_qs(urlsplit(json.loads(result["body"])["url"]).query)["session"][0]
        self.store.rows[("LAB#test-lab","META")]["active"]=False
        self.assertEqual(self.call("GET /dashboard",query={"session":token})["statusCode"],401)

    def test_session_separation_and_unknown_routes(self):
        self.assertEqual(self.call("POST /api/web/admin/session",{})["statusCode"],401)
        self.assertEqual(self.call("GET /api/web/admin/issue")["statusCode"],404)
        self.assertEqual(self.call("GET /dashboard",query={"session":self.admin})["statusCode"],401)

    def test_template_separation_and_tls(self):
        template=build_template.build(); resources=template["Resources"]
        self.assertEqual(resources["ProgressTable"]["DeletionPolicy"],"Retain")
        self.assertTrue(template["Parameters"]["AdminKeyHash"]["NoEcho"])
        instance=resources["TeacherInstance"]["Properties"]
        self.assertNotIn("IamInstanceProfile",instance)
        userdata=instance["UserData"]["Fn::Base64"]["Fn::Sub"][0]
        self.assertIn("ssl_preread on",userdata)
        config=json.loads(userdata.split("\n",1)[1])
        self.assertIn('default "";',config["write_files"][0]["content"])
        self.assertNotIn("ssl_certificate",userdata)
        self.assertLess(len(json.dumps(template).encode()),51200)

    def test_mission_results_independent_and_bootstrap_not_a_mission(self):
        for kind, mission, status in [('bootstrap', None, 'PASS'), ('assessment', 'P1', 'PASS'),
                                      ('assessment', 'M1', 'FAIL'), ('assessment', 'P1', 'UNKNOWN')]:
            body = self.report(); body['kind'] = kind
            body['checks'][0]['status'] = status
            if mission: body['mission_id'] = mission
            self.assertEqual(self.call('POST /api/web/submit', body)['statusCode'], 200)
        latest = {r['sk']: r for r in self.store.labs('test-lab')[0]['results']}
        self.assertEqual(set(latest), {'LATEST#BOOTSTRAP', 'LATEST#P1', 'LATEST#M1'})
        self.assertEqual(latest['LATEST#P1']['unknown'], 1)
        self.assertEqual(latest['LATEST#M1']['passed'], 0)
        self.assertEqual(latest['LATEST#BOOTSTRAP']['passed'], 1)

    def test_old_request_retry_does_not_replace_new_mission_result(self):
        body = self.report(); body.update(kind='assessment', mission_id='P1')
        first = self.call('POST /api/web/submit', body)
        later = self.report(); later.update(kind='assessment', mission_id='P1')
        later['checks'][0]['status'] = 'FAIL'
        self.call('POST /api/web/submit', later)
        self.assertEqual(self.call('POST /api/web/submit', body), first)
        self.assertEqual(self.store.get('LAB#test-lab', 'LATEST#P1')['passed'], 0)

    def test_jdu_email_link_is_authenticated_scoped_and_no_echo(self):
        body = dict(lab_id='test-lab', student_email='Fixture.Student@JDU.UZ')
        result = self.call('POST /api/web/link-email', body)
        self.assertEqual(result['statusCode'], 200)
        self.assertNotIn('fixture.student', result['body'])
        self.assertEqual(self.store.get('LAB#test-lab', 'META')['student_email'], 'fixture.student@jdu.uz')
        self.assertEqual(self.call('POST /api/web/link-email', body, 'wrong')['statusCode'], 401)
        for email in ('student@example.com', '<script>@jdu.uz', 'a@jdu.uz.evil', '', 'x\ny@jdu.uz'):
            body['student_email'] = email
            self.assertEqual(self.call('POST /api/web/link-email', body)['statusCode'], 400)

    def test_dashboard_languages_scope_and_hidden_infrastructure_ids(self):
        self.call('POST /api/web/submit', self.report())
        session = self.call('POST /api/web/student/session', dict(lab_id='test-lab'))
        token = parse_qs(urlsplit(json.loads(session['body'])['url']).query)['session'][0]
        for language in ('ja', 'uz', 'ru', 'not-a-language'):
            page = self.call('GET /dashboard', query=dict(session=token, lang=language))
            self.assertEqual(page['statusCode'], 200)
            self.assertIn('aria-pressed="true"', page['body'])
            self.assertNotIn(self.instances['bastion'], page['body'])
            self.assertNotIn(self.token, page['body'])
            self.assertIn('content="30"', page['body'])
        self.assertEqual(self.call('POST /api/web/admin/session', {}, token)['statusCode'], 401)

    def test_dashboard_escapes_check_labels_and_keeps_unknown_visible(self):
        lab = dict(lab_id='test-lab', release_id='web-2026-10-r1', student_email='<script>', results=[
            dict(sk='LATEST#P1', kind='assessment', mission_id='P1', passed=0, total=1, unknown=1,
                 checks=[dict(role='web', id='<img src=x>', status='UNKNOWN')])])
        page = api.render_dashboard([lab], 'teacher', 'fixture-session-token')
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;img src=x&gt;', page)
        self.assertIn('UNKNOWN', page)
        self.assertIn('0 / 1', page)


if __name__=="__main__":
    unittest.main()
