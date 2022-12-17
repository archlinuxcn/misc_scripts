#!/usr/bin/env lua

local log_req = function(premature, data)
  -- premature is ignored because it's always false for timeout 0
  local ip, port = '127.0.0.1', 8125
  local sock = ngx.socket.udp()
  sock:setpeername(ip, port)
  sock:send(data)
  sock:close()
end

call_statsd = function(name)
  local prefix = 'wiki.nginx.' .. name .. '.'
  local status = ngx.status
  local data_s = prefix .. 'requests.'.. status ..':1|c'
  ngx.timer.at(0, log_req, data_s)
  local time = ngx.var.upstream_response_time
  if time then
    time = time:gsub(',.*', '') -- only use first time if multiple
    if tonumber(time) then
      local data_t = prefix .. 'time:' .. (tonumber(time) * 1000) .. '|ms'
      ngx.timer.at(0, log_req, data_t)
    end
  end
end

--[[

usage:

add to the http section:

  init_by_lua_file stats.lua; # This file

add to server / location section, e.g.

  log_by_lua_block {
    call_statsd("wiki")
  }

--]]
