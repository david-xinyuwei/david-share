// TRIPLE:
//   Skill: azure-storage-blob-java
//   Prompt: "Using azure-storage-blob-java skill, write Java code that uploads a blob with DefaultAzureCredential."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java/skills/azure-storage-blob-java

import com.azure.identity.DefaultAzureCredentialBuilder;
import com.azure.storage.blob.BlobClient;
import com.azure.storage.blob.BlobContainerClient;
import com.azure.storage.blob.BlobServiceClient;
import com.azure.storage.blob.BlobServiceClientBuilder;
import com.azure.storage.blob.models.BlobStorageException;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

public class AzureStorageBlob {

    public static void main(String[] args) {
        String account = System.getenv("AZURE_STORAGE_ACCOUNT_NAME");
        String endpoint = String.format("https://%s.blob.core.windows.net", account);

        BlobServiceClient serviceClient = new BlobServiceClientBuilder()
                .endpoint(endpoint)
                .credential(new DefaultAzureCredentialBuilder().build())
                .buildClient();

        // Create container (handle 409 Conflict)
        String containerName = "skill-demo";
        BlobContainerClient containerClient = serviceClient.getBlobContainerClient(containerName);
        try {
            containerClient.create();
            System.out.printf("Container '%s' created.%n", containerName);
        } catch (BlobStorageException e) {
            if (e.getStatusCode() == 409) {
                System.out.printf("Container '%s' already exists.%n", containerName);
            } else {
                throw e;
            }
        }

        // Upload a blob
        String blobName = "hello.txt";
        byte[] data = "Hello from Azure SDK Java skill demo!".getBytes(StandardCharsets.UTF_8);
        BlobClient blobClient = containerClient.getBlobClient(blobName);
        blobClient.upload(new ByteArrayInputStream(data), data.length, true);
        System.out.printf("Blob '%s' uploaded.%n", blobName);
    }
}
