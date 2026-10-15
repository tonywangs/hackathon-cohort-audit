#!/usr/bin/env python3
"""Dependency-free offline installation into a new prefix (Linux, Python 3.10+)."""
import argparse
from pathlib import Path
import shutil
import tempfile
import zipapp


def install(prefix):
    root = Path(__file__).resolve().parents[1]
    executable = prefix / 'bin' / 'cohort-audit'
    executable.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cohort-build-') as tmp:
        package = Path(tmp) / 'cohort_audit'
        package.mkdir()
        for path in (root / 'cohort_audit').iterdir():
            if path.suffix in ('.py', '.json', '.html', '.css', '.js'):
                shutil.copyfile(path, package / path.name)
        archive = Path(tmp) / 'cohort-audit.pyz'
        # Keep output outside the source tree to avoid including itself.
        stage = Path(tmp) / 'app'
        stage.mkdir()
        shutil.move(str(package), stage)
        zipapp.create_archive(stage, archive, interpreter='/usr/bin/env python3', main='cohort_audit.__main__:entry', compressed=True)
        # Exclusive file creation, including dangling symlink collisions.
        with executable.open('xb') as out:
            out.write(archive.read_bytes())
        executable.chmod(0o755)
    print(executable)
    return executable


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', required=True, type=Path)
    install(parser.parse_args().prefix)
