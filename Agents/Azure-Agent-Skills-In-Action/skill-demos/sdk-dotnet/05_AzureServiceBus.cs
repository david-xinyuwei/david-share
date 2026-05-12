// TRIPLE:
//   Skill: azure-servicebus-dotnet
//   Prompt: "Using azure-servicebus-dotnet skill, write C# code that sends a message to
//            a Service Bus queue and receives with peek-lock + complete/dead-letter."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet/skills/azure-servicebus-dotnet

using System.Text.Json;
using Azure.Identity;
using Azure.Messaging.ServiceBus;

var ns = Environment.GetEnvironmentVariable("SERVICEBUS_NAMESPACE")!;
var queue = "document-ingestion";
await using var client = new ServiceBusClient(ns, new DefaultAzureCredential());

// Send
await using var sender = client.CreateSender(queue);
var body = JsonSerializer.Serialize(new { blob_url = "https://storage/doc.pdf", action = "index" });
await sender.SendMessageAsync(new ServiceBusMessage(body) { ContentType = "application/json" });
Console.WriteLine($"Sent to {queue}");

// Receive with peek-lock
await using var receiver = client.CreateReceiver(queue);
var msg = await receiver.ReceiveMessageAsync(TimeSpan.FromSeconds(10));
if (msg != null)
{
    try
    {
        var doc = JsonSerializer.Deserialize<JsonElement>(msg.Body.ToString());
        Console.WriteLine($"Received: {doc}");
        await receiver.CompleteMessageAsync(msg);
        Console.WriteLine("  → completed");
    }
    catch (JsonException)
    {
        await receiver.DeadLetterMessageAsync(msg, "parse_failure", "Invalid JSON");
        Console.WriteLine("  → dead-lettered");
    }
}
