#!/usr/bin/python3

import json
import hmac
import logging
import os
import asyncio

from aiohttp import web

from agithub import GitHub

from . import issue
from . import config
from . import git

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

  async def post(self, request):
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

    data = json.loads(body)

    if event_type == 'push':
      pushed_repo = data['repository']['full_name']
      if pushed_repo == config.REPO_NAME:
        asyncio.ensure_future(
          git.pull_repo(config.REPODIR, config.REPO_NAME)
        )
      return

    if event_type != 'issues':
      return

    if data['action'] not in ['opened', 'edited']:
      return

    asyncio.ensure_future(issue.process_issue(
      self.gh, data['issue'], data['action'] == 'edited'))

def setup_app(app, secret, token):
  handler = IssueHandler(secret, token)
  app.router.add_post('/lilac/issue', handler.post)

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
