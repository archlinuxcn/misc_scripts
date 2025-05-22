use matrix_sdk::{Client, Room};
use matrix_sdk::ruma::{
  self,
  OwnedRoomAliasId, OwnedRoomOrAliasId,
  OwnedUserId, OwnedRoomId, OwnedEventId, EventId,
  events::{
    AnySyncTimelineEvent,
    AnySyncMessageLikeEvent,
    SyncMessageLikeEvent,
    room::message::{
      RoomMessageEventContent, ReplacementMetadata,
      ForwardThread, AddMentions,
      OriginalRoomMessageEvent,
    },
  },
};
use matrix_sdk::deserialized_responses::TimelineEvent;
use tokio::net::{UnixListener, UnixStream};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tracing::{event, Level};

use crate::util::Result;

struct Ipc {
  path: String,
  client: Client,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
#[serde(tag="cmd")]
enum Message {
  #[serde(rename="send_message")]
  SendMessage {
    target: OwnedRoomOrAliasId,
    content: String,
    html_content: Option<String>,
    reply_to: Option<OwnedEventId>,
    replaces: Option<OwnedEventId>,
    #[serde(default)]
    return_id: bool,
  },
  #[serde(rename="delete_user_messages")]
  DeleteUserMessages { target: OwnedRoomOrAliasId, user: OwnedUserId },
}

#[derive(serde::Serialize)]
struct ReturnMessage {
  id: OwnedEventId,
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

async fn handle_msg(client: &Client, msg: &[u8]) -> Result<Option<ReturnMessage>> {
  let msg_str = std::str::from_utf8(msg)?;
  event!(Level::DEBUG, msg = msg_str, "got message");
  let msg = serde_json::from_str(msg_str)?;
  match msg {
    Message::SendMessage {
      target, content, html_content,
      reply_to, replaces, return_id,
    } => {
      event!(Level::INFO, msg = msg_str, "sending message");
      let room_id = resolve_to_room_id(client, target).await?;
      if let Some(room) = client.get_room(&room_id) {
        let mut msg = match html_content {
          Some(html) => RoomMessageEventContent::text_html(content, html),
          None => RoomMessageEventContent::text_plain(content),
        };
        let replied_msg = if let Some(evt) = reply_to {
          room_message_event(&room, &evt).await
        } else {
          None
        };
        if let Some(evt) = replaces {
          let meta = ReplacementMetadata::new(evt, None);
          msg = msg.make_replacement(meta, replied_msg.as_ref());
        } else if let Some(replied_msg) = replied_msg {
          msg = msg.make_reply_to(
            &replied_msg, ForwardThread::Yes, AddMentions::Yes,
          );
        }
        let res = room.send(msg).await?;
        if return_id {
          return Ok(Some(ReturnMessage {
            id: res.event_id,
          }))
        }
      } else {
        event!(Level::ERROR, msg = msg_str, "room not found");
      }
    },
    Message::DeleteUserMessages { target, user } => {
      event!(Level::INFO, %target, %user, "deleting messages");
      let room_id = resolve_to_room_id(client, target).await?;
      if let Some(room) = client.get_room(&room_id) {
        delete_spam_messages(room, user).await;
      } else {
        event!(Level::ERROR, msg = msg_str, "room not found");
      }
    }
  }
  Ok(None)
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

async fn ipc_task_one_connection(
  client: Client, mut sock: UnixStream,
) -> Result<()> {
  let mut buf = vec![];
  loop {
    let size = sock.read_u32().await?;
    buf.clear();
    buf.resize(size as usize, 0);
    sock.read_exact(&mut buf).await?;
    match handle_msg(&client, &buf).await {
      Ok(None) => { },
      Ok(m) => {
        let data = serde_json::to_vec(&m)?;
        sock.write_u32(data.len() as u32).await?;
        sock.write_all(&data).await?;
      },
      Err(e) => {
        event!(Level::ERROR,
          error=?e, msg=?&buf, "bad ipc message");
      },
    }
  }
}

async fn ipc_task(ipc: Ipc) -> Result<()> {
  let socket = UnixListener::bind(&ipc.path)?;
  loop {
    let (socket, _) = socket.accept().await?;
    tokio::spawn(ipc_task_one_connection(ipc.client.clone(), socket));
  }
}

pub fn enable(client: Client, mut path: String) -> Result<()> {
  if path.starts_with('@') {
    path.replace_range(0..1, "\0");
  } else {
    let _ = std::fs::remove_file(&path);
  }
  let ipc = Ipc { path, client };
  tokio::spawn(ipc_task(ipc));
  Ok(())
}

async fn room_message_event(
  room: &Room, event_id: &EventId,
) -> Option<OriginalRoomMessageEvent> {
  let m = room.event(event_id, None).await.ok()?;
  let timeline_event = m.into_raw().deserialize().ok()?;
  let AnySyncTimelineEvent::MessageLike(message_like) =
    timeline_event else { return None };
  let AnySyncMessageLikeEvent::RoomMessage(rm) =
    message_like else { return None };
  let SyncMessageLikeEvent::Original(orignal) =
    rm else { return None };
  Some(orignal.into_full_event(room.room_id().to_owned()))
}
