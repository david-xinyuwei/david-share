// TRIPLE:
//   Skill: azure-cosmos-java
//   Prompt: "Using azure-cosmos-java skill, write Java code that creates a Cosmos DB database/container, upserts an item, and queries."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java/skills/azure-cosmos-java

import com.azure.cosmos.CosmosClient;
import com.azure.cosmos.CosmosClientBuilder;
import com.azure.cosmos.CosmosContainer;
import com.azure.cosmos.CosmosDatabase;
import com.azure.cosmos.models.*;
import com.azure.identity.DefaultAzureCredentialBuilder;

import java.time.Instant;
import java.util.Map;

public class AzureCosmos {

    public static void main(String[] args) {
        String endpoint = System.getenv("AZURE_COSMOS_ENDPOINT");

        CosmosClient client = new CosmosClientBuilder()
                .endpoint(endpoint)
                .credential(new DefaultAzureCredentialBuilder().build())
                .consistencyLevel(ConsistencyLevel.SESSION)
                .buildClient();

        // Create database if not exists
        CosmosDatabaseResponse dbResp = client.createDatabaseIfNotExists("skill-demo-db");
        CosmosDatabase database = client.getDatabase(dbResp.getProperties().getId());
        System.out.printf("Database: %s%n", database.getId());

        // Create container with partition key
        CosmosContainerProperties containerProps =
                new CosmosContainerProperties("items", "/category");
        database.createContainerIfNotExists(containerProps);
        CosmosContainer container = database.getContainer("items");
        System.out.printf("Container: %s%n", container.getId());

        // Upsert an item
        Map<String, Object> item = Map.of(
                "id", "item-001",
                "category", "demo",
                "name", "Azure Cosmos Skill Demo",
                "timestamp", Instant.now().toString()
        );
        container.upsertItem(item);
        System.out.println("Upserted: item-001");

        // Query by partition key
        String query = "SELECT * FROM c WHERE c.category = 'demo'";
        CosmosQueryRequestOptions options = new CosmosQueryRequestOptions();
        container.queryItems(query, options, Map.class)
                .forEach(doc -> System.out.printf("  %s: %s%n", doc.get("id"), doc.get("name")));

        client.close();
    }
}
