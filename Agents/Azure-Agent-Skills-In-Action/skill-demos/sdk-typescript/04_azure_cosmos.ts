// TRIPLE:
//   Skill: azure-cosmos-ts
//   Prompt: "Using azure-cosmos-ts skill, write TypeScript code that connects to Cosmos DB, creates a database/container, upserts an item, and queries by partition key."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript/skills/azure-cosmos-ts

import { CosmosClient } from "@azure/cosmos";
import { DefaultAzureCredential } from "@azure/identity";

async function main(): Promise<void> {
  const endpoint = process.env["AZURE_COSMOS_ENDPOINT"]!;
  const credential = new DefaultAzureCredential();
  const client = new CosmosClient({ endpoint, aadCredentials: credential });

  // Create database if not exists
  const { database } = await client.databases.createIfNotExists({ id: "skill-demo-db" });
  console.log(`Database: ${database.id}`);

  // Create container with partition key
  const { container } = await database.containers.createIfNotExists({
    id: "items",
    partitionKey: { paths: ["/category"] },
  });
  console.log(`Container: ${container.id}`);

  // Upsert an item
  const item = {
    id: "item-001",
    category: "demo",
    name: "Azure Cosmos Skill Demo",
    timestamp: new Date().toISOString(),
  };
  const { resource: upserted } = await container.items.upsert(item);
  console.log(`Upserted: ${upserted?.id}`);

  // Query by partition key
  const querySpec = {
    query: "SELECT * FROM c WHERE c.category = @category",
    parameters: [{ name: "@category", value: "demo" }],
  };
  const { resources } = await container.items.query(querySpec).fetchAll();
  console.log(`Query results: ${resources.length} item(s)`);
  for (const r of resources) {
    console.log(`  ${r.id}: ${r.name}`);
  }
}

main().catch(console.error);
