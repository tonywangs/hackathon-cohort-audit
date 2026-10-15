import csv
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import unicodedata

from cohort_audit.core import (AuditError, Budget, COHORT_FIELDS, PROJECT_FIELDS, LIMITS,
                               analyze, digest, dumps, read_bytes)
from cohort_audit.report import render


def csv_bytes(fields, rows):
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(fields); writer.writerows(rows)
    return out.getvalue().encode('utf-8')


def project(pid='p', event='e', year=2024, labels=None, status='complete', title='Example'):
    return [pid, event, year, title, 'https://example.invalid/' + pid, json.dumps(labels or [], ensure_ascii=False), status]


def run(rows=None, cohorts=None, budget=None):
    return analyze(csv_bytes(PROJECT_FIELDS, rows if rows is not None else [project(labels=['Python'])]),
                   csv_bytes(COHORT_FIELDS, cohorts if cohorts is not None else [['c', 'e', 2024, '']]), budget)


# Independent reference: deliberately simple repeated scans over raw rows.
# Does not use production normalization, grouping, counting, or comparison helpers.
def oracle(raw_rows, event_years, technology):
    selected = [r for r in raw_rows if (r[1], int(r[2])) in event_years]
    ids = sorted(set(r[0] for r in selected))
    mentioned = completed = complete_mentions = unknown = unresolved = 0
    aliases = {'python3': 'python', 'python 3': 'python', 'js': 'javascript', 'reactjs': 'react', 'react.js': 'react'}
    for pid in ids:
        subset = [r for r in selected if r[0] == pid]
        labels = []
        for row in subset:
            for label in json.loads(row[5]):
                key = unicodedata.normalize('NFC', label).strip().casefold()
                labels.append(aliases.get(key, key))
        present = technology in labels
        complete = all(r[6] == 'complete' for r in subset)
        all_unknown = all(r[6] == 'unknown' for r in subset)
        mentioned += present; completed += complete; complete_mentions += present and complete
        unknown += all_unknown; unresolved += not complete and not present
    return dict(projects=len(ids), complete=completed, unknown=unknown, partial=len(ids)-completed-unknown,
                mentions=mentioned, complete_mentions=complete_mentions,
                proportion=mentioned/len(ids) if ids else None,
                complete_proportion=complete_mentions/completed if completed else None,
                possible_upper=(mentioned+unresolved)/len(ids) if ids else None)


class SeededOracleTests(unittest.TestCase):
    def assert_summary(self, actual, rows, events, techs):
        for tech in techs:
            expected = oracle(rows, events, tech)
            for key in ['projects', 'complete', 'partial', 'unknown']:
                self.assertEqual(actual[key], expected[key])
            for key in ['mentions', 'complete_mentions', 'proportion', 'complete_proportion', 'possible_upper']:
                self.assertEqual(actual['technologies'][tech][key], expected[key])

    def test_300_seeded_datasets(self):
        for seed in range(300):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                rows, cohorts = [], []
                for year in [2024, 2025]:
                    for event in ['a', 'b', 'c']:
                        cohorts.append(['all', event, year, ''])
                        if event == 'a':
                            cohorts.append(['single', event, year, ''])
                        for i in range(rng.randrange(0, 12)):
                            status = rng.choice(['complete', 'partial', 'unknown'])
                            labels = [] if status == 'unknown' else rng.choices(['Python', 'python3', 'JS', 'javascript', 'café', 'cafe\u0301', '工具', 'reactjs', 'react.js', 'new!'], k=rng.randrange(5))
                            row = project(f'p{i}', event, year, labels, status)
                            rows.append(row)
                            if rng.random() < .3:
                                rows.append(row.copy())
                cohorts.append(['empty', 'empty', 2025, 0])
                p, c = csv_bytes(PROJECT_FIELDS, rows), csv_bytes(COHORT_FIELDS, cohorts)
                hashes = digest(p), digest(c)
                result = analyze(p, c)
                techs = result['technologies']
                for group in result['groups']:
                    events = {(m[1], int(m[2])) for m in cohorts if m[0] == group['cohort_id'] and int(m[2]) == group['year']}
                    self.assert_summary(group['summary'], rows, events, techs)
                    for event in group['events']:
                        self.assert_summary(event['summary'], rows, {(event['event_id'], group['year'])}, techs)
                for comp in result['comparisons']:
                    b, a = result['groups'][comp['before']], result['groups'][comp['after']]
                    b_events = {m[1] for m in cohorts if m[0] == b['cohort_id'] and int(m[2]) == b['year']}
                    a_events = {m[1] for m in cohorts if m[0] == a['cohort_id'] and int(m[2]) == a['year']}
                    common = b_events & a_events
                    self.assertEqual(comp['common_events'], sorted(common))
                    self.assert_summary(comp['before_common'], rows, {(e, b['year']) for e in common}, techs)
                    self.assert_summary(comp['after_common'], rows, {(e, a['year']) for e in common}, techs)
                    for t in techs:
                        br = oracle(rows, {(e, b['year']) for e in b_events}, t)['proportion']
                        ar = oracle(rows, {(e, a['year']) for e in a_events}, t)['proportion']
                        bc = oracle(rows, {(e, b['year']) for e in common}, t)['proportion']
                        ac = oracle(rows, {(e, a['year']) for e in common}, t)['proportion']
                        expected_delta = ar-br if ar is not None and br is not None else None
                        expected_common = ac-bc if ac is not None and bc is not None else None
                        deltas = []
                        for e in sorted(common):
                            eb = oracle(rows, {(e, b['year'])}, t)['proportion']
                            ea = oracle(rows, {(e, a['year'])}, t)['proportion']
                            if ea is not None and eb is not None:
                                deltas.append(ea-eb)
                        entry = comp['technologies'][t]
                        self.assertEqual(entry['delta'], expected_delta)
                        self.assertEqual(entry['common_delta'], expected_common)
                        self.assertEqual(entry['equal_event_delta'], sum(deltas)/len(deltas) if deltas else None)
                        self.assertEqual(entry['reversal'], bool(expected_delta is not None and deltas and ((expected_delta < 0 and all(d > 0 for d in deltas)) or (expected_delta > 0 and all(d < 0 for d in deltas)))))
                self.assertEqual(dumps(result), dumps(analyze(p, c)))
                self.assertEqual(hashes, (digest(p), digest(c)))

    def test_synthetic_reversal_and_missingness(self):
        root = Path(__file__).resolve().parents[1]
        d = analyze((root/'examples/projects.csv').read_bytes(), (root/'examples/cohorts.csv').read_bytes())
        b, a = [g for g in d['groups'] if g['cohort_id'] == 'synthetic-reversal']
        self.assertEqual(b['summary']['technologies']['python']['proportion'], .74)
        self.assertEqual(a['summary']['technologies']['python']['proportion'], .36)
        c = next(c for c in d['comparisons'] if c['before'] == b['group_id'] and c['after'] == a['group_id'])
        self.assertTrue(c['technologies']['python']['reversal'])
        self.assertAlmostEqual(c['technologies']['python']['equal_event_delta'], .1)
        coverage = next(g for g in d['groups'] if g['cohort_id'] == 'synthetic-coverage')
        self.assertEqual(coverage['summary']['projects'], 3)
        self.assertEqual(coverage['cross_event_excess'], 1)
        self.assertEqual(coverage['summary']['unknown'], 1)
        self.assertEqual(coverage['summary']['technologies']['javascript']['possible_upper'], 2/3)
        self.assertEqual(d['diagnostics']['duplicate_rows_collapsed'], 1)


class ValidationTests(unittest.TestCase):
    def test_invalid_fields(self):
        cases = [(0, ''), (0, ' p'), (0, 'é'), (1, 'unlisted'), (2, '02024'), (2, 'nan'), (3, ''),
                 (3, 'x\x00'), (3, 'x'*1001), (4, 'javascript:alert(1)'), (4, 'https://x@host/a'),
                 (4, 'https://host:bad/a'), (4, 'https://host\\evil/a'), (4, 'https://host/ space'),
                 (5, '{}'), (5, 'null'), (5, '[3]'), (5, '[["x"]]'), (5, '[""]'),
                 (5, '[" "]'), (5, json.dumps(['x'*101])), (5, json.dumps(['x']*33)), (6, 'yes')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                row = project(); row[field] = value
                with self.assertRaises(AuditError): run([row])
        with self.assertRaises(AuditError): run([project(labels=['python'], status='unknown')])

    def test_ambiguous_duplicates(self):
        with self.assertRaisesRegex(AuditError, 'conflicting duplicate'):
            run([project(labels=['JS']), project(labels=['javascript'])])
        row = project(); row[4] += '/other'
        with self.assertRaisesRegex(AuditError, 'ambiguous'):
            run([project(), row])
        row = project('p2'); row[4] = project()[4]
        with self.assertRaisesRegex(AuditError, 'ambiguous'):
            run([project(), row])

    def test_cohort_validation(self):
        cases = [[], [['c', 'e', 2024, ''], ['c', 'e', 2024, '']],
                 [['c', 'e', 2024, 0]], [['c', 'e', 2024, '-1']], [['c', 'e', 2024, '01']],
                 [['c', 'e', 2024, ''], ['d', 'e', 2024, 3]]]
        for cohorts in cases:
            with self.subTest(cohorts=cohorts):
                with self.assertRaises(AuditError): run(cohorts=cohorts)

    def test_invalid_csv_and_encoding(self):
        c = csv_bytes(COHORT_FIELDS, [['c', 'e', 2024, '']])
        header = csv_bytes(PROJECT_FIELDS, [])
        for raw in [b'', b'wrong\n', b'\xff', header + b'"unterminated', header + b'a,b\n', header + b'x'*8001]:
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(AuditError): analyze(raw, c)
        # BOM and CRLF are accepted, but fingerprints cover the exact input bytes.
        raw = b'\xef\xbb\xbf' + csv_bytes(PROJECT_FIELDS, [project()]).replace(b'\n', b'\r\n')
        self.assertEqual(analyze(raw, c)['provenance']['projects_sha256'], digest(raw))

    def test_limits(self):
        with self.assertRaisesRegex(AuditError, 'byte limit'):
            analyze(b'x'*(LIMITS['input_bytes']+1), csv_bytes(COHORT_FIELDS, [['c', 'e', 2024, '']]))
        for limit, value, rows, cohorts, message in [
            ('project_rows', 1, [project(), project('p2')], None, 'record limit'),
            ('cohort_rows', 1, [], [['c', 'e', 2024, ''], ['c', 'f', 2024, '']], 'record limit'),
            ('groups', 1, [], [['c', 'e', 2024, ''], ['d', 'e', 2024, '']], 'group limit'),
            ('technologies', 1, [project(labels=['a', 'b'])], None, 'technology limit'),
            ('operations', 0, None, None, 'computation limit')]:
            with self.subTest(limit=limit), patch.dict(LIMITS, {limit:value}):
                with self.assertRaisesRegex(AuditError, message): run(rows, cohorts)
        with self.assertRaisesRegex(AuditError, 'runtime limit'): run(budget=Budget(-1))
        result = run()
        for limit in ['json_bytes', 'html_bytes']:
            with patch.dict(LIMITS, {limit:10}):
                with self.assertRaisesRegex(AuditError, 'report byte limit'): render(result)

    def test_file_limits_and_types(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)/'large'; p.write_bytes(b'0123456789')
            with patch.dict(LIMITS, input_bytes=9):
                with self.assertRaisesRegex(AuditError, 'byte limit'): read_bytes(p, Budget())
            with self.assertRaisesRegex(AuditError, 'regular file'): read_bytes(t, Budget())

    def test_no_technologies_and_empty_group(self):
        d = run([], [['empty', 'e', 2024, 0]])
        self.assertEqual(d['groups'][0]['summary']['projects'], 0)
        self.assertEqual(d['technologies'], [])
        self.assertIsNone(d['groups'][0]['events'][0]['coverage'])
        render(d)

    def test_hostile_text_is_inert(self):
        bad = '</script><script>window.pwned=1</script>'
        result = run([project(labels=[bad], title=bad)])
        raw, html = render(result)
        self.assertIn(bad, raw.decode())
        self.assertNotIn(bad, html.decode())
        self.assertIn('\\u003c/script', html.decode())
        self.assertEqual(render(result), (raw, html))
        with self.assertRaises(ValueError): dumps({'bad':float('nan')})


if __name__ == '__main__': unittest.main()
