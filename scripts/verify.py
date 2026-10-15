#!/usr/bin/env python3
"""One offline verification command. Requires a locally cached Playwright + Chromium."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.make_example import generate
from scripts.benchmark import benchmark
from cohort_audit.__main__ import write_bundle
from cohort_audit.core import Budget, analyze, COHORT_FIELDS, PROJECT_FIELDS
from tests.test_core import csv_bytes


def publication_check():
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    paths = sorted({ROOT/n for n in names if n})
    assert len(paths) <= 1000, 'publication file count exceeded'
    total = 0
    for path in paths:
        assert path.is_file() and not path.is_symlink(), f'nonregular publication file: {path}'
        assert path.stat().st_size <= 10*1024*1024, f'oversized file: {path}'
        assert path.suffix != '.log' or path == ROOT/'results/tests.log', f'log not publishable: {path}'
        total += path.stat().st_size
    assert total <= 32*1024*1024, 'publication tree too large'
    return dict(files=len(paths), bytes=total)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--playwright-module', help='absolute path to installed playwright module; otherwise Node resolution is used')
    p.add_argument('--browser-path', help='cached Playwright browsers directory')
    p.add_argument('--record', action='store_true', help='save plain tests.log and measured benchmark/browser JSON under results/')
    args = p.parse_args()
    env = dict(os.environ)
    if args.playwright_module: env['PLAYWRIGHT_MODULE'] = str(Path(args.playwright_module).resolve())
    if args.browser_path: env['PLAYWRIGHT_BROWSERS_PATH'] = str(Path(args.browser_path).resolve())
    log = []
    def command(argv, timeout=120):
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
        output = result.stdout + result.stderr
        print(output, end='', flush=True); log.append(output)
        if result.returncode: raise RuntimeError(f'verification command failed: {argv[0]} (exit {result.returncode})')
        return result.stdout
    try:
        command([sys.executable, '-m', 'unittest', 'discover', '-v'])
        with tempfile.TemporaryDirectory(prefix='cohort-verify-') as tmp:
            base = Path(tmp)
            generate(base/'examples')
            for name in ['projects.csv', 'cohorts.csv', 'provenance.json']:
                assert (base/'examples'/name).read_bytes() == (ROOT/'examples'/name).read_bytes(), f'synthetic fixture drift: {name}'
            result = analyze((base/'examples/projects.csv').read_bytes(), (base/'examples/cohorts.csv').read_bytes())
            write_bundle(result, base/'report', Budget())
            empty = analyze(csv_bytes(PROJECT_FIELDS, []), csv_bytes(COHORT_FIELDS, [['empty', 'e', 2025, 0]]))
            write_bundle(empty, base/'empty', Budget())
            browser = json.loads(command(['node', str(ROOT/'scripts/browser_test.cjs'), str(base/'report/report.html'), '', str(base/'empty/report.html')]).splitlines()[-1])
        measured = benchmark()
        publication = publication_check()
        if args.record:
            (ROOT/'results').mkdir(exist_ok=True)
            (ROOT/'results/benchmark.json').write_text(json.dumps(measured, indent=2, sort_keys=True)+'\n')
            (ROOT/'results/browser.json').write_text(json.dumps(browser, indent=2, sort_keys=True)+'\n')
        message = f'PASS: unit/oracle tests, regenerated fixtures, Chromium offline interaction, installed CLI, repeated workload hashes, unchanged inputs. Publication candidate: {publication["files"]} files, {publication["bytes"]} bytes.\n'
        print(message, end=''); log.append(message)
    finally:
        if args.record:
            (ROOT/'results').mkdir(exist_ok=True)
            (ROOT/'results/tests.log').write_text(''.join(log))


if __name__ == '__main__': main()
