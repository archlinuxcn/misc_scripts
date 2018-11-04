import os
import configparser
import asyncio
from typing import List

from lilac2.repo import Repo
from lilac2.lilacpy import load_lilac, LilacMod
from lilac2.typing import Maintainer

from .config import REPODIR

def get_repo(inifile: os.PathLike) -> Repo:
  config = configparser.ConfigParser()
  config.optionxform = lambda option: option # type: ignore
  config.read(inifile)
  return Repo(config)

# FIXME: load_lilac and find_maintainers may chdir
def _get_mod(pkgbase: str) -> LilacMod:
  with load_lilac(REPODIR / pkgbase) as m:
    return m

async def find_maintainers(repo: Repo, pkgbase: str) -> List[Maintainer]:
  loop = asyncio.get_event_loop()
  mod = _get_mod(pkgbase)
  return await loop.run_in_executor(None, repo.find_maintainers, mod)

