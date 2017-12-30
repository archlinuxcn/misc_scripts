import asyncio
import subprocess

async def get_maintainer(repodir, package, exclude):
  process = await asyncio.create_subprocess_exec(
    "git", "log", "-1", "--format=%H %an <%ae>", "--", package,
    cwd = repodir,
    stdout = subprocess.PIPE,
  )

  while True:
    line = await process.readline()
    if not line:
      raise LookupError(f'no maintainer found for {package}')
    commit, author = line.rstrip().split(None, 1)
    if exclude not in author:
      process.terminate()
      await process.wait()
      break

  return author
