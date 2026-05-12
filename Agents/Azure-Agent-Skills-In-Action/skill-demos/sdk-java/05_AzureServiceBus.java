// TRIPLE:
//   Skill: azure-servicebus-java
//   Prompt: "Using azure-servicebus-java skill, write Java code that sends and receives messages with peek-lock."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java/skills/azure-servicebus-java

import com.azure.identity.DefaultAzureCredentialBuilder;
import com.azure.messaging.servicebus.*;

import java.time.Duration;

public class AzureServiceBus {

    public static void main(String[] args) {
        String namespace = System.getenv("AZURE_SERVICEBUS_NAMESPACE");
        String queueName = System.getenv("AZURE_SERVICEBUS_QUEUE") != null
                ? System.getenv("AZURE_SERVICEBUS_QUEUE") : "skill-demo-queue";

        // Send a message
        ServiceBusSenderClient sender = new ServiceBusClientBuilder()
                .fullyQualifiedNamespace(namespace)
                .credential(new DefaultAzureCredentialBuilder().build())
                .sender()
                .queueName(queueName)
                .buildClient();

        ServiceBusMessage message = new ServiceBusMessage("{\"action\":\"process\"}")
                .setContentType("application/json")
                .setSubject("skill-demo");
        sender.sendMessage(message);
        System.out.println("Message sent.");
        sender.close();

        // Receive with peek-lock (default)
        ServiceBusReceiverClient receiver = new ServiceBusClientBuilder()
                .fullyQualifiedNamespace(namespace)
                .credential(new DefaultAzureCredentialBuilder().build())
                .receiver()
                .queueName(queueName)
                .buildClient();

        for (ServiceBusReceivedMessage msg : receiver.receiveMessages(1, Duration.ofSeconds(5))) {
            System.out.printf("Received: %s%n", msg.getBody().toString());
            try {
                // Process then complete
                receiver.complete(msg);
                System.out.println("Message completed.");
            } catch (Exception e) {
                receiver.deadLetter(msg, new DeadLetterOptions()
                        .setDeadLetterReason("ProcessingFailed")
                        .setDeadLetterErrorDescription("Demo: simulated failure"));
                System.out.println("Message dead-lettered.");
            }
        }

        receiver.close();
    }
}
