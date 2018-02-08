import os
import asyncio
import subprocess

async def find_build_log(repodir, buildlog, packages):
  autobuild = [x for x in packages
               if os.path.exists(
                 os.path.join(repodir, x, 'lilac.py'))
              ]
  pkg_re = ' (' + '|'.join(autobuild) + ') '
  cmd = ['grep', '-P', pkg_re, buildlog]

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

  out = out.decode('utf-8').splitlines()

  ret = {}

  for l in out:
    name = l.split()[2]
    ret[name] = l

  return ret
