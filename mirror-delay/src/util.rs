use std::borrow::Cow;

pub fn name_from_url(url: &url::Url) -> Cow<str> {
  if let Some(url::Host::Domain(host)) = url.host() {
    if let Some(d) = psl::domain(host.as_bytes()) {
      let whole = d.as_bytes();
      let suffix = d.suffix().as_bytes();
      let main = &whole[..suffix.as_ptr() as usize - whole.as_ptr() as usize];
      let host_stem = std::str::from_utf8(main).unwrap().trim_end_matches('.');
      return if host_stem == "xtom" {
        Cow::Owned(std::str::from_utf8(whole).unwrap().replace('.', "_"))
      } else {
        Cow::Borrowed(host_stem)
      };
    }
  }
  Cow::Borrowed("host_invalid")
}
