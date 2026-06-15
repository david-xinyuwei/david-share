// TRIPLE:
//   Skill: azure-ai-projects-java
//   Prompt: "Using azure-ai-projects-java skill, write Java code that creates an AIProjectClient and lists deployments."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java/skills/azure-ai-projects-java

import com.azure.ai.projects.AIProjectClient;
import com.azure.ai.projects.AIProjectClientBuilder;
import com.azure.ai.projects.models.Deployment;
import com.azure.identity.DefaultAzureCredentialBuilder;

public class AzureAiProjects {

    public static void main(String[] args) {
        String connectionString = System.getenv("AZURE_AI_PROJECT_CONNECTION_STRING");

        AIProjectClient client = new AIProjectClientBuilder()
                .connectionString(connectionString)
                .credential(new DefaultAzureCredentialBuilder().build())
                .buildClient();

        System.out.println("=== Foundry Project Deployments ===");
        for (Deployment deployment : client.deployments().list()) {
            System.out.printf("  Name: %s%n", deployment.getName());
            System.out.printf("  Model: %s%n",
                    deployment.getProperties() != null
                            ? deployment.getProperties().getModel().getName()
                            : "N/A");
            System.out.println("---");
        }
    }
}
