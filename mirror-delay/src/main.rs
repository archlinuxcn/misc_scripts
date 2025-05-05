#![allow(clippy::uninlined_format_args)]

use std::time::Duration;

use sqlx::postgres;
use sqlx::Executor;

mod timer;
mod util;
mod official;
mod cnrepo;

async fn async_main() {
  let rate = 1.0 / (8.0 * 60.0);
  let timeout = Duration::from_secs(5);

  let pool = postgres::PgPoolOptions::new()
    .max_connections(3)
    .after_connect(|conn, _meta| Box::pin(async move {
      conn.execute("set search_path to 'mirror_delay'").await?;
      Ok(())
    }))
    .connect("postgres://%2frun%2fpostgresql").await.unwrap();

  do_work(timeout, &pool).await;
  for to_wait in timer::Timer::new(rate) {
    match to_wait {
      Ok(dur) => tokio::time::sleep(dur).await,
      Err(dur) => {
        eprintln!("behind {:.3}s.", dur.as_secs_f32());
        // don't try to compensate missed work
        continue;
      }
    }
    do_work(timeout, &pool).await;
  }
}

async fn do_work(to: Duration, pool: &postgres::PgPool) {
  use tokio::time::timeout;
  let (a, b) = futures::join!(
    timeout(to, official::do_work()),
    timeout(to, cnrepo::do_work(pool)),
  );

  match a {
    Ok(Err(e)) => { eprintln!("Error for official mirror stats: {:?}", e); }
    Ok(_) => { }
    Err(_) => { eprintln!("Timed out for official mirror stats"); }
  }
  match b {
    Ok(Err(e)) => { eprintln!("Error for archlinuxcn mirror stats: {:?}", e); }
    Ok(_) => { }
    Err(_) => { eprintln!("Timed out for archlinuxcn mirror stats"); }
  }
}

fn main() {
  nyquest_preset::register();
  let rt = tokio::runtime::Builder::new_current_thread()
    .enable_all()
    .build()
    .unwrap();
  rt.block_on(async_main());
}
