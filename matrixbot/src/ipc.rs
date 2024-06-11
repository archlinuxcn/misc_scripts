use matrix_sdk::Client;
use matrix_sdk::ruma::{
  OwnedRoomAliasId, OwnedRoomOrAliasId,
  events::room::message::RoomMessageEventContent,
};
use tokio::net::UnixDatagram;
use tracing::{event, Level};

use crate::util::Result;

struct Ipc {
  socket: UnixDatagram,
  client: Client,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
#[serde(tag="cmd")]
enum Message {
  #[serde(rename="send_message")]
  SendMessage { target: OwnedRoomOrAliasId, content: String },
}

async fn handle_msg(ipc: &Ipc, msg: &[u8]) -> Result<()> {
  let msg_str = std::str::from_utf8(msg)?;
  event!(Level::DEBUG, msg = msg_str, "got message");
  let msg = serde_json::from_str(msg_str)?;
  match msg {
    Message::SendMessage { target, content } => {
      let room_id = if target.is_room_alias_id() {
        let alias: OwnedRoomAliasId = target.try_into().unwrap();
        ipc.client.resolve_room_alias(&alias).await?.room_id
      } else {
        target.try_into().unwrap()
      };
      if let Some(room) = ipc.client.get_room(&room_id) {
        event!(Level::INFO, msg = msg_str, "sending message");
        room.send(RoomMessageEventContent::text_plain(content)).await?;
      } else {
        event!(Level::ERROR, msg = msg_str, "room not found");
      }
    },
  }
  Ok(())
}

async fn ipc_task(ipc: Ipc) -> Result<()> {
  let mut buf = vec![0; 4096];
  loop {
    let (size, _addr) = ipc.socket.recv_from(&mut buf).await?;
    if let Err(e) = handle_msg(&ipc, &buf[..size]).await {
      event!(Level::ERROR, error=?e, msg=?&buf[..size], "bad ipc message");
    }
  }
}

pub fn enable(client: Client, mut path: String) -> Result<()> {
  if path.starts_with('@') {
    path.replace_range(0..1, "\0");
  } else {
    let _ = std::fs::remove_file(&path);
  }
  let socket = UnixDatagram::bind(&path)?;
  let ipc = Ipc { socket, client };
  tokio::spawn(ipc_task(ipc));
  Ok(())
}
