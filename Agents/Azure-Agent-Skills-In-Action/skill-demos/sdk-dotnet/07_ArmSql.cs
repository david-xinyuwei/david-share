// TRIPLE:
//   Skill: azure-resource-manager-sql-dotnet
//   Prompt: "Using azure-resource-manager-sql-dotnet skill, write C# code that uses ARM SDK
//            to provision a SQL Server + database with Entra-only auth (no SQL passwords)."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-sql-dotnet

using Azure.Identity;
using Azure.ResourceManager;
using Azure.ResourceManager.Sql;
using Azure.ResourceManager.Sql.Models;

var arm = new ArmClient(new DefaultAzureCredential());
var sub = arm.GetSubscriptionResource(new Azure.Core.ResourceIdentifier(
    $"/subscriptions/{Environment.GetEnvironmentVariable("AZURE_SUBSCRIPTION_ID")}"));
var rg = (await sub.GetResourceGroups().GetAsync("agent-infra")).Value;

// SQL Server with Entra-only auth (per skill: NO SQL passwords)
var serverData = new SqlServerData(new Azure.Core.AzureLocation("eastus"))
{
    AdministratorLogin = null,  // Entra-only — no SQL admin
    MinimalTlsVersion = "1.2",
};
var server = (await rg.GetSqlServers().CreateOrUpdateAsync(
    Azure.WaitUntil.Completed, "agent-sql", serverData)).Value;
Console.WriteLine($"Server: {server.Data.Name}");

// Database
var dbData = new SqlDatabaseData(new Azure.Core.AzureLocation("eastus"))
{
    Sku = new SqlSku("Basic"),
};
var db = (await server.GetSqlDatabases().CreateOrUpdateAsync(
    Azure.WaitUntil.Completed, "agent-metadata", dbData)).Value;
Console.WriteLine($"Database: {db.Data.Name}");
