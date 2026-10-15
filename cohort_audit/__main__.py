"""Command-line entry point, bounded runtime and exclusive atomic publication."""
import argparse
import ctypes
import errno
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
from . import __version__
from .core import AuditError, Budget, LIMITS, analyze, digest, dumps, read_bytes
from .report import render


def publish_directory(source, destination):
    """Linux renameat2(RENAME_NOREPLACE): never replace even an empty directory."""
    if not sys.platform.startswith('linux'):
        raise AuditError('atomic directory output currently requires Linux')
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError as exc:
        raise AuditError('renameat2 is required for exclusive atomic output') from exc
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            raise AuditError('output already exists; choose a new directory')
        raise OSError(error, os.strerror(error))


def write_bundle(result, destination, budget):
    destination = Path(destination).absolute()
    if os.path.lexists(destination):
        raise AuditError('output already exists; choose a new directory')
    if not destination.parent.is_dir():
        raise AuditError('output parent directory must already exist')
    raw, html = render(result)
    budget.check()
    temp = Path(tempfile.mkdtemp(prefix='.cohort-audit-', dir=destination.parent))
    try:
        artifacts = {'report.json': raw, 'report.html': html}
        for name, content in artifacts.items():
            with (temp / name).open('xb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            budget.check()
        manifest = dict(status='complete', schema_version='1.0',
                        files={name: dict(bytes=len(raw), sha256=digest(raw)) for name, raw in artifacts.items()})
        with (temp / 'complete.json').open('x', encoding='utf-8') as stream:
            stream.write(dumps(manifest))
            stream.flush()
            os.fsync(stream.fileno())
        budget.check()
        publish_directory(temp, destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def parser():
    p = argparse.ArgumentParser(description='Offline project-level technology mention audit. Output must not exist.')
    p.add_argument('--version', action='version', version=__version__)
    p.add_argument('--projects', required=True, type=Path)
    p.add_argument('--cohorts', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--max-seconds', type=float, default=LIMITS['runtime_seconds'], help='runtime budget >0 and <=30 seconds')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if not 0 < args.max_seconds <= LIMITS['runtime_seconds']:
        print('error: --max-seconds must be >0 and <=30', file=sys.stderr)
        return 2
    if not sys.platform.startswith('linux'):
        print('error: this CLI requires Linux for exclusive atomic directory output', file=sys.stderr)
        return 2
    budget = Budget(args.max_seconds)
    def timed_out(signum, frame):
        raise AuditError('runtime limit exceeded')
    def cancelled(signum, frame):
        raise KeyboardInterrupt()
    saved = {s: signal.getsignal(s) for s in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM)}
    signal.signal(signal.SIGALRM, timed_out)
    signal.signal(signal.SIGINT, cancelled)
    signal.signal(signal.SIGTERM, cancelled)
    try:
        signal.setitimer(signal.ITIMER_REAL, args.max_seconds)
        if os.path.lexists(args.out):
            raise AuditError('output already exists; choose a new directory')
        project_raw, cohort_raw = read_bytes(args.projects, budget), read_bytes(args.cohorts, budget)
        result = analyze(project_raw, cohort_raw, budget)
        write_bundle(result, args.out, budget)
        print(f'Complete: {args.out / "report.html"}')
        return 0
    except KeyboardInterrupt:
        print('cancelled: no partial report published', file=sys.stderr)
        return 130
    except (AuditError, OSError, ValueError, TypeError, RecursionError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for s, handler in saved.items():
            signal.signal(s, handler)


def entry():
    sys.exit(main())


if __name__ == '__main__':
    entry()
