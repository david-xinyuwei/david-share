// TRIPLE:
//   Skill: azure-storage-blob-rust
//   Prompt: "Using azure-storage-blob-rust skill, write Rust code that uploads a blob using the azure_storage_blob crate."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-rust/skills/azure-storage-blob-rust

use azure_identity::DefaultAzureCredential;
use azure_storage_blob::prelude::*;
use azure_core::request_options::ContentLength;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let account = std::env::var("AZURE_STORAGE_ACCOUNT_NAME")?;
    let credential = Arc::new(DefaultAzureCredential::new()?);

    let blob_service_client = BlobServiceClient::new(
        &account,
        credential.clone(),
    );

    let container_name = "skill-demo";
    let container_client = blob_service_client.container_client(container_name);

    // Create container (ignore if already exists)
    match container_client.create().await {
        Ok(_) => println!("Container '{}' created.", container_name),
        Err(e) if e.to_string().contains("ContainerAlreadyExists") => {
            println!("Container '{}' already exists.", container_name);
        }
        Err(e) => return Err(e.into()),
    }

    // Upload a blob
    let blob_name = "hello.txt";
    let blob_client = container_client.blob_client(blob_name);
    let data = b"Hello from Azure SDK Rust skill demo!";

    blob_client
        .put_block_blob(data.to_vec())
        .content_type("text/plain")
        .await?;

    println!("Blob '{}' uploaded ({} bytes).", blob_name, data.len());

    Ok(())
}
