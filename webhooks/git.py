import os
import asyncio
import subprocess

async def get_maintainer(repodir, package, exclude):
  process = await asyncio.create_subprocess_exec(
    "git", "log", "-1", "--format=%H %an <%ae>", "--", package,
    cwd = repodir,
    stdout = subprocess.PIPE,
  )

  while True:
    line = await process.stdout.readline()
    if not line:
      raise LookupError(f'no maintainer found for {package}')
    line = line.decode()
    commit, author = line.rstrip().split(None, 1)
    if exclude not in author:
      process.terminate()
      await process.wait()
      break

  return author

async def pull_repo(repodir, repo):
  if os.path.dirname(repodir):
    process = await asyncio.create_subprocess_exec(
      'git', 'pull',
      cwd = repodir,
    )
    res = await process.wait()
  else:
    process = await asyncio.create_subprocess_exec(
      'git', 'clone', repo, repodir,
    )
    res = await process.wait()

  if res != 0:
    raise subprocess.CalledProcessError(res, 'pull_repo')
