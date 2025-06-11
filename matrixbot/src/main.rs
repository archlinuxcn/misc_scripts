#![allow(clippy::uninlined_format_args)]

use std::time::Duration;

use matrix_sdk::{
  config::SyncSettings, ruma,
};
use matrix_sdk_base::store::{StateStoreDataKey, StateStoreDataValue};

use clap::Parser;
use tracing::info;

use matrixutils::login;
use matrixutils::verification;

mod util;
mod ipc;

use util::Result;

#[derive(Parser)]
struct Args {
  #[arg(long)]
  login: bool,
  #[arg(long)]
  verification: bool,
  #[arg(long, help="ipc socket path")]
  ipc_socket: Option<String>,
  #[arg(long, help="login info file", default_value="login.json")]
  logininfo: String,
  #[arg(long, default_value="info")]
  loglevel: String,
}

fn main() -> Result<()> {
  let args = Args::parse();
  util::setup_logging(&args.loglevel)?;

  let rt = tokio::runtime::Builder::new_current_thread()
    .enable_all()
    .build()
    .unwrap();
  rt.block_on(async_main_wrapper(args))
}

async fn async_main_wrapper(args: Args) -> Result<()> {
  use futures::future::Either;

  let main_fu = async_main(args);
  futures::pin_mut!(main_fu);
  let ctrl_c = tokio::signal::ctrl_c();
  futures::pin_mut!(ctrl_c);

  match futures::future::select(main_fu, ctrl_c).await {
    Either::Left((a, _)) => a?,
    Either::Right((b, _)) => b?,
  }

  Ok(())
}

async fn async_main(args: Args) -> Result<()> {
  let client = if args.login {
    login::new_login(&args.logininfo).await?
  } else {
    login::get_client(&args.logininfo).await?
  };

  let sync_token = client.state_store().get_kv_data(StateStoreDataKey::SyncToken).await?;
  let mut sync_settings = SyncSettings::new()
    .timeout(Duration::from_secs(600))
    .set_presence(ruma::presence::PresenceState::Unavailable);
  if let Some(StateStoreDataValue::SyncToken(token)) = sync_token {
    sync_settings = sync_settings.token(token);
  }
  info!("Syncing once...");
  client.sync_once(sync_settings.clone()).await?;
  info!("Synced.");

  if args.verification {
    verification::enable_verification(&client);
  }

  if let Some(path) = args.ipc_socket {
    ipc::enable(client.clone(), path)?;
  }

  client.sync(sync_settings).await?;

  Ok(())
}
