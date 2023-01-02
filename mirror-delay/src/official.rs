use std::net::TcpStream;
use std::time::Duration;
use std::io::Write;

use serde::Deserialize;
use chrono::{DateTime, Utc};

use super::util::name_from_url;

#[derive(Deserialize)]
struct Result {
  last_check: DateTime<Utc>,
  urls: Vec<Mirror>,
}

#[derive(Deserialize)]
struct Mirror {
  url: url::Url,
  protocol: String,
  delay: Option<u32>,
  active: bool,
  country_code: String,
}

pub fn do_work() -> reqwest::Result<()> {
  let r: Result = reqwest::blocking::get("https://archlinux.org/mirrors/status/json/")?.json()?;
  let t = r.last_check.timestamp();
  let mirrors: Vec<_> = r.urls.into_iter().filter(|m|
    m.active && m.country_code == "CN" && m.protocol == "https" && m.delay.is_some()
  ).collect();
  send_stats(t, mirrors);
  Ok(())
}

fn send_stats(t: i64, mirrors: Vec<Mirror>) {
  if let Err(e) = send_stats_real(t, mirrors) {
    eprintln!("Error while sending stats: {:?}", e);
  }
}

fn send_stats_real(t: i64, mirrors: Vec<Mirror>) -> std::io::Result<()> {
  let mut sock = TcpStream::connect(("localhost", 2003))?;
  sock.set_write_timeout(Some(Duration::from_secs(1)))?;
  for m in mirrors {
    let stat = format!(
      "stats.mirrors.{}.{}.delay {} {}\n",
      m.country_code,
      name_from_url(&m.url),
      m.delay.unwrap(),
      t,
    );
    sock.write_all(stat.as_bytes())?;
  }

  Ok(())
}

