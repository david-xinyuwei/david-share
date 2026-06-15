// TRIPLE:
//   Skill: azure-identity-dotnet
//   Prompt: "Using azure-identity-dotnet skill, write C# code that acquires tokens for
//            3 scopes (Foundry, AOAI, Graph) using DefaultAzureCredential."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet/skills/azure-identity-dotnet

using Azure.Identity;

var credential = new DefaultAzureCredential();

var foundryToken = await credential.GetTokenAsync(
    new Azure.Core.TokenRequestContext(new[] { "https://ai.azure.com/.default" }));
Console.WriteLine($"Foundry token: ...{foundryToken.Token[^20..]}");

var aoaiToken = await credential.GetTokenAsync(
    new Azure.Core.TokenRequestContext(new[] { "https://cognitiveservices.azure.com/.default" }));
Console.WriteLine($"AOAI token:    ...{aoaiToken.Token[^20..]}");

var graphToken = await credential.GetTokenAsync(
    new Azure.Core.TokenRequestContext(new[] { "https://graph.microsoft.com/.default" }));
Console.WriteLine($"Graph token:   ...{graphToken.Token[^20..]}");
