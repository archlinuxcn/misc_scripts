use std::path::Path;
use std::io::Write;

use matrix_sdk::ruma;
use matrix_sdk::{
  Client,
  matrix_auth::{MatrixSession, MatrixSessionTokens},
  SessionMeta,
};
use matrix_sdk_sqlite::SqliteStateStore;
use tracing::info;

use crate::util::Result;

#[derive(serde::Deserialize, serde::Serialize)]
#[serde(deny_unknown_fields)]
struct LoginInfo {
  homeserver: url::Url,
  user_id: String,
  device_id: String,
  access_token: String,
}

pub async fn interactive_login<P: AsRef<Path>>(
  loginfile: P,
) -> Result<Client> {
  info!("interactive login.");
  let mut rl = rustyline::DefaultEditor::new()?;
  let uid: ruma::OwnedUserId = loop {
    let user = match rl.readline("User: ") {
      Ok(s) => s,
      Err(_) => continue,
    };
    match user.parse() {
      Ok(u) => {
        break u;
      }
      Err(e) => {
        eprintln!("Error: {:?}", e);
      }
    }
  };

  let client = Client::builder().server_name(uid.server_name()).build().await?;

  // TODO: use pinentry
  let password = rl.readline("Password: ")?;
  client.matrix_auth().login_username(uid, &password).send().await?;

  let login_info = LoginInfo {
    homeserver: client.homeserver(),
    user_id: String::from(client.user_id().unwrap().as_str()),
    device_id: String::from(client.device_id().unwrap().as_str()),
    access_token: client.access_token().unwrap(),
  };
  let data = serde_json::to_string_pretty(&login_info)?;
  let mut f = std::fs::File::create(loginfile)?;
  f.write_all(data.as_bytes())?;
  f.write_all(b"\n")?;

  Ok(client)
}

pub async fn get_client<P: AsRef<Path>>(logininfo: P) -> Result<Client> {
  info!("Login...");
  let f = std::fs::File::open(logininfo)?;
  let f = std::io::BufReader::new(f);
  let info: LoginInfo = serde_json::from_reader(f)?;
  let session = MatrixSession {
    meta: SessionMeta {
      user_id: info.user_id.try_into()?,
      device_id: info.device_id.into(),
    },
    tokens: MatrixSessionTokens {
      access_token: info.access_token,
      refresh_token: None,
    },
  };

  let store = SqliteStateStore::open("states", None).await?;
  let store_config = matrix_sdk::config::StoreConfig::new()
    .state_store(store);
  let client = Client::builder()
    .store_config(store_config)
    .homeserver_url(info.homeserver)
    .build()
    .await?;
  client.restore_session(session).await?;
  Ok(client)
}
