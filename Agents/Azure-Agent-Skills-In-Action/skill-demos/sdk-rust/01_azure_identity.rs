// TRIPLE:
//   Skill: azure-identity-rust
//   Prompt: "Using azure-identity-rust skill, write Rust code that gets a token with DefaultAzureCredential using async tokio."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-rust/skills/azure-identity-rust

use azure_identity::DefaultAzureCredential;
use azure_core::credentials::TokenRequestOptions;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let credential = Arc::new(DefaultAzureCredential::new()?);

    let scopes = [
        "https://management.azure.com/.default",
        "https://cognitiveservices.azure.com/.default",
        "https://storage.azure.com/.default",
    ];

    for scope in &scopes {
        let options = TokenRequestOptions::default();
        match credential.get_token(&[scope], &options).await {
            Ok(token) => {
                let preview = &token.token.secret()[..20];
                println!("Scope: {}", scope);
                println!("  Token (first 20 chars): {}...", preview);
                println!("  Expires: {:?}", token.expires_on);
            }
            Err(e) => {
                eprintln!("Failed for scope {}: {}", scope, e);
            }
        }
    }

    Ok(())
}
