// TRIPLE:
//   Skill: azure-ai-projects-dotnet
//   Prompt: "Using azure-ai-projects-dotnet skill, write C# code that connects to a Foundry
//            project, lists deployments, and gets inference client."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet/skills/azure-ai-projects-dotnet

using Azure.AI.Projects;
using Azure.Identity;

var endpoint = Environment.GetEnvironmentVariable("FOUNDRY_PROJECT_ENDPOINT")!;
var client = new AIProjectClient(new Uri(endpoint), new DefaultAzureCredential());

await foreach (var deployment in client.GetDeploymentsAsync())
{
    Console.WriteLine($"Deployment: {deployment.Name} ({deployment.Properties.Model.Name})");
}

var inference = client.GetChatCompletionsClient();
Console.WriteLine("Inference client ready.");
