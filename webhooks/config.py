from pathlib import Path

MY_GITHUB = 'lilacbot'
REPO_NAME = 'archlinuxcn/repo'

REPO_URL = f'git@github.com:{REPO_NAME}.git'
MYMAIL = 'lilac@build.archlinuxcn.org'
REPODIR = Path('~/archgitrepo-webhook/archlinuxcn').expanduser()
BUILDLOG = Path('~/.lilac/build.log').expanduser()
LILAC_INI = Path('~/soft/lilac/config.ini').expanduser()
