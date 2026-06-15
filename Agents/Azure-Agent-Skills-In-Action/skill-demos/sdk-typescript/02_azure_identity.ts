// TRIPLE:
//   Skill: azure-identity-ts
//   Prompt: "Using azure-identity-ts skill, write TypeScript code that gets tokens for 3 scopes (ai.azure.com, cognitiveservices, graph)."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript/skills/azure-identity-ts

import { DefaultAzureCredential } from "@azure/identity";

async function main(): Promise<void> {
  const credential = new DefaultAzureCredential();

  const scopes = [
    "https://ai.azure.com/.default",
    "https://cognitiveservices.azure.com/.default",
    "https://graph.microsoft.com/.default",
  ];

  for (const scope of scopes) {
    try {
      const token = await credential.getToken(scope);
      const expiresOn = token.expiresOnTimestamp
        ? new Date(token.expiresOnTimestamp).toISOString()
        : "N/A";
      console.log(`Scope: ${scope}`);
      console.log(`  Token (first 20 chars): ${token.token.substring(0, 20)}...`);
      console.log(`  Expires: ${expiresOn}`);
    } catch (err: any) {
      console.error(`Failed for scope ${scope}: ${err.message}`);
    }
  }
}

main().catch(console.error);
