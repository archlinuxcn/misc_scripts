use std::net::TcpStream;
use std::time::Duration;
use std::io::Write;

use serde::Deserialize;

use super::util::name_from_url;

#[derive(Deserialize)]
struct Mirror {
  url: url::Url,
  lastupdate: u64,
  diff: u32,
}

pub fn do_work() -> reqwest::Result<()> {
  let mirrors: Vec<Mirror> = reqwest::blocking::get("https://build.archlinuxcn.org/~imlonghao/status/status.json")?.json()?;
  send_stats(mirrors);
  Ok(())
}

fn send_stats(mirrors: Vec<Mirror>) {
  if let Err(e) = send_stats_real(mirrors) {
    eprintln!("Error while sending stats: {:?}", e);
  }
}

fn send_stats_real(mirrors: Vec<Mirror>) -> std::io::Result<()> {
  let t = timestamp();
  let mut sock = TcpStream::connect(("localhost", 2003))?;
  sock.set_write_timeout(Some(Duration::from_secs(1)))?;
  for m in mirrors {
    if m.lastupdate == 0 { // failed
      continue;
    }
    let stat = format!(
      "stats.cnrepo_mirrors.{}.delay {} {}\n",
      name_from_url(&m.url),
      m.diff,
      t,
    );
    sock.write_all(stat.as_bytes())?;
  }

  Ok(())
}

fn timestamp() -> u64 {
  use std::time::{SystemTime, UNIX_EPOCH};
  let now = SystemTime::now();
  let elapsed = now.duration_since(UNIX_EPOCH).unwrap();
  elapsed.as_secs()
}
