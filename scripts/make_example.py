#!/usr/bin/env python3
"""Generate original synthetic fixtures; never represents real hackathon projects."""
import csv
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cohort_audit.core import PROJECT_FIELDS, COHORT_FIELDS


def generate(directory):
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    # Both event series improve, but the high-mention series loses sample weight.
    for year, specs in [(2024, [('high', 90, 72), ('low', 10, 2)]),
                        (2025, [('high', 10, 9), ('low', 90, 27)])]:
        for event, total, mentions in specs:
            for i in range(total):
                pid = f'synthetic-{year}-{event}-{i:03d}'
                rows.append([pid, event, year, 'SYNTHETIC project ' + pid,
                             'https://example.invalid/projects/' + pid,
                             json.dumps(['Python', 'python3', 'Python'] if i < mentions else []), 'complete'])
    # Separate coverage cohort demonstrates incomplete annotations, duplicates,
    # stable identities across events, empty cohorts, and literal hostile text.
    hostile = '</script><img src="https://example.invalid/beacon" onerror="window.pwned=1">'
    rows.extend([
        ['shared', 'coverage-a', 2025, 'SYNTHETIC ' + hostile, 'https://example.invalid/projects/shared', json.dumps(['JS', hostile, 'café', 'cafe\u0301']), 'partial'],
        ['shared', 'coverage-b', 2025, 'SYNTHETIC shared project', 'https://example.invalid/projects/shared', '["javascript"]', 'complete'],
        ['unannotated', 'coverage-a', 2025, 'SYNTHETIC unknown annotations', 'https://example.invalid/projects/unannotated', '[]', 'unknown'],
        ['negative', 'coverage-a', 2025, 'SYNTHETIC explicitly empty labels', 'https://example.invalid/projects/negative', '[]', 'complete'],
    ])
    rows.append(rows[-1].copy())
    cohorts = [['synthetic-reversal', e, y, n] for y, specs in [(2024, [('high', 90), ('low', 10)]), (2025, [('high', 10), ('low', 90)])] for e, n in specs]
    cohorts.extend([['synthetic-coverage', 'coverage-a', 2025, 10], ['synthetic-coverage', 'coverage-b', 2025, ''], ['synthetic-empty', 'empty', 2025, 0]])
    for filename, fields, data in [('projects.csv', PROJECT_FIELDS, rows), ('cohorts.csv', COHORT_FIELDS, cohorts)]:
        with (directory / filename).open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, lineterminator='\n'); writer.writerow(fields); writer.writerows(data)
    manifest = dict(kind='synthetic', generator='scripts/make_example.py', seed=None,
                    license='CC0-1.0 (synthetic CSV fixtures only)',
                    selection='All generated rows; no real people, projects, or events.',
                    expected=dict(python_before=0.74, python_after=0.36, aggregate_delta=-0.38,
                                  high_delta=0.1, low_delta=0.1, equal_event_delta=0.1),
                    files={n: hashlib.sha256((directory / n).read_bytes()).hexdigest() for n in ['projects.csv', 'cohorts.csv']})
    (directory / 'provenance.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    generate(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'examples')
