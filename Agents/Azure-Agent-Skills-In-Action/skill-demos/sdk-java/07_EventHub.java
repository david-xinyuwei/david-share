// TRIPLE:
//   Skill: azure-eventhub-java
//   Prompt: "Using azure-eventhub-java skill, write Java code that sends a producer batch and consumes events with checkpoint."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java/skills/azure-eventhub-java

import com.azure.identity.DefaultAzureCredentialBuilder;
import com.azure.messaging.eventhubs.*;
import com.azure.messaging.eventhubs.checkpointstore.blob.BlobCheckpointStore;
import com.azure.messaging.eventhubs.models.EventPosition;
import com.azure.storage.blob.BlobContainerAsyncClient;
import com.azure.storage.blob.BlobContainerClientBuilder;

import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

public class EventHub {

    public static void main(String[] args) throws Exception {
        String namespace = System.getenv("AZURE_EVENTHUB_NAMESPACE");
        String eventHubName = System.getenv("AZURE_EVENTHUB_NAME");
        String storageAccount = System.getenv("AZURE_STORAGE_ACCOUNT_NAME");
        String containerName = "eventhub-checkpoints";

        // --- Producer: send a batch ---
        EventHubProducerClient producer = new EventHubClientBuilder()
                .fullyQualifiedNamespace(namespace)
                .eventHubName(eventHubName)
                .credential(new DefaultAzureCredentialBuilder().build())
                .buildProducerClient();

        EventDataBatch batch = producer.createBatch();
        batch.tryAdd(new EventData("{\"sensor\":\"temp\",\"value\":22.5}"));
        batch.tryAdd(new EventData("{\"sensor\":\"temp\",\"value\":23.1}"));
        producer.send(batch);
        System.out.printf("Sent batch of %d events.%n", batch.getCount());
        producer.close();

        // --- Consumer: receive with checkpoint ---
        BlobContainerAsyncClient blobClient = new BlobContainerClientBuilder()
                .endpoint(String.format("https://%s.blob.core.windows.net", storageAccount))
                .containerName(containerName)
                .credential(new DefaultAzureCredentialBuilder().build())
                .buildAsyncClient();

        CountDownLatch latch = new CountDownLatch(2);

        EventProcessorClient processor = new EventProcessorClientBuilder()
                .fullyQualifiedNamespace(namespace)
                .eventHubName(eventHubName)
                .consumerGroup(EventHubClientBuilder.DEFAULT_CONSUMER_GROUP_NAME)
                .credential(new DefaultAzureCredentialBuilder().build())
                .checkpointStore(new BlobCheckpointStore(blobClient))
                .initialEventPosition(EventPosition.latest())
                .processEvent(eventContext -> {
                    System.out.printf("Received: %s%n", eventContext.getEventData().getBodyAsString());
                    eventContext.updateCheckpoint();
                    latch.countDown();
                })
                .processError(errorContext ->
                        System.err.printf("Error: %s%n", errorContext.getThrowable().getMessage()))
                .buildEventProcessorClient();

        processor.start();
        latch.await(30, TimeUnit.SECONDS);
        processor.stop();
        System.out.println("Consumer stopped.");
    }
}
