def iter_commits(repo, stop_time, lilac_mail):
  commit_hash = repo.head.target
  commit = repo[commit_hash]
  stack = [commit]
  seen_commits = set()

  while stack:
    commit = stack.pop()
    if commit.commit_time < stop_time:
      continue
    if commit.id.raw in seen_commits:
      continue
    stack.extend(commit.parents)
    seen_commits.add(commit.id.raw)
    if commit.author.email == lilac_mail:
      continue

    yield commit

def get_touched_packages(diff):
  ret = set()
  for d in diff.deltas:
    for a in [d.old_file, d.new_file]:
      parts = a.path.split('/', 2)
      if len(parts) == 3:
        r, pkgbase, _ = parts
        ret.add((r, pkgbase))
  return ret

