#!/usr/bin/python3

import hmac
import logging
import os
import asyncio
import subprocess

from aiohttp import web

logger = logging.getLogger(__name__)

class PushHandler:
  def __init__(self, secret, repodir):
    self.secret = secret.encode('ascii')
    self.repodir = repodir

  def get_signature(self, body):
    m = hmac.new(self.secret, digestmod='sha1')
    m.update(body)
    return 'sha1=' + m.hexdigest()

  async def post(self, request):
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

    if event_type == 'push':
      asyncio.ensure_future(pull_repo(self.repodir))
      return

async def pull_repo(repodir: os.PathLike) -> None:
  process = await asyncio.create_subprocess_exec(
    'git', 'pull',
    cwd = repodir,
  )
  res = await process.wait()

  if res != 0:
    raise subprocess.CalledProcessError(res, 'pull_repo')

def setup_app(app, secret, repodir):
  handler = PushHandler(secret, repodir)
  app.router.add_post('/webhook', handler.post)

def main():
  import argparse

  from nicelogger import enable_pretty_logging

  parser = argparse.ArgumentParser(
    description = 'Webhook to auto pull a local repo when pushed to GitHub',
  )
  parser.add_argument('--port', default=9007, type=int,
                      help='port to listen on')
  parser.add_argument('--ip', default='127.0.0.1',
                      help='address to listen on')
  parser.add_argument('--loglevel', default='info',
                      choices=['debug', 'info', 'warn', 'error'],
                      help='log level')
  parser.add_argument('repodir',
                      help='the repo to pull')
  args = parser.parse_args()

  enable_pretty_logging(args.loglevel.upper())

  app = web.Application()
  setup_app(app, os.environ['SECRET'], args.repodir)

  web.run_app(app, host=args.ip, port=args.port)

if __name__ == '__main__':
  main()
