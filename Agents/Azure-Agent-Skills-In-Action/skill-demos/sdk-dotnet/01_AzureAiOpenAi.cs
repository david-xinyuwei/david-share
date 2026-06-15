// TRIPLE:
//   Skill: azure-ai-openai-dotnet
//   Prompt: "Using azure-ai-openai-dotnet skill, write C# code that sends a chat completion
//            to gpt-4.1-mini via AzureOpenAIClient + DefaultAzureCredential."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet/skills/azure-ai-openai-dotnet

using Azure.AI.OpenAI;
using Azure.Identity;
using OpenAI.Chat;

var client = new AzureOpenAIClient(
    new Uri(Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")!),
    new DefaultAzureCredential());

var chat = client.GetChatClient("gpt-4.1-mini");
var response = await chat.CompleteChatAsync("Summarize Azure Agent Skills in one sentence.");
Console.WriteLine(response.Value.Content[0].Text);
