#!/usr/bin/python

import tomllib
import asyncio
import urllib.parse
import json

from cryptography import fernet
import tornado.web
from tornado.httpserver import HTTPServer
from tornado.httpclient import AsyncHTTPClient
AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

class VerifyHandler(tornado.web.RequestHandler):
  async def post(self):
    token = self.request.body.decode()
    httpclient = AsyncHTTPClient()
    config = self.settings['config']
    recaptcha_req = [
      ("secret", config['recaptcha_key']),
      ("response", token),
    ]
    res = await httpclient.fetch(
      'https://www.recaptcha.net/recaptcha/api/siteverify',
      method = 'POST',
      body = urllib.parse.urlencode(recaptcha_req),
    )
    j = json.loads(res.body)
    if j['success'] and j['hostname'] in config['valid_domains']:
      ip = self.request.remote_ip
      f = fernet.Fernet(config['fernet_key'])
      value = f.encrypt(ip.encode())
      self.set_cookie('__v', value, expires_days=7, httponly=True)
      r = 'ok'
    else:
      r = 'fail'
    self.finish({'status': r})

routes = [
  (r'/__verify', VerifyHandler),
]

async def main():
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument('config',
                      help='config file')
  args = parser.parse_args()

  with open(args.config, 'rb') as f:
    config = tomllib.load(f)

  application = tornado.web.Application(
    routes,
    config = config,
  )
  http_server = HTTPServer(application, xheaders=True)
  http_server.listen(config['listen_port'], config['listen_ip'])
  await asyncio.Event().wait()

if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    pass
