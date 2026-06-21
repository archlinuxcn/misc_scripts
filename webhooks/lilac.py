from __future__ import annotations

import asyncio

from lilac2.lilacyaml import (
  iter_pkgdir, load_lilac_yaml,
)

from .config import REPOSDIR
from .util import Dependent, Maintainer, split_repo_pkgbase

async def find_maintainers(
  pkgbase: str,
) -> list[Maintainer]:
  loop = asyncio.get_running_loop()
  return await loop.run_in_executor(
    None, find_maintainers_sync, pkgbase)

def find_maintainers_sync(
  pkg: str,
) -> list[Maintainer]:
  repo, pkgbase = split_repo_pkgbase(pkg)
  ly = load_lilac_yaml(REPOSDIR / repo / pkgbase)
  return [
    x['github'] for x in
    ly.get('maintainers', ())
    if 'github' in x
  ]

async def find_dependent_packages(
  pkgbase: str,
) -> list[str]:
  loop = asyncio.get_running_loop()
  dependents = await loop.run_in_executor(
    None, find_dependent_packages_ext, pkgbase)
  return [x.pkgbase for x in dependents]

async def find_dependent_packages_ext_async(
  pkgbase: str,
) -> list[Dependent]:
  loop = asyncio.get_running_loop()
  dependents = await loop.run_in_executor(
    None, find_dependent_packages_ext, pkgbase)
  return dependents

def find_dependent_packages_ext(
  target: str,
) -> list[Dependent]:
  ret = []
  repo, pkgbase = split_repo_pkgbase(target)
  for x in iter_pkgdir(REPOSDIR / repo):
    try:
      ly = load_lilac_yaml(x)
    except Exception:
      # ignore wrong packages
      continue
    for d, _ in ly.get('repo_depends', ()):
      if d == target:
        maints = [x['github'] for x in
                  ly.get('maintainers', ())
                  if 'github' in x]
        ret.append(Dependent(x.name, maints))
  return ret

