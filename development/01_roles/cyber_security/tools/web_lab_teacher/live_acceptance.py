"""Live API fixtures only. These results do not accept a five-node student lab."""
import copy
import json
import os
from pathlib import Path
import socket
import ssl
import uuid
from urllib.parse import urlsplit

import web_progress as client


def main():
    os.umask(0o077)
    root=Path.home()/".jdu-web-teacher"
    teacher=client.private_json(root/"teacher.credentials.json")
    result={"scope":"live_api_fixture_only_not_student_lab_acceptance","cases":{}}
    cases=result["cases"]
    host=urlsplit(teacher["api_base_url"]).hostname
    conn=client.PinnedHTTPSConnection(host,teacher["fixed_ingress_ipv4"])
    conn.request("GET","/healthz"); response=conn.getresponse()
    assert response.status==200 and json.loads(response.read())["service"]=="jdu-web-progress"
    conn.close(); cases["fixed_ipv4_aws_hostname_ca_verified"]=True
    other=client.PinnedHTTPSConnection("example.org",teacher["fixed_ingress_ipv4"])
    try:
        other.request("GET","/healthz")
        raise AssertionError("Unexpected SNI accepted")
    except (OSError,ssl.SSLError,socket.timeout):
        cases["other_sni_rejected"]=True
    finally:
        other.close()
    lab="api-smoke-20261015"
    credential_path=root/"private"/"api-smoke.credentials.json"
    client.issue(teacher,lab,credential_path)
    student=client.private_json(credential_path)
    state_path=root/"private"/"api-smoke-deployment.json"
    if state_path.exists():
        deployment=client.private_json(state_path)
    else:
        deployment={"lab_id":lab,"release_id":teacher["release_id"],"deployment_id":str(uuid.uuid4()),
                    "instances":{role:"i-"+format(i,"017x") for i,role in enumerate(("bastion","repo","dns","db","web"),1)}}
        client.save_private(state_path,deployment)
    client.register(student,deployment); client.register(student,deployment)
    cases["issue_and_registration_retry"]=True
    report={"schema_version":1,"kind":"bootstrap","lab_id":lab,"release_id":teacher["release_id"],
            "deployment_id":deployment["deployment_id"],"request_id":str(uuid.uuid4()),
            "checks":[{"id":"API_FIXTURE_ONLY","role":"repo","instance_id":deployment["instances"]["repo"],"status":"PASS"}]}
    receipt=client.submit(student,report)
    assert client.submit(student,report)==receipt
    cases["stored_and_idempotent_retry"]=True
    def rejects(name,config,body,status):
        try:
            client.submit(config,body)
            raise AssertionError("Expected rejection: "+name)
        except client.ProgressError as exc:
            assert "HTTP "+str(status) in str(exc),name
            cases[name]=True
    altered=copy.deepcopy(report); altered["checks"][0]["status"]="FAIL"
    rejects("same_request_changed_body_rejected",student,altered,409)
    bad=dict(student,lab_token="x"*43)
    rejects("wrong_token_rejected",bad,dict(report,request_id=str(uuid.uuid4())),401)
    rejects("different_deployment_rejected",student,dict(report,deployment_id=str(uuid.uuid4()),request_id=str(uuid.uuid4())),409)
    rejects("bootstrap_points_rejected",student,dict(report,request_id=str(uuid.uuid4()),points=25),400)
    for kind,secret,body,path in [
        ("teacher",teacher["admin_key"],{},"/api/web/admin/session"),
        ("student",student["lab_token"],{"lab_id":lab},"/api/web/student/session")]:
        session=client.request(teacher,path,body,secret,fixed=True)
        (root/"private"/(kind+".session.json")).write_text(json.dumps(session))
        conn=client.PinnedHTTPSConnection(host,teacher["fixed_ingress_ipv4"])
        conn.request("GET",urlsplit(session["url"]).path+"?"+urlsplit(session["url"]).query)
        response=conn.getresponse(); page=response.read().decode()
        assert response.status==200 and lab in page and secret not in page
        conn.close(); cases[kind+"_dashboard"]=True
    result.update(api_base_url=teacher["api_base_url"],fixed_ingress_ipv4=teacher["fixed_ingress_ipv4"],
                  fixture_lab_id=lab,fixture_instance_ids_are_synthetic=True)
    (root/"api-live-acceptance.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))


if __name__=="__main__":
    main()
