// TRIPLE:
//   Skill: azure-ai-projects-ts
//   Prompt: "Using azure-ai-projects-ts skill, write TypeScript code that connects to a Foundry project and lists deployments."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript/skills/azure-ai-projects-ts

import { AIProjectClient } from "@azure/ai-projects";
import { DefaultAzureCredential } from "@azure/identity";

async function main(): Promise<void> {
  const connectionString = process.env["AZURE_AI_PROJECT_CONNECTION_STRING"]!;
  const credential = new DefaultAzureCredential();

  const client = new AIProjectClient(connectionString, credential);

  // List deployments in the project
  console.log("=== Foundry Project Deployments ===");
  const deployments = await client.deployments.list();
  for await (const deployment of deployments) {
    console.log(`  Name: ${deployment.name}`);
    console.log(`  Model: ${deployment.properties?.model?.name ?? "N/A"}`);
    console.log(`  State: ${deployment.properties?.provisioningState ?? "N/A"}`);
    console.log("---");
  }

  // Get project connection info
  const connections = await client.connections.list();
  for await (const conn of connections) {
    console.log(`Connection: ${conn.name} (${conn.properties?.category})`);
  }
}

main().catch(console.error);
