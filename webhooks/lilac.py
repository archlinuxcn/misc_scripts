from __future__ import annotations

import asyncio
from typing import List

from lilac2.lilacyaml import (
  iter_pkgdir, load_lilac_yaml,
)

from .config import REPODIR
from .util import Dependent, Maintainer

async def find_maintainers(
  pkgbase: str,
) -> List[Maintainer]:
  loop = asyncio.get_event_loop()
  return await loop.run_in_executor(
    None, _find_maintainers_sync, pkgbase)

def _find_maintainers_sync(
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
  loop = asyncio.get_event_loop()
  dependents = await loop.run_in_executor(
    None, find_dependent_packages_ext, str)
  return [x.pkgbase for x in dependents]

def find_dependent_packages_ext(
  target: str,
) -> List[Dependent]:
  ret = []
  for x in iter_pkgdir(REPODIR):
    ly = load_lilac_yaml(x)
    for d, _ in ly.get('repo_depends', []):
      if d == target:
        maints = [x['github'] for x in
                  ly.get('maintainers', ())
                  if 'github' in x]
        ret.append(Dependent(x.name, maints))
  return ret

