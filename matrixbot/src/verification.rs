use std::io::Write;

use futures_util::stream::StreamExt;
use matrix_sdk::{
  encryption::verification::{
    format_emojis, Emoji, SasState, SasVerification, Verification, VerificationRequest,
    VerificationRequestState,
  },
  ruma::{
    events::{
      key::verification::request::ToDeviceKeyVerificationRequestEvent,
      room::message::{MessageType, OriginalSyncRoomMessageEvent},
    },
    UserId,
  },
  Client,
};

async fn wait_for_confirmation(sas: SasVerification, emoji: [Emoji; 7]) {
  println!("\nDo the emojis match: \n{}", format_emojis(emoji));
  print!("Confirm with `yes` or cancel with `no`: ");
  std::io::stdout().flush().expect("We should be able to flush stdout");

  let mut input = String::new();
  std::io::stdin().read_line(&mut input).expect("error: unable to read user input");

  match input.trim().to_lowercase().as_ref() {
    "yes" | "true" | "ok" => {
      println!("Confirming...");
      sas.confirm().await.unwrap()
    }
    _ => sas.cancel().await.unwrap(),
  }
}

async fn print_devices(user_id: &UserId, client: &Client) {
  println!("Devices of user {user_id}");

  for device in client.encryption().get_user_devices(user_id).await.unwrap().devices() {
    if device.device_id()
      == client.device_id().expect("We should be logged in now and know our device id")
    {
      continue;
    }

    println!(
      "   {:<10} {:<30} {:<}",
      device.device_id(),
      device.display_name().unwrap_or("-"),
      if device.is_verified() { "✅" } else { "❌" }
    );
  }
}

async fn sas_verification_handler(client: Client, sas: SasVerification) {
  println!(
    "Starting verification with {} {}",
    &sas.other_device().user_id(),
    &sas.other_device().device_id()
  );
  print_devices(sas.other_device().user_id(), &client).await;
  sas.accept().await.unwrap();

  let mut stream = sas.changes();

  while let Some(state) = stream.next().await {
    match state {
      SasState::KeysExchanged { emojis, decimals: _ } => {
        tokio::spawn(wait_for_confirmation(
            sas.clone(),
            emojis.expect("We only support verifications using emojis").emojis,
        ));
      }
      SasState::Done { .. } => {
        let device = sas.other_device();

        println!(
          "Successfully verified device {} {} {:?}",
          device.user_id(),
          device.device_id(),
          device.local_trust_state()
        );

        print_devices(sas.other_device().user_id(), &client).await;

        break;
      }
      SasState::Cancelled(cancel_info) => {
        println!("The verification has been cancelled, reason: {}", cancel_info.reason());

        break;
      }
      SasState::Started { .. } | SasState::Accepted { .. } | SasState::Confirmed => (),
    }
  }
}

async fn request_verification_handler(client: Client, request: VerificationRequest) {
  println!("Accepting verification request from {}", request.other_user_id(),);
  request.accept().await.expect("Can't accept verification request");

  let mut stream = request.changes();

  while let Some(state) = stream.next().await {
    match state {
      VerificationRequestState::Created { .. }
      | VerificationRequestState::Requested { .. }
      | VerificationRequestState::Ready { .. } => (),
      VerificationRequestState::Transitioned { verification } => {
        // We only support SAS verification.
        if let Verification::SasV1(s) = verification {
          tokio::spawn(sas_verification_handler(client, s));
          break;
        }
      }
      VerificationRequestState::Done | VerificationRequestState::Cancelled(_) => break,
    }
  }
}

pub fn enable_verification(client: &Client) {
  client.add_event_handler(
    |ev: ToDeviceKeyVerificationRequestEvent, client: Client| async move {
      let request = client
        .encryption()
        .get_verification_request(&ev.sender, &ev.content.transaction_id)
        .await
        .expect("Request object wasn't created");

        tokio::spawn(request_verification_handler(client, request));
    },
  );

  client.add_event_handler(|ev: OriginalSyncRoomMessageEvent, client: Client| async move {
    if let MessageType::VerificationRequest(_) = &ev.content.msgtype {
      let request = client
        .encryption()
        .get_verification_request(&ev.sender, &ev.event_id)
        .await
        .expect("Request object wasn't created");

        tokio::spawn(request_verification_handler(client, request));
    }
  });
}
