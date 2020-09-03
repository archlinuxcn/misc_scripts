import asyncio
import subprocess
from pathlib import Path
from typing import Iterable, Dict

async def find_build_log(
  repodir: Path, buildlog: Path, packages: Iterable[str],
) -> Dict[str, str]:
  autobuild = [x for x in packages
               if (repodir / x / 'lilac.yaml').exists()]
  pkg_re = ' (' + '|'.join(autobuild) + ') '
  cmd = ['grep', '-P', pkg_re, str(buildlog)]

  process = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=subprocess.PIPE,
  )
  out, _ = await process.communicate()
  res = await process.wait()
  if res == 1: # not found:
    raise LookupError
  elif res != 0:
    raise subprocess.CalledProcessError(res, 'grep_buildlog')

  out_lines = out.decode('utf-8').splitlines()

  ret = {}

  for l in out_lines:
    name = l.split()[2]
    ret[name] = l

  return ret
