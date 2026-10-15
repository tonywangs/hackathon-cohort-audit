#!/usr/bin/env python3
"""Bounded synthetic workload measurements; measurements are never inserted in reports."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cohort_audit.core import PROJECT_FIELDS, COHORT_FIELDS, digest


def worker(projects, cohorts, out):
    from cohort_audit.__main__ import main
    start = time.perf_counter()
    code = main(['--projects', projects, '--cohorts', cohorts, '--out', out])
    if code: raise RuntimeError(f'CLI returned {code}')
    print(json.dumps(dict(elapsed_seconds=time.perf_counter()-start,
                         peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))


def generate(base, n):
    for filename, fields in [('projects.csv', PROJECT_FIELDS), ('cohorts.csv', COHORT_FIELDS)]:
        with (base/filename).open('w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, lineterminator='\n'); w.writerow(fields)
            if filename == 'cohorts.csv':
                for y in [2024, 2025]:
                    for e in ['a', 'b']:
                        w.writerow(['bounded-synthetic', e, y, ''])
            else:
                for i in range(n):
                    labels = [f'tech-{i%16}', 'Python', 'python3'] if i%5 else []
                    w.writerow([f'p{i:05}', 'a' if i%2 else 'b', 2024 if i<n//2 else 2025,
                                'SYNTHETIC bounded workload', f'https://example.invalid/p{i:05}', json.dumps(labels),
                                'unknown' if i%5 == 0 else ('partial' if i%7 == 0 else 'complete')])


def benchmark():
    root = Path(__file__).resolve().parents[1]
    result = dict(environment=dict(python=sys.version, platform=platform.platform(), machine=platform.machine(),
                                   cpu_count=os.cpu_count(), rss_units='KiB on Linux; includes Python interpreter'),
                  workload='Deterministic synthetic generator scripts/benchmark.py; 2 years × 2 event series; 17 canonical labels; no real data.',
                  runs=[])
    with tempfile.TemporaryDirectory(prefix='cohort-benchmark-') as tmp:
        base = Path(tmp)
        for n in [250, 2500, 5000]:
            input_dir = base/str(n); input_dir.mkdir(); generate(input_dir, n)
            paths = [input_dir/'projects.csv', input_dir/'cohorts.csv']
            initial_hashes = {p.name:digest(p.read_bytes()) for p in paths}
            repetitions = []
            for repeat in range(2):
                out = input_dir/f'out-{repeat}'
                start = time.perf_counter()
                process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', *map(str, paths), str(out)], cwd=root, check=True, capture_output=True, text=True, timeout=40)
                wall = time.perf_counter()-start
                sample = json.loads(process.stdout.splitlines()[-1]); sample['process_wall_seconds'] = wall
                sample['artifacts'] = {p.name:dict(bytes=p.stat().st_size, sha256=digest(p.read_bytes())) for p in sorted(out.iterdir())}
                repetitions.append(sample)
            assert repetitions[0]['artifacts'] == repetitions[1]['artifacts'], 'non-deterministic reports'
            assert initial_hashes == {p.name:digest(p.read_bytes()) for p in paths}, 'inputs changed'
            result['runs'].append(dict(project_rows=n, input_sha256=initial_hashes, repetitions=repetitions, deterministic=True, inputs_unchanged=True))
    return result


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker': worker(*sys.argv[2:])
    else:
        parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path)
        args = parser.parse_args(); result = benchmark(); text = json.dumps(result, indent=2, sort_keys=True)+'\n'
        if args.output: args.output.write_text(text)
        else: print(text, end='')
