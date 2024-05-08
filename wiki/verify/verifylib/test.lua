#!/usr/bin/env lua

local key = "..."
local cookie = "..."
local expected = "..."

local ffi = require("ffi")
ffi.cdef[[
bool verify(const char *key, const char *cookie, char* buf, unsigned int buflen);
]]
local verifylib = ffi.load("verifylib")

local buf = ffi.new("char[?]", 128)
local ok = verifylib.verify(key, cookie, buf, 128)
local data = ffi.string(buf)
print(ok, data, data == expected)
