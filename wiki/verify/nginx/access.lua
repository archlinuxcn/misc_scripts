local verify = require('verify')
local asn = ngx.var.geoip2_data_asn
local req_uri = ngx.var.request_uri
if true
    and (ngx.var.geoip2_data_country_code == 'CN'
         or asn == '132203'  -- Tencent KR?
         or asn == '37963'   -- Aliyun CN
         or asn == '45102'   -- Aliyun US
         or asn == '16509'   -- Amazon mass crawlers
         or asn == '210906'  -- UAB Bite Lietuva; many weird UA bots
         or string.find(ua, ' Firefox/[23]%.')
         or string.find(req_uri, 'SELECT%20', 1, true)
         or string.find(req_uri, '%20AND%20', 1, true)
        )
    and not (req_uri == '/wzh/api.php' and ngx.var.request_method == 'POST')
    and string.find(req_uri, '/wzh/skins/', 1, true) ~= 1
    and string.find(req_uri, '/wzh/resources/', 1, true) ~= 1
    and not verify_cookie() then
  return ngx.redirect("/__challenge?" .. ngx.encode_args{url = ngx.var.request_uri})
end

-- vim: se ft=lua:
