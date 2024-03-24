use serde::Deserialize;
use sqlx::postgres;

use super::util::name_from_url;

#[derive(Deserialize)]
struct Mirror {
  url: url::Url,
  lastupdate: u64,
  diff: u32,
}

pub async fn do_work(pool: &postgres::PgPool) -> eyre::Result<()> {
  let mirrors: Vec<Mirror> =
    reqwest::get("https://build.archlinuxcn.org/~imlonghao/status/status.json").await?
    .json().await?;
  send_stats(mirrors, pool).await?;
  Ok(())
}

async fn send_stats(
  mirrors: Vec<Mirror>,
  pool: &postgres::PgPool,
) -> sqlx::Result<()> {
  let mut tx = pool.begin().await?;
  for m in mirrors.into_iter().filter(|m| m.lastupdate != 0) {
    let name = name_from_url(&m.url);
    let delay = m.diff;
    sqlx::query("insert into cnmirror_delay (name, delay) values ($1, $2)")
      .bind(name)
      .bind(delay as i32)
      .execute(&mut *tx)
      .await?;
  }

  tx.commit().await?;
  Ok(())
}
