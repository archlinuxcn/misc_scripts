import os
import asyncio
import subprocess
import time

_last_pull: float = 0

async def may_pull_repo(repodir: os.PathLike, repo: str) -> None:
  if _last_pull + 600 > time.time():
    return

  await pull_repo(repodir, repo)

async def pull_repo(repodir: os.PathLike, repo: str) -> None:
  if os.path.dirname(repodir):
    process = await asyncio.create_subprocess_exec(
      'git', 'pull',
      cwd = repodir,
    )
    res = await process.wait()
  else:
    process = await asyncio.create_subprocess_exec(
      'git', 'clone', repo, str(repodir),
    )
    res = await process.wait()

  if res != 0:
    raise subprocess.CalledProcessError(res, 'pull_repo')

  global _last_pull
  _last_pull = time.time()
