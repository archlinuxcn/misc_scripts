from __future__ import annotations

import asyncio
from typing import List
import pathlib

from lilac2.lilacyaml import (
  iter_pkgdir, load_lilac_yaml,
)

from .config import REPODIR
from .util import Dependent, Maintainer

async def find_maintainers(
  pkgbase: str,
) -> List[Maintainer]:
  loop = asyncio.get_running_loop()
  return await loop.run_in_executor(
    None, find_maintainers_sync, pkgbase)

def find_maintainers_sync(
  pkgbase: str,
) -> List[Maintainer]:
  ly = load_lilac_yaml(REPODIR / pkgbase)
  return [
    x['github'] for x in
    ly.get('maintainers', ())
    if 'github' in x
  ]

async def find_dependent_packages(
  pkgbase: str,
) -> List[str]:
  loop = asyncio.get_running_loop()
  dependents = await loop.run_in_executor(
    None, find_dependent_packages_ext, REPODIR, pkgbase)
  return [x.pkgbase for x in dependents]

async def find_dependent_packages_ext_async(
  pkgbase: str,
) -> List[Dependent]:
  loop = asyncio.get_running_loop()
  dependents = await loop.run_in_executor(
    None, find_dependent_packages_ext, REPODIR, pkgbase)
  return dependents

def find_dependent_packages_ext(
  repo: pathlib.Path,
  target: str,
) -> List[Dependent]:
  ret = []
  for x in iter_pkgdir(repo):
    ly = load_lilac_yaml(x)
    for d, _ in ly.get('repo_depends', ()):
      if d == target:
        maints = [x['github'] for x in
                  ly.get('maintainers', ())
                  if 'github' in x]
        ret.append(Dependent(x.name, maints))
  return ret

