import re
from enum import Enum
import logging

from expiringdict import ExpiringDict
from agithub import Issue

from . import git
from . import config
from . import files

logger = logging.getLogger(__name__)

IssueType = Enum('IssueType', 'PackageRequest OutOfDate Orphaning Official Other')

_ParseState = Enum('_ParseState', 'init issuetype packages')

_TypeDescMap = {
  '软件打包请求': IssueType.PackageRequest,
  '过期软件包': IssueType.OutOfDate,
  '弃置软件包': IssueType.Orphaning,
  '软件包被官方仓库收录': IssueType.Official,
  '其它': IssueType.Other,
}

_PkgPattern = re.compile(r'[\w-]+')

def parse_issue_text(text):
  st = _ParseState.init
  skipping = False

  issuetype = None
  packages = []

  for line in text.splitlines():
    if line.endswith('-->'):
      skipping = False
      continue
    elif line.startswith('<!--'):
      skipping = True

    if skipping or not line:
      continue
    elif line.startswith('### 问题类型 '):
      st = _ParseState.issuetype
      continue
    elif line.startswith('### 受影响的软件包 '):
      st = _ParseState.packages
      continue
    elif line.startswith('----'):
      break

    if st == _ParseState.issuetype:
      for key in _TypeDescMap.keys():
        if key in line:
          issuetype = _TypeDescMap.get(key)
          break
    elif st == _ParseState.packages:
      firstword = _PkgPattern.search(line)
      if firstword:
        firstword = firstword.group()
        packages.append(firstword)

  return issuetype, packages

async def process_issue(gh, issue):
  issue = Issue(issue, gh)
  body = issue.body
  issuetype, packages = parse_issue_text(body)
  if issuetype is None or (not packages and issuetype in [
    IssueType.OutOfDate, IssueType.Orphaning, IssueType.Official]):
    await issue.comment('''\
Lilac cannot parse this issue. Did you follow the template?

Lilac 无法解析此问题报告。你按照模板填写了吗？''')
    return

  find_assignees = True
  assignees = []
  comment = None
  if issuetype == IssueType.PackageRequest:
    find_assignees = False
    labels = ['package-request']
  elif issuetype == IssueType.OutOfDate:
    labels = ['out-of-date']
  elif issuetype == IssueType.Orphaning:
    labels = ['orphaning']
    find_assignees = False
    assignees.append('lilacbot')
  else:
    labels = None

  if packages:
    if find_assignees:
      _email_to_login_cache.expire()
      await git.pull_repo(config.REPODIR, config.REPO)

      for pkg in packages:
        try:
          maintainer = await git.get_maintainer(
            config.REPODIR, pkg, config.MYMAIL)
        except LookupError:
          logger.warn('maintainer not found for %s', pkg)
          continue

        login = _email_to_login_cache.get(maintainer)
        if not login:
          try:
            login = await gh.find_login_by_email(maintainer)
          except LookupError:
            logger.warn('maintainer with email %s not found on GitHub', maintainer)
            continue

        assignees.append(login)

      if issuetype == IssueType.OutOfDate and packages:
        comment = ''
        try:
          logs = await files.find_build_log(
            config.REPODIR, config.BUILDLOG, packages,
          )
        except LookupError:
          pass
        else:
          logs = [line for name, line in logs.items() if name in packages]
          logs = '\n'.join(sorted(logs))
          comment = f'''build log for auto building out-of-date packages:
```
{logs}
```
'''
        aur_pkgs, aur_ups = aur.filter_aur(packages)
        aur_ups = tuple(aur_ups)
        aur_versions = aur.get_version(aur_ups)
        aur_info = '\n'.join((aur.aur_item.format(pkg, aur) for pkg, aur in zip(aur_pkgs, aur_ups)))
        if aur_info:
          comment += f'''
The following packages track AUR. Flag out-of-date on AUR first.

{aur_info}
'''

  if labels:
    await issue.add_labels(labels)
  if assignees:
    await issue.assign(assignees)
  if comment:
    await issue.comment(comment)

_email_to_login_cache = ExpiringDict(86400)
