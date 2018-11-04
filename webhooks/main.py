#!/usr/bin/env python3

import json
import hmac
import logging
import os

from aiohttp import web

from agithub import GitHub
from expiringdict import ExpiringDict

from . import issue
from . import lilac
from . import config

logger = logging.getLogger(__name__)

class IssueHandler:
  def __init__(self, secret, token):
    self.secret = secret.encode('ascii')
    self.token = token
    # need to create inside a loop
    self.gh = None

  def get_signature(self, body):
    m = hmac.new(self.secret, digestmod='sha1')
    m.update(body)
    return 'sha1=' + m.hexdigest()

  async def __call__(self, request):
    if not self.gh:
      self.gh = GitHub(self.token)

    sig = request.headers.get('X-Hub-Signature')
    body = await request.content.read()
    our_sig = self.get_signature(body)
    if not hmac.compare_digest(sig, our_sig):
      logger.error('signature mismatch: %r != %r', sig, our_sig)
      return web.Response(status=500)

    res = await self.process(request, body)
    if res is None:
      res = web.Response(status=204)
    return res

  async def process(self, request, body):
    event_type = request.headers.get('X-GitHub-Event')

    if event_type == 'ping':
      return web.Response(status=204, text='PONG!')

    if event_type != 'issues':
      return

    data = json.loads(body)
    if data['action'] != 'opened':
      return

    await issue.process_issue(self.gh, data['issue'])

class MaintainersHandler:
  def __init__(self):
    self.repo = lilac.get_repo(config.LILAC_INI)
    self._cache = ExpiringDict(60)

  async def get_single_result(self, pkgbase):
    if pkgbase in self._cache:
      return self._cache[pkgbase]

    maintainers = await lilac.find_maintainers(self.repo, pkgbase)
    r = [{
      'name': m.name,
      'email': m.email,
      'github': m.github,
    } for m in maintainers]
    self._cache[pkgbase] = r
    return r

  async def __call__(self, request: web.Request) -> web.Response:
    q = request.query.get('q')
    if q:
      packages = q.split(',')
    else:
      packages = []

    ret = []

    self._cache.expire()

    for pkgbase in packages:
      ms = await self.get_single_result(pkgbase)
      ret.append({
        'pkgbase': pkgbase,
        'maintainers': ms,
      })

    res = web.json_response({'result': ret})
    res.headers['Cache-Control'] = 'public, max-age=60'
    return res

def setup_app(app, secret, token):
  app.router.add_post('/lilac/issue', IssueHandler(secret, token))
  app.router.add_post('/lilac/find_maintainers', MaintainersHandler())

def main():
  import argparse

  from nicelogger import enable_pretty_logging

  parser = argparse.ArgumentParser(
    description = 'HTTP services for build.archlinuxcn.org',
  )
  parser.add_argument('--port', default=9007, type=int,
                      help='port to listen on')
  parser.add_argument('--ip', default='127.0.0.1',
                      help='address to listen on')
  parser.add_argument('--loglevel', default='info',
                      choices=['debug', 'info', 'warn', 'error'],
                      help='log level')
  args = parser.parse_args()

  enable_pretty_logging(args.loglevel.upper())

  app = web.Application()
  setup_app(app, os.environ['SECRET'], os.environ['GITHUB_TOKEN'])

  web.run_app(app, host=args.ip, port=args.port)

if __name__ == '__main__':
  main()
