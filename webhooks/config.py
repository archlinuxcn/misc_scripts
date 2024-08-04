from pathlib import Path
import time

MY_GITHUB = 'lilacbot'
REPO_NAME = 'archlinuxcn/repo'

ADMIN_GH = 'lilydjwg'

REPO_URL = f'git@github.com:{REPO_NAME}.git'
MYMAIL = 'lilac@build.archlinuxcn.org'
REPODIR = Path('/data/archgitrepo-webhook/archlinuxcn').expanduser()

def gen_log_comment(pkgs: set[str]) -> str:
  ss = ['''\
| pkgbase | build history | last build log | files |
| --- | --- | --- | --- |''']
  t = int(time.time())
  for pkg in pkgs:
    ss.append(f'''\
| {pkg} \
| [build history](https://build.archlinuxcn.org/~imlonghao/#{pkg}) \
| [last build log](https://build.archlinuxcn.org/imlonghao-api/pkg/{pkg}/log/{t}) \
| [{pkg}](https://github.com/archlinuxcn/repo/tree/master/archlinuxcn/{pkg}) \
|''')
  return '\n'.join(ss)
