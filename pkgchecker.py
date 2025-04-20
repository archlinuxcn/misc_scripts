from __future__ import annotations

import contextlib
from functools import partial
import itertools
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from typing import Optional, Generator, Iterator

import zstandard

logger = logging.getLogger(__name__)

@contextlib.contextmanager
def tarfile_open_zstd_compat(name: str) -> Generator[tarfile.TarFile, None, None]:
  if name.endswith('.zst'):
    dctx = zstandard.ZstdDecompressor()
    with open(name, 'rb') as f, dctx.stream_reader(f) as reader, tarfile.open(mode='r|', fileobj=reader) as tar:
      yield tar
  else:
    with tarfile.open(name) as tar:
      yield tar

def get_buildinfo(pkg: os.PathLike) -> Optional[str]:
  with tarfile_open_zstd_compat(str(pkg)) as tar:
    threshold = 10
    for tarinfo in itertools.islice(tar, threshold):
      if tarinfo.name == '.BUILDINFO':
        f = tar.extractfile(tarinfo)
        assert f is not None
        return f.read().decode()

  logger.warning('Cannot find .BUILDINFO in first %d entries of %s; checking anyway', threshold, pkg)
  return None

def iter_installed(buildinfo: str) -> Iterator[str]:
  for line in buildinfo.split('\n'):
    if line.startswith('installed = '):
      parts = line[len('installed = '):].rsplit('-', maxsplit=3)
      yield parts

@contextlib.contextmanager
def extract_package(pkg: os.PathLike) -> Generator[str, None, None]:
  logger.info('extracting %s...', pkg)
  d = tempfile.mkdtemp(prefix='depcheck-')
  try:
    subprocess.check_call(['bsdtar', 'xf', pkg, '--no-fflags', '-C', d])
    yield d
  finally:
    shutil.rmtree(d, onerror=partial(handle_rmtree_error, d))

def handle_rmtree_error(tmpdir, func, path, excinfo):
  if isinstance(excinfo[1], PermissionError) and \
     os.path.commonpath((path, tmpdir)) == tmpdir:
    os.chmod(os.path.dirname(path), 0o700)
    if os.path.isdir(path):
      shutil.rmtree(path, onerror=partial(handle_rmtree_error, path))
    else:
      os.unlink(path)

