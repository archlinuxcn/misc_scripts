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
use secrecy::ExposeSecret;

use crate::util::Result;

#[derive(serde::Deserialize, serde::Serialize)]
#[serde(deny_unknown_fields)]
struct LoginInfo {
  homeserver: url::Url,
  user_id: String,
  device_id: String,
  access_token: String,
}

fn ask_password(account: &ruma::UserId) -> Result<Option<secrecy::Secret<String>>> {
  if let Some(mut input) = pinentry::PassphraseInput::with_default_binary() {
    Ok(Some(input
      .with_title("Input Password")
      .with_description(&format!("Enter password for account: {account}"))
      .required("password can't be empty")
      .interact().map_err(|e| eyre::eyre!("pinentry error: {e}"))?
    ))
  } else {
    Ok(None)
  }
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

  let store = SqliteStateStore::open("states", None).await?;
  let store_config = matrix_sdk::config::StoreConfig::new()
    .state_store(store);
  let client = Client::builder()
    .store_config(store_config)
    .server_name(uid.server_name())
    .build().await?;

  let password = if let Some(p) = ask_password(&uid)? {
    p
  } else {
    secrecy::SecretString::new(rl.readline("Password: ")?)
  };
  client.matrix_auth().login_username(uid, password.expose_secret()).send().await?;

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
