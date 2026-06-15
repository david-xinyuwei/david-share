// TRIPLE:
//   Skill: azure-resource-manager-cosmosdb-dotnet
//   Prompt: "Using azure-resource-manager-cosmosdb-dotnet skill, write C# code that uses
//            ARM SDK to create a Cosmos DB account + database + container (control plane)."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-cosmosdb-dotnet

using Azure.Identity;
using Azure.ResourceManager;
using Azure.ResourceManager.CosmosDB;
using Azure.ResourceManager.CosmosDB.Models;

var subscriptionId = Environment.GetEnvironmentVariable("AZURE_SUBSCRIPTION_ID")!;
var rgName = "agent-infra";

var arm = new ArmClient(new DefaultAzureCredential());
var subscription = arm.GetSubscriptionResource(new Azure.Core.ResourceIdentifier($"/subscriptions/{subscriptionId}"));
var rg = (await subscription.GetResourceGroups().GetAsync(rgName)).Value;

// Create Cosmos DB account (NoSQL API)
var accountData = new CosmosDBAccountCreateOrUpdateContent(
    new Azure.Core.AzureLocation("eastus"),
    new[] { new CosmosDBAccountLocation { LocationName = "eastus" } })
{
    Kind = CosmosDBAccountKind.GlobalDocumentDB,
};
var account = (await rg.GetCosmosDBAccounts().CreateOrUpdateAsync(
    Azure.WaitUntil.Completed, "agent-cosmos", accountData)).Value;
Console.WriteLine($"Account: {account.Data.Name}");

// Create database
var dbData = new CosmosDBSqlDatabaseCreateOrUpdateContent(
    new Azure.Core.ResourceIdentifier("dummy"),
    new CosmosDBSqlDatabaseResourceInfo("agent-db"));
var db = (await account.GetCosmosDBSqlDatabases().CreateOrUpdateAsync(
    Azure.WaitUntil.Completed, "agent-db", dbData)).Value;
Console.WriteLine($"Database: {db.Data.Name}");
