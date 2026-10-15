import contextlib
import io
import json
import os
from pathlib import Path
import signal
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cohort_audit import __main__ as cli
from cohort_audit.core import AuditError, Budget, digest
from tests.test_core import run

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.out = self.base / 'report'

    def args(self):
        return ['--projects', str(ROOT/'examples/projects.csv'), '--cohorts', str(ROOT/'examples/cohorts.csv'), '--out', str(self.out)]

    def test_end_to_end_and_repeated_hashes(self):
        inputs = [ROOT/'examples/projects.csv', ROOT/'examples/cohorts.csv']
        before = [digest(p.read_bytes()) for p in inputs]
        subprocess.run([sys.executable, '-m', 'cohort_audit', *self.args()], check=True, capture_output=True)
        first = {p.name:p.read_bytes() for p in self.out.iterdir()}
        self.out = self.base/'second'
        subprocess.run([sys.executable, '-m', 'cohort_audit', *self.args()], check=True, capture_output=True)
        self.assertEqual(first, {p.name:p.read_bytes() for p in self.out.iterdir()})
        manifest = json.loads(first['complete.json'])
        for name, info in manifest['files'].items():
            self.assertEqual(digest(first[name]), info['sha256'])
            self.assertEqual(len(first[name]), info['bytes'])
        self.assertEqual(before, [digest(p.read_bytes()) for p in inputs])

    def test_existing_output_and_symlink(self):
        self.out.mkdir()
        with self.assertRaises(AuditError): cli.write_bundle(run(), self.out, Budget())
        self.out.rmdir(); self.out.symlink_to(self.base/'missing')
        with self.assertRaises(AuditError): cli.write_bundle(run(), self.out, Budget())
        self.assertTrue(self.out.is_symlink())

    def test_serialization_write_and_publication_failures_clean_up(self):
        for target in ['render', 'os.fsync', 'publish_directory']:
            with self.subTest(target=target):
                with patch('cohort_audit.__main__.'+target, side_effect=OSError('injected failure')):
                    with self.assertRaises(OSError): cli.write_bundle(run(), self.out, Budget())
                self.assertEqual(list(self.base.iterdir()), [])
        with patch('cohort_audit.report.dumps', side_effect=ValueError('serialize failed')):
            with self.assertRaises(ValueError): cli.write_bundle(run(), self.out, Budget())
        self.assertEqual(list(self.base.iterdir()), [])

    def test_cancelled_write_cleans_up(self):
        for signum in [signal.SIGINT, signal.SIGTERM]:
            with self.subTest(signal=signum):
                with patch('cohort_audit.__main__.os.fsync', side_effect=lambda fd: signal.raise_signal(signum)):
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(cli.main(self.args()), 130)
                self.assertEqual(list(self.base.iterdir()), [])

    def test_external_process_cancellation(self):
        guard = self.base/'signal-guard'; guard.mkdir()
        (guard/'sitecustomize.py').write_text(
            'import os, time\noriginal = os.fsync\n'
            'def pause(fd):\n print("WRITE_READY", flush=True)\n time.sleep(10)\n original(fd)\n'
            'os.fsync = pause\n')
        env = {**os.environ, 'PYTHONPATH':str(guard)}
        child = subprocess.Popen([sys.executable, '-m', 'cohort_audit', *self.args()],
                                 cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 5)[0], 'child did not reach write stage')
            self.assertEqual(child.stdout.readline().strip(), 'WRITE_READY')
            child.send_signal(signal.SIGTERM)
            stdout, stderr = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 130, stderr)
            self.assertFalse(self.out.exists())
            self.assertEqual(list(self.base.glob('.cohort-audit-*')), [])
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_timeout_during_write_cleans_up(self):
        with patch('cohort_audit.__main__.os.fsync', side_effect=lambda fd: signal.raise_signal(signal.SIGALRM)):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(self.args()), 2)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_publication_race_does_not_replace_competitor(self):
        original = cli.publish_directory
        def compete(source, dest):
            dest.mkdir()
            (dest/'owner').write_text('another writer')
            original(source, dest)
        with patch('cohort_audit.__main__.publish_directory', side_effect=compete):
            with self.assertRaisesRegex(AuditError, 'already exists'): cli.write_bundle(run(), self.out, Budget())
        self.assertEqual((self.out/'owner').read_text(), 'another writer')
        self.assertEqual(list(self.base.iterdir()), [self.out])

    def test_empty_directory_race(self):
        stage = self.base/'stage'; stage.mkdir(); self.out.mkdir()
        with self.assertRaisesRegex(AuditError, 'already exists'): cli.publish_directory(stage, self.out)
        self.assertTrue(stage.exists()); self.assertTrue(self.out.exists())

    def test_short_timeout_and_invalid_budget(self):
        for budget in ['0.000000001', '0', '31', 'nan', 'inf']:
            p = subprocess.run([sys.executable, '-m', 'cohort_audit', *self.args(), '--max-seconds', budget], capture_output=True)
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertFalse(self.out.exists())

    def test_installed_zipapp_offline(self):
        prefix = self.base/'isolated'
        subprocess.run([sys.executable, str(ROOT/'scripts/install.py'), '--prefix', str(prefix)], check=True, capture_output=True)
        exe = prefix/'bin/cohort-audit'
        # Isolated cwd plus an audit hook blocks socket use in the installed app.
        guard = self.base/'guard'; guard.mkdir()
        (guard/'sitecustomize.py').write_text('import sys\ndef guard(event, args):\n if event.startswith("socket."): raise RuntimeError("network disabled")\nsys.addaudithook(guard)\n')
        env = {**os.environ, 'PYTHONPATH':str(guard), 'PYTHONNOUSERSITE':'1'}
        p = subprocess.run([str(exe), *self.args()], cwd=self.base, env=env, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        collision = subprocess.run([str(exe), *self.args()], cwd=self.base, env=env, capture_output=True)
        self.assertEqual(collision.returncode, 2)
        self.assertEqual(json.loads((self.out/'complete.json').read_text())['status'], 'complete')
        self.assertEqual(json.loads((self.out/'report.json').read_text())['diagnostics']['input_project_rows'], 205)


if __name__ == '__main__': unittest.main()
