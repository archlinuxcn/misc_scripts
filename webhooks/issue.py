from __future__ import annotations

import re
from enum import Enum
import logging
from typing import Dict, Any, List, Set, Tuple, Optional

from agithub import Issue, GitHub

from . import config
from . import files
from . import lilac
from .util import annotate_maints, Maintainer

logger = logging.getLogger(__name__)

IssueType = Enum('IssueType', 'PackageRequest OutOfDate Orphaning Official Error Other')

_ParseState = Enum('_ParseState', 'init issuetype packages')

_TypeDescMap = {
  '软件打包请求': IssueType.PackageRequest,
  '过期软件包': IssueType.OutOfDate,
  '弃置软件包': IssueType.Orphaning,
  '软件包被官方仓库收录': IssueType.Official,
  '打包错误': IssueType.Error,
  '其它': IssueType.Other,
}

_PkgPattern = re.compile(r'[\w.+-]+')

_CANT_PARSE_NEW = '''\
Lilac cannot parse this issue. Did you follow the template? Please update and I'll reopen this.

Lilac 无法解析此问题报告。你按照模板填写了吗？请更新，然后我会重新打开这个问题。'''

_CANT_PARSE_EDITED = '''\
Lilac still cannot parse this issue, please check against the template. Please update and I'll reopen this.

Lilac 依旧无法解析此问题报告，请对照模板检查。请更新，然后我会重新打开这个问题。'''

def parse_issue_text(text: str) -> Tuple[Optional[IssueType], List[str]]:
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
      firstword_m = _PkgPattern.search(line)
      if firstword_m:
        if line.startswith('* [x] '):
          continue
        firstword = firstword_m.group()
        packages.append(firstword)

  return issuetype, packages

async def find_affecting_deps(
  packages: List[str],
) -> Dict[str, List[str]]:
  ret = {}
  for pkg in packages:
    deps = [x for x in 
            await lilac.find_dependent_packages(pkg)
            if x not in packages]
    if deps:
      ret[pkg] = deps
  return ret

async def process_orphaning(
  author: str, edited: bool,
  packages: List[str], assignees: Set[str],
  maintainers: List[Maintainer],
) -> str:
  if author != config.MY_GITHUB:
    try:
      assignees.remove(author)
    except KeyError:
      pass

  comment = ''

  depinfo = await find_affecting_deps(packages)
  if depinfo:
    affected: Set[str] = set()
    for x in depinfo.values():
      affected.update(x)

    affected_maints = {x: await lilac.find_maintainers(x) for x in affected}
    comment_parts = ['WARNING: other packages will be affected!\n']
    for p, ds in depinfo.items():
      ds_str = ', '.join(
        annotate_maints(d, affected_maints[d]) for d in ds)
      c = f'* {p} is depended by {ds_str}'
      comment_parts.append(c)
    comment += '\n'.join(comment_parts) + '\n\n'
    assignees.update(
      m for x in affected_maints.values() for m in x
    )

  if not edited and author not in maintainers:
    at_authors = ' '.join(f'@{x}' for x in maintainers)
    comment += f'WARNING: Listed packages are maintained by {at_authors} other than the issue author.'

  return comment

async def process_issue(gh: GitHub, issue_dict: Dict[str, Any],
                        edited: bool) -> None:
  issue = Issue(issue_dict, gh)
  if issue.number < 700 or 'no-lilac' in issue.labels:
    return

  body = issue.body
  issuetype, packages = parse_issue_text(body)

  if edited and issuetype != IssueType.Orphaning:
    async for c in gh.get_issue_comments(
      config.REPO_NAME, issue.number):
      if c.author == config.MY_GITHUB and 'cannot parse' in c.body:
        await c.delete()
        break

  if issuetype is None or (not packages and issuetype in [
    IssueType.OutOfDate, IssueType.Orphaning, IssueType.Official]):
    if edited:
      await issue.comment(_CANT_PARSE_EDITED)
    else:
      await issue.comment(_CANT_PARSE_NEW)
    await issue.close()
    return

  find_assignees = True
  assignees = set()
  comment = ''
  if issuetype == IssueType.PackageRequest:
    find_assignees = False
    labels = ['package-request']
  elif issuetype == IssueType.OutOfDate:
    labels = ['out-of-date']
  elif issuetype == IssueType.Orphaning:
    labels = ['orphaning']
    find_assignees = True
    assignees.add(config.MY_GITHUB)
  elif issuetype == IssueType.Official:
    labels = ['in-official-repos']
    assignees.add(config.MY_GITHUB)
  else:
    labels = []

  if packages:
    if find_assignees:
      unmaintained = []
      for pkg in packages:
        try:
          maintainers = await lilac.find_maintainers(pkg)
        except FileNotFoundError:
          continue

        if not maintainers:
          unmaintained.append(pkg)

        assignees.update(x for x in maintainers)

      if issuetype == IssueType.Orphaning:
        comment = await process_orphaning(
          issue.author, edited,
          packages, assignees, maintainers,
        )

      elif unmaintained:
        depinfo = {
          pkg: await lilac.find_dependent_packages_ext_async(pkg)
          for pkg in unmaintained
        }

        comment_parts = ['NOTE: some affected packages are unmaintained:\n']
        for p, ds in depinfo.items():
          ds_str = ', '.join(
            annotate_maints(d.pkgbase, d.maintainers) for d in ds)
          c2 = f'* {p} is depended by {ds_str}'
          comment_parts.append(c2)
        comment += '\n'.join(comment_parts) + '\n\n'

      if issuetype == IssueType.OutOfDate and packages:
        try:
          logs = await files.find_build_log(
            config.REPODIR, config.BUILDLOG, packages,
          )
        except LookupError:
          pass
        else:
          logs2 = [line for name, line in logs.items() if name in packages]
          logs3 = '\n'.join(sorted(logs2))
          comment += f'''build log for auto building out-of-date packages:
```
{logs3}
```
'''

  if labels:
    await issue.add_labels(labels)
  if assignees:
    r = await issue.assign(list(assignees))
    assigned = {x['login'] for x in r['assignees']}
    failed = assignees - assigned
    if failed:
      if comment:
        comment += '\n\n'
      comment += 'Some maintainers (perhaps outside contributors) cannot be assigned: ' + ', '.join(f'@{x}' for x in failed)
  if comment:
    await issue.comment(comment)

  if issue.closed and issue.closed_by == config.MY_GITHUB \
     and 'request-failed' not in issue.labels:
    await issue.reopen()
