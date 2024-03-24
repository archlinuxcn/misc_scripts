use std::time::Duration;

use serde::Deserialize;
use chrono::{DateTime, Utc};

use super::util::name_from_url;

#[derive(Deserialize)]
struct Response {
  last_check: DateTime<Utc>,
  urls: Vec<Mirror>,
}

#[derive(Deserialize)]
struct Mirror {
  url: url::Url,
  protocol: String,
  // it can be negative
  delay: Option<i32>,
  active: bool,
  country_code: String,
}

pub async fn do_work() -> eyre::Result<()> {
  let r: Response = reqwest::get("https://archlinux.org/mirrors/status/json/").await?
    .json().await?;
  let t = r.last_check.timestamp();
  let mirrors: Vec<_> = r.urls.into_iter().filter(|m|
    m.active && m.country_code == "CN" && m.protocol == "https" && m.delay.is_some()
  ).collect();
  send_stats(t, mirrors).await?;
  Ok(())
}

async fn send_stats(t: i64, mirrors: Vec<Mirror>) -> std::io::Result<()> {
  use tokio::net::TcpStream;
  use tokio::io::AsyncWriteExt;
  use tokio::time::timeout;

  let mut sock = TcpStream::connect(("localhost", 2003)).await?;
  for m in mirrors {
    let stat = format!(
      "stats.mirrors.{}.{}.delay {} {}\n",
      m.country_code,
      name_from_url(&m.url),
      m.delay.unwrap(),
      t,
    );
    timeout(Duration::from_millis(200), sock.write_all(stat.as_bytes())).await??;
  }

  Ok(())
}

