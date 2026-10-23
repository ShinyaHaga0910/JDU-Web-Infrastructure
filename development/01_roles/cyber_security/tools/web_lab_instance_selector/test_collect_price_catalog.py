import copy
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import unittest

from collect_price_catalog import parse


class OfficialPriceCatalogTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[4]
        evidence = root / '03_knowledge/aws_official/web_lab_ami_2026-10-15'
        self.fixture = json.loads((evidence / 'selected-price-rows.json').read_text(encoding='utf-8-sig'))
        self.prices = json.loads((evidence / 'teacher-price-catalog.json').read_text(encoding='utf-8-sig'))['prices']
        self.now = datetime(2026, 10, 22, 9, tzinfo=timezone.utc)

    def data(self, rows, metadata=None):
        stream = io.StringIO(newline=''); writer = csv.writer(stream)
        writer.writerows(metadata or self.fixture['csv_metadata'])
        writer.writerow(rows[0].keys())
        writer.writerows(row.values() for row in rows)
        stream.seek(0)
        return stream

    def test_previously_accepted_official_rows_reproduce_exact_catalog(self):
        metadata, rows, prices = parse(self.data(self.fixture['rows']), self.now)
        self.assertEqual(prices, self.prices)
        self.assertEqual(len(rows), len(self.fixture['rows']))

    def test_other_currency_and_dedicated_tenancy_are_not_used(self):
        rows = copy.deepcopy(self.fixture['rows'])
        for row in rows: row['Currency'] = 'EUR'; row['Tenancy'] = 'Dedicated'
        with self.assertRaises(ValueError): parse(self.data(rows), self.now)

    def test_conflicting_rates_for_same_type_stop_comparison(self):
        rows = copy.deepcopy(self.fixture['rows'])
        changed = dict(rows[0], PricePerUnit='999.0000'); rows.append(changed)
        with self.assertRaises(ValueError): parse(self.data(rows), self.now)

    def test_future_publication_or_future_terms_are_refused(self):
        metadata = copy.deepcopy(self.fixture['csv_metadata'])
        metadata[2][1] = '2027-01-01T00:00:00Z'
        with self.assertRaises(ValueError): parse(self.data(self.fixture['rows'], metadata), self.now)
        rows = copy.deepcopy(self.fixture['rows'])
        for row in rows: row['EffectiveDate'] = '2027-01-01'
        with self.assertRaises(ValueError): parse(self.data(rows), self.now)


if __name__ == '__main__': unittest.main()
