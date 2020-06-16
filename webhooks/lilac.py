from __future__ import annotations

import os
import configparser
import asyncio
from typing import List
from pathlib import Path

from lilac2.repo import Repo
from lilac2.lilacpy import load_lilac, LilacMod
from lilac2.typing import Maintainer
from lilac2.lilacyaml import (
  iter_pkgdir, load_lilac_yaml,
)

from .config import REPODIR

def get_repo(inifile: os.PathLike) -> Repo:
  config = configparser.ConfigParser()
  config.optionxform = lambda option: option # type: ignore
  config.read(inifile)
  return Repo(config)

def _get_mod(pkgbase: str) -> LilacMod:
  with load_lilac(REPODIR / pkgbase) as m:
    return m

async def find_maintainers(
  repo: Repo, pkgbase: str,
) -> List[Maintainer]:
  loop = asyncio.get_event_loop()
  mod = _get_mod(pkgbase)
  return await loop.run_in_executor(
    None, repo.find_maintainers, mod)

async def find_dependent_packages(
  pkgbase: str,
) -> List[str]:
  loop = asyncio.get_event_loop()
  return await loop.run_in_executor(
    None, _find_dependent_packages, str)

def _find_dependent_packages(target: str) -> List[str]:
  ret = []
  for x in iter_pkgdir(REPODIR):
    ly = load_lilac_yaml(x)
    for d, _ in ly.get('repo_depends', []):
      if d == target:
        ret.append(x.name)
  return ret

