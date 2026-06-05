use std::time::{SystemTime, UNIX_EPOCH};

use serde::Deserialize;
use sqlx::postgres;

use super::util::name_from_url;

#[derive(Deserialize)]
struct Mirror {
  url: url::Url,
  lastupdate: u64,
  diff: i32,
}

pub async fn do_work(pool: &postgres::PgPool) -> eyre::Result<()> {
  let res = nyquest::r#async::get("https://build.archlinuxcn.org/~imlonghao/status/status.json").await?;
  let t = res.get_header("last-modified").ok()
    .and_then(|x| httpdate::parse_http_date(&x[0]).ok())
    .unwrap_or_else(SystemTime::now);
  let mirrors: Vec<Mirror> = res.json().await?;
  send_stats(t.duration_since(UNIX_EPOCH)?.as_secs() as i64, mirrors, pool).await?;
  Ok(())
}

async fn send_stats(
  t: i64,
  mirrors: Vec<Mirror>,
  pool: &postgres::PgPool,
) -> sqlx::Result<()> {
  let mut tx = pool.begin().await?;
  for m in mirrors.into_iter().filter(|m| m.lastupdate != 0) {
    let name = name_from_url(&m.url);
    let delay = m.diff;
    sqlx::query("
        insert into cnmirror_delay
          (ts, name, delay)
        values
          (to_timestamp($1), $2, $3)
        on conflict do nothing
      ")
      .bind(t)
      .bind(name)
      .bind(delay)
      .execute(&mut *tx)
      .await?;
  }

  tx.commit().await?;
  Ok(())
}
