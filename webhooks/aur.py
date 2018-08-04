import configparser
from functools import lru_cache
import asyncio
from nvchecker.source.aur import get_version as _async_get_version

from . import config

aur_item = '* [{}](https://aur.archlinux.org/packages/{})'

@lru_cache(1)
def __load_nvconfig():
  nvconfig = configparser.ConfigParser(dict_type=dict, allow_no_value=True)
  with open(config.REPODIR + '/nvchecker.ini', 'r') as f:
    nvconfig.read_file(f)
  return nvconfig


def filter_aur(packages):
  nvconfig = __load_nvconfig()
  aur_info = filter(
    lambda r: r[1] is not None,
    ((pkg, nvconfig.get(pkg, 'aur', fallback=None)) for pkg in packages)
  )
  packages = (p[0] for p in aur_info)
  upstreams = (p[1] or p[0] for p in aur_info)

  return packages, upstreams


def get_version(packages):
  nvconfig = __load_nvconfig()
  pkg_q = asyncio.Queue(maxsize=20)

  ioloop = asyncio.get_event_loop()

  async def worker():
    pkg = await pkg_q.get()
    return await _async_get_version(pkg, nvconfig[pkg])

  tasks = []
  for pkg in packages:
    asyncio.ensure_future(pkg_q.put(pkg))
    tasks.append(worker())

  return ioloop.run_until_complete(asyncio.gather(*tasks))


if __name__ == '__main__':
  print(get_version(['compton-git', 'yaourt']))
