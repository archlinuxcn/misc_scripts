use std::ffi::{c_char, c_uint, CStr};

use eyre::Result;
use eyre::eyre;

#[no_mangle]
pub unsafe fn verify(key: *const c_char, cookie: *const c_char, ttl: c_uint, buf: *mut c_char, buflen: c_uint) -> bool {
  let (ret, data) = match verify_inner(key, cookie, ttl) {
    Ok(data) => (true, data),
    Err(e) => (false, format!("{:#?}", e)),
  };
  unsafe {
    buf.copy_from_nonoverlapping(data.as_ptr() as *const i8, buflen as usize-1);
    std::ptr::write(buf.byte_offset(buflen as isize-1), 0);
  }
  ret
}

fn verify_inner(key: *const c_char, cookie: *const c_char, ttl: u32) -> Result<String> {
  let key = unsafe { CStr::from_ptr(key) };
  let key = key.to_str()?;
  let cookie = unsafe { CStr::from_ptr(cookie) };
  let cookie = cookie.to_str()?;

  let fernet = fernet::Fernet::new(key).ok_or_else(|| eyre!("failed to load fernet key"))?;
  let data = fernet.decrypt_with_ttl(cookie, ttl.into())?;
  Ok(String::from_utf8(data)?)
}
