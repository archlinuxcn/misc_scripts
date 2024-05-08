if not verify_cookie() then
--if ngx.var.geoip2_data_country_code == 'CN' and not verify_cookie() then
  return ngx.redirect("/__challenge?" .. ngx.encode_args{url = ngx.var.uri})
end
-- vim: se ft=lua:
