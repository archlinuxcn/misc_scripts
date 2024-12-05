use matrix_sdk::{Client, Room};
use matrix_sdk::ruma::{
  self,
  OwnedRoomAliasId, OwnedRoomOrAliasId,
  OwnedUserId, OwnedRoomId,
  events::room::message::RoomMessageEventContent,
};
use matrix_sdk::deserialized_responses::TimelineEvent;
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
  SendMessage { target: OwnedRoomOrAliasId, content: String, html_content: Option<String> },
  #[serde(rename="delete_user_messages")]
  DeleteUserMessages { target: OwnedRoomOrAliasId, user: OwnedUserId },
}

async fn resolve_to_room_id(client: &Client, target: OwnedRoomOrAliasId) -> Result<OwnedRoomId> {
  let room_id = if target.is_room_alias_id() {
    let alias: OwnedRoomAliasId = target.try_into().unwrap();
    client.resolve_room_alias(&alias).await?.room_id
  } else {
    target.try_into().unwrap()
  };
  Ok(room_id)
}

async fn handle_msg(ipc: &Ipc, msg: &[u8]) -> Result<()> {
  let msg_str = std::str::from_utf8(msg)?;
  event!(Level::DEBUG, msg = msg_str, "got message");
  let msg = serde_json::from_str(msg_str)?;
  match msg {
    Message::SendMessage { target, content, html_content } => {
      event!(Level::INFO, msg = msg_str, "sending message");
      let room_id = resolve_to_room_id(&ipc.client, target).await?;
      if let Some(room) = ipc.client.get_room(&room_id) {
        let msg = match html_content {
          Some(html) => RoomMessageEventContent::text_html(content, html),
          None => RoomMessageEventContent::text_plain(content),
        };
        room.send(msg).await?;
      } else {
        event!(Level::ERROR, msg = msg_str, "room not found");
      }
    },
    Message::DeleteUserMessages { target, user } => {
      event!(Level::INFO, %target, %user, "deleting messages");
      let room_id = resolve_to_room_id(&ipc.client, target).await?;
      if let Some(room) = ipc.client.get_room(&room_id) {
        delete_spam_messages(room, user).await;
      } else {
        event!(Level::ERROR, msg = msg_str, "room not found");
      }
    }
  }
  Ok(())
}

async fn delete_spam_messages(
  room: Room,
  target_user: OwnedUserId,
) {
  if let Err(e) = delete_spam_messages_real(room, target_user).await {
    event!(Level::ERROR, "error delete_spam_messages: {:?}", e);
  }
}

async fn search_message_for_user(
  room: &Room,
  target_user: ruma::OwnedUserId,
  limit: u64,
) -> Result<Vec<TimelineEvent>> {
  event!(Level::INFO, %target_user, "Search messages...");

  let mut msgs = {
    let mut filter = ruma::api::client::filter::RoomEventFilter::empty();
    filter.senders = Some(vec![target_user]);

    let mut mopts = matrix_sdk::room::MessagesOptions::backward();
    mopts.filter = filter;
    mopts.limit = ruma::UInt::new(limit).unwrap();
    room.messages(mopts).await?.chunk
  };
  msgs.retain(|ev|
    if let Ok(Some(t)) = ev.kind.raw().get_field::<&str>("type") {
      t == "m.room.message"
    } else {
      false
    }
  );
  event!(Level::INFO, "Got {} messages.", msgs.len());
  Ok(msgs)
}

async fn delete_spam_messages_real(
  room: Room,
  target_user: ruma::OwnedUserId,
) -> Result<()> {
  let msgs = search_message_for_user(&room, target_user.to_owned(), 10).await?;

  let reason = Some("spam");
  for msg in msgs {
    let msg = msg.kind.into_raw().deserialize()?;
    event!(Level::DEBUG, ?msg, "Message");
    if msg.sender() != target_user {
      continue;
    }
    if let ruma::events::AnySyncTimelineEvent::MessageLike(msg) = msg {
      event!(Level::WARN, ?msg, "Removing message");
      room.redact(msg.event_id(), reason, None).await?;
    }
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
