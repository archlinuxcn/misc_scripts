import os
import asyncio
import subprocess

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
