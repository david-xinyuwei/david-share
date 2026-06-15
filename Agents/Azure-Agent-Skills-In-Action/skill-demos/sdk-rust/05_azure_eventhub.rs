// TRIPLE:
//   Skill: azure-eventhub-rust
//   Prompt: "Using azure-eventhub-rust skill, write Rust code that produces events using the azure_messaging_eventhubs crate."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-rust/skills/azure-eventhub-rust

use azure_messaging_eventhubs::producer::ProducerClient;
use azure_identity::DefaultAzureCredential;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let namespace = std::env::var("AZURE_EVENTHUB_NAMESPACE")?;
    let eventhub_name = std::env::var("AZURE_EVENTHUB_NAME")?;
    let credential = Arc::new(DefaultAzureCredential::new()?);

    let producer = ProducerClient::new(
        namespace,
        eventhub_name.clone(),
        credential,
        None,
    );

    // Create and send a batch of events
    let mut batch = producer.create_batch(None).await?;

    let events = vec![
        r#"{"sensor":"temp","value":22.5}"#,
        r#"{"sensor":"temp","value":23.1}"#,
        r#"{"sensor":"humidity","value":45.0}"#,
    ];

    for event_data in &events {
        batch.try_add_event_data(event_data.as_bytes())?;
    }

    producer.send_batch(&batch).await?;
    println!("Sent batch of {} events to '{}'.", events.len(), eventhub_name);

    Ok(())
}
