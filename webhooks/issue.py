from enum import Enum
import logging

from expiringdict import ExpiringDict
from agithub import Issue

from . import git
from . import config

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

def parse_issue_text(text):
  st = _ParseState.init
  skipping = False

  issuetype = None
  packages = []

  for line in text.splitlines():
    if line.endswith('-->'):
      skipping = False
    elif line.startswith('<!--'):
      skipping = True

    if skipping:
      continue
    elif line.startswith('### 问题类型 '):
      st = _ParseState.issuetype
    elif line.startswith('### 受影响的软件包 '):
      st = _ParseState.packages
    elif line.startswith('----'):
      break

    if line.startswith('*'):
      if st == _ParseState.issuetype:
        firstword = line[1:].split(None, 1)[0]
        issuetype = _TypeDescMap.get(firstword)
      elif st == _ParseState.packages:
        firstword = line[1:].split(None, 1)[0]
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

  if labels:
    await issue.add_labels(labels)
  if assignees:
    await issue.assign(assignees)

_email_to_login_cache = ExpiringDict(86400)
