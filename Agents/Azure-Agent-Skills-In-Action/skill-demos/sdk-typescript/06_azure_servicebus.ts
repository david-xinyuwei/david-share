// TRIPLE:
//   Skill: azure-servicebus-ts
//   Prompt: "Using azure-servicebus-ts skill, write TypeScript code that sends a message, receives with peek-lock, and completes or dead-letters."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript/skills/azure-servicebus-ts

import { ServiceBusClient, ServiceBusReceivedMessage } from "@azure/service-bus";
import { DefaultAzureCredential } from "@azure/identity";

async function main(): Promise<void> {
  const fullyQualifiedNamespace = process.env["AZURE_SERVICEBUS_NAMESPACE"]!;
  const queueName = process.env["AZURE_SERVICEBUS_QUEUE"] ?? "skill-demo-queue";
  const credential = new DefaultAzureCredential();

  const sbClient = new ServiceBusClient(fullyQualifiedNamespace, credential);

  // Send a message
  const sender = sbClient.createSender(queueName);
  await sender.sendMessages({
    body: { action: "process", timestamp: new Date().toISOString() },
    contentType: "application/json",
    subject: "skill-demo",
  });
  console.log("Message sent.");
  await sender.close();

  // Receive with peek-lock (default mode)
  const receiver = sbClient.createReceiver(queueName);
  const messages: ServiceBusReceivedMessage[] = await receiver.receiveMessages(1, {
    maxWaitTimeInMs: 5000,
  });

  for (const msg of messages) {
    console.log(`Received: ${JSON.stringify(msg.body)}`);
    try {
      // Process message then complete
      await receiver.completeMessage(msg);
      console.log("Message completed.");
    } catch {
      // On failure, dead-letter the message
      await receiver.deadLetterMessage(msg, {
        deadLetterReason: "ProcessingFailed",
        deadLetterErrorDescription: "Demo: simulated failure",
      });
      console.log("Message dead-lettered.");
    }
  }

  await receiver.close();
  await sbClient.close();
}

main().catch(console.error);
