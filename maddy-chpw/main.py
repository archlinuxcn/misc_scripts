#!/usr/bin/python3

import logging
import subprocess

import aiohttp
from aiohttp import web
from aiohttp_session import setup, get_session, new_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
from yarl import URL
import asyncpg

import config

logger = logging.getLogger(__name__)
KEY_DB = web.AppKey('db', asyncpg.Pool)

async def index(request):
  session = await get_session(request)
  username = session.get('username')
  if not username:
    with open('index.html', 'rb') as f:
      body = f.read()
    return web.Response(
      body = body,
      content_type = 'text/html',
      charset = 'utf-8',
    )

  db = request.app[KEY_DB]
  mailaddr, _new = await get_mailinfo(db, username)
  with open('index-loggedin.html') as f:
    body = f.read()
  return web.Response(
    text = body.format(username=username, mailaddr=f'{mailaddr}@archlinuxcn.org'),
    content_type = 'text/html',
    charset = 'utf-8',
  )

async def github_login(request):
  code = request.query.get('code')
  if not code:
    url = URL('https://github.com/login/oauth/authorize') % {
      'client_id': config.CLIENT_ID,
      'redirect_uri': f'https://{request.host}/mail/login',
      'scope': 'read:org',
    }
    raise web.HTTPFound(str(url))

  async with aiohttp.ClientSession() as session:
    url = 'https://github.com/login/oauth/access_token'
    data = {
      'client_id': config.CLIENT_ID,
      'client_secret': config.CLIENT_SECRET,
      'code': code,
    }
    headers = {
      'Accept': 'application/json',
    }
    async with session.post(url, data=data, headers=headers) as res:
      j = await res.json()
      access_token = j['access_token']

    url = 'https://api.github.com/user/orgs'
    headers = {
      'Accept': 'application/vnd.github+json',
      'Authorization': f'Bearer {access_token}',
      'X-GitHub-Api-Version': '2022-11-28',
    }
    async with session.get(url, headers=headers) as res:
      j = await res.json()
      orgs = [o['login'] for o in j]
      if config.TARGET_ORG not in orgs:
        raise web.HTTPForbidden()

    url = 'https://api.github.com/user'
    async with session.get(url, headers=headers) as res:
      j = await res.json()
      username = j['login']
    session = await new_session(request)
    session['username'] = username

  raise web.HTTPFound('/mail/chpw')

async def submit(request):
  session = await get_session(request)
  username = session.get('username')
  if not username:
    raise web.HTTPForbidden()

  data = await request.post()
  newpass = data.get('password')
  if not newpass:
    raise web.HTTPBadRequest()

  db = request.app[KEY_DB]
  mailaddr, new = await get_mailinfo(db, username)
  logger.info('%s wants to change password for %s (new? %s).', username, mailaddr, new)
  await chpw(db, mailaddr, newpass, new)

  return web.Response(text='OK')

async def get_mailinfo(db, username):
  async with db.acquire() as conn, conn.transaction():
    rs = await conn.fetch('select mailname, new from mailinfo where github ilike $1', username)
    if not rs:
      raise web.HTTPNotFound(reason='user not found in database')

    return rs[0]

async def chpw(db, addr, newpass, new):
  newpass = newpass.encode()
  mailaddr = f'{addr}@archlinuxcn.org'
  if new:
    cmd = ['maddy', 'creds', 'create', mailaddr]
    subprocess.run(cmd, input=newpass, check=True)
    cmd = ['maddy', 'imap-acct', 'create', mailaddr]
    subprocess.run(cmd, check=True)
    async with db.acquire() as conn, conn.transaction():
      await conn.execute('update mailinfo set new = false where mailname = $1', addr)
  else:
    cmd = ['maddy', 'creds', 'password', mailaddr]
    subprocess.run(cmd, input=newpass, check=True)

async def init_db(app):
  app[KEY_DB] = await asyncpg.create_pool(config.DB_URL, setup=conn_init, min_size=0)
  yield
  await app[KEY_DB].close()

async def conn_init(conn):
  await conn.execute("set search_path to 'mailusers'")

def setup_app(app):
  app.cleanup_ctx.append(init_db)

  f = fernet.Fernet(config.FERNET_KEY)
  setup(app, EncryptedCookieStorage(
    f, path='/mail/chpw', max_age=86400,
    secure=True, samesite='Lax',
  ))

  app.router.add_get('/mail/chpw', index)
  app.router.add_post('/mail/chpw', submit)
  app.router.add_get('/mail/login', github_login)

def main():
  import argparse

  from nicelogger import enable_pretty_logging

  parser = argparse.ArgumentParser(
    description = 'change password for maddy accounts',
  )
  parser.add_argument('--port', default=9008, type=int,
                      help='port to listen on')
  parser.add_argument('--ip', default='127.0.0.1',
                      help='address to listen on')
  parser.add_argument('--loglevel', default='info',
                      choices=['debug', 'info', 'warn', 'error'],
                      help='log level')
  args = parser.parse_args()

  enable_pretty_logging(args.loglevel.upper())

  app = web.Application()
  setup_app(app)

  web.run_app(app, host=args.ip, port=args.port)

if __name__ == '__main__':
  main()
