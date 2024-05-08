local KEY = "..."
local cookie = require("cookie")
local ffi = require("ffi")
ffi.cdef[[
  bool verify(const char *key, const char *cookie, char* buf, unsigned int buflen);
]]
local verifylib = ffi.load("verifylib")

verify_cookie = function()
  local buf = ffi.new("char[?]", 128)
  local c = cookie:new():get('__v')
  if not c then
    return false
  end
  c = c:gsub('"', '')

  local ok = verifylib.verify(KEY, c, buf, 128)
  local data = ffi.string(buf)
  if not ok then
    ngx.log(ngx.ERR, data)
    return false
  end

  if data ~= ngx.var.remote_addr then
    ngx.log(ngx.ERR, "cookie data mismatch: ", data)
    return false
  end

  return true
end

-- vim: se ft=lua:
