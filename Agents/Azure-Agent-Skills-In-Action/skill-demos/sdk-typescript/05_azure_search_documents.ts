// TRIPLE:
//   Skill: azure-search-documents-ts
//   Prompt: "Using azure-search-documents-ts skill, write TypeScript code that performs hybrid search (vector+BM25) with semantic ranker."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript/skills/azure-search-documents-ts

import { SearchClient, AzureKeyCredential } from "@azure/search-documents";
import { DefaultAzureCredential } from "@azure/identity";

async function main(): Promise<void> {
  const endpoint = process.env["AZURE_SEARCH_ENDPOINT"]!;
  const indexName = process.env["AZURE_SEARCH_INDEX"] ?? "skill-demo-index";
  const credential = new DefaultAzureCredential();

  const client = new SearchClient(endpoint, indexName, credential);

  // Hybrid search: keyword (BM25) + vector + semantic ranker
  const queryText = "How to deploy a model on Azure AI Foundry?";
  const queryVector: number[] = new Array(1536).fill(0).map(() => Math.random()); // placeholder embedding

  const results = await client.search(queryText, {
    vectorSearchOptions: {
      queries: [
        {
          kind: "vector",
          vector: queryVector,
          kNearestNeighborsCount: 5,
          fields: ["contentVector"],
        },
      ],
    },
    queryType: "semantic",
    semanticSearchOptions: {
      configurationName: "my-semantic-config",
    },
    top: 5,
    select: ["title", "content", "url"],
  });

  console.log("=== Hybrid Search Results ===");
  for await (const result of results.results) {
    const doc = result.document as any;
    console.log(`  Score: ${result.score?.toFixed(4)}`);
    console.log(`  Reranker: ${result.rerankerScore?.toFixed(4) ?? "N/A"}`);
    console.log(`  Title: ${doc.title}`);
    console.log("---");
  }
}

main().catch(console.error);
