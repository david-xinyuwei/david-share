// TRIPLE:
//   Skill: azure-search-documents-dotnet
//   Prompt: "Using azure-search-documents-dotnet skill, write C# code that performs hybrid
//            search (vector + BM25) with semantic ranker using DefaultAzureCredential."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet/skills/azure-search-documents-dotnet

using Azure.Identity;
using Azure.Search.Documents;
using Azure.Search.Documents.Models;

var endpoint = new Uri(Environment.GetEnvironmentVariable("SEARCH_ENDPOINT")!);
var client = new SearchClient(endpoint, "agent-docs", new DefaultAzureCredential());

var options = new SearchOptions
{
    QueryType = SearchQueryType.Semantic,
    SemanticSearch = new() { SemanticConfigurationName = "default" },
    Size = 5,
    Select = { "title", "content", "url" },
    VectorSearch = new()
    {
        Queries = { new VectorizedQuery(new float[1536]) { KNearestNeighborsCount = 5, Fields = { "embedding" } } }
    }
};

var results = await client.SearchAsync<SearchDocument>("How does Azure MCP authenticate?", options);
await foreach (var result in results.Value.GetResultsAsync())
{
    Console.WriteLine($"[{result.Score:F2}] {result.Document["title"]}");
}
