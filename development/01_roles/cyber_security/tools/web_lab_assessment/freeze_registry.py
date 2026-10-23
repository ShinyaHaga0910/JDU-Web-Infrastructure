"""Freeze the approved design and the exact teacher application into a new candidate."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def application_bundle():
    app = ROOT.parent / 'web_lab_catalog'
    spec = importlib.util.spec_from_file_location('catalog_bundle_builder', app / 'build_bundle.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.bundle(app)


def freeze():
    source = ROOT.parents[1] / 'system_requirements/2026-10_web_infrastructure_d11_assessment_contract.json'
    c = json.loads(source.read_text())
    keep = ('check_definitions', 'profiles', 'tasks', 'recommended_order', 'raw_points_max', 'raw_points_by_mission')
    frozen = {k: c[k] for k in keep}
    app, manifest = application_bundle()
    frozen.update(schema_version=1, contract_id='web-d11-2026-10-r1', source_contract_id=c['contract_id'],
                  user_approved_date='2026-10-22', application_manifest=manifest,
                  application_archive_sha256=hashlib.sha256(app).hexdigest())
    raw = (json.dumps(frozen, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    (ROOT / 'assessment-registry.json').write_bytes(raw)
    print('D11_REGISTRY_SHA256=' + hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    freeze()
