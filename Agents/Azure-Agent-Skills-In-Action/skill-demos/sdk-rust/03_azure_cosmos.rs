// TRIPLE:
//   Skill: azure-cosmos-rust
//   Prompt: "Using azure-cosmos-rust skill, write Rust code that creates a database and upserts an item using the azure_data_cosmos crate."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-rust/skills/azure-cosmos-rust

use azure_data_cosmos::prelude::*;
use azure_identity::DefaultAzureCredential;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Debug, Serialize, Deserialize)]
struct DemoItem {
    id: String,
    category: String,
    name: String,
    timestamp: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let endpoint = std::env::var("AZURE_COSMOS_ENDPOINT")?;
    let credential = Arc::new(DefaultAzureCredential::new()?);

    let client = CosmosClient::new(&endpoint, credential, CosmosOptions::default())?;

    // Create database if not exists
    let db_name = "skill-demo-db";
    client.create_database(db_name).into_future().await.ok();
    let database = client.database_client(db_name);
    println!("Database: {}", db_name);

    // Create container if not exists
    let container_name = "items";
    database
        .create_collection(container_name, "/category")
        .into_future()
        .await
        .ok();
    let container = database.collection_client(container_name);
    println!("Container: {}", container_name);

    // Upsert an item
    let item = DemoItem {
        id: "item-001".to_string(),
        category: "demo".to_string(),
        name: "Azure Cosmos Skill Demo".to_string(),
        timestamp: chrono::Utc::now().to_rfc3339(),
    };

    container
        .document_client(&item.id, &item.category)?
        .replace_document(&item)
        .into_future()
        .await
        .ok();
    println!("Upserted: {}", item.id);

    Ok(())
}
