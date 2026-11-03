from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from renew_release import deadline
from release_tools import compatible_core


class RenewalTests(unittest.TestCase):
    def test_end_of_january_means_start_of_february_exclusive_uzt(self):
        now=datetime(2026,11,3,tzinfo=timezone.utc)
        self.assertEqual(deadline('2027-02-01T00:00:00+05:00',now),
                         datetime(2027,1,31,19,tzinfo=timezone.utc))

    def test_no_unbounded_naive_expired_or_future_year_validity(self):
        now=datetime(2026,11,3,tzinfo=timezone.utc)
        for value in ('2027-01-31','2026-11-02T00:00:00+00:00',
                      (now+timedelta(days=121)).isoformat()):
            with self.subTest(value=value),self.assertRaises((ValueError,TypeError)):
                deadline(value,now)

    def test_retained_state_needs_the_signed_same_runtime_declaration(self):
        with tempfile.TemporaryDirectory() as folder:
            context={'root':Path(folder),'release':{
                'core_manifest_sha256':'b'*64,'assessment_archive_sha256':'c'*64}}
            self.assertTrue(compatible_core(context,'b'*64))
            self.assertFalse(compatible_core(context,'a'*64))
            row={'scope':'same_runtime_validity_renewal','original_core_manifest_sha256':'a'*64,
                 'renewed_core_manifest_sha256':'b'*64,'runtime_artifacts_unchanged':True,
                 'assessment_archive_sha256':'c'*64}
            path=Path(folder)/'RENEWAL.json';path.write_text(json.dumps(row),encoding='utf-8')
            self.assertTrue(compatible_core(context,'a'*64))
            for key,value in [('scope','arbitrary'),('renewed_core_manifest_sha256','d'*64),
                              ('runtime_artifacts_unchanged',False),('assessment_archive_sha256','e'*64)]:
                path.write_text(json.dumps({**row,key:value}),encoding='utf-8')
                self.assertFalse(compatible_core(context,'a'*64))


if __name__=='__main__':unittest.main()
