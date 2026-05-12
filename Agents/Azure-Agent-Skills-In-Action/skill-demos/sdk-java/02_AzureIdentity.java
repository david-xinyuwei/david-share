// TRIPLE:
//   Skill: azure-identity-java
//   Prompt: "Using azure-identity-java skill, write Java code that gets tokens for 3 scopes (ai.azure.com, cognitiveservices, graph)."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java/skills/azure-identity-java

import com.azure.core.credential.AccessToken;
import com.azure.core.credential.TokenRequestContext;
import com.azure.identity.DefaultAzureCredential;
import com.azure.identity.DefaultAzureCredentialBuilder;

public class AzureIdentity {

    public static void main(String[] args) {
        DefaultAzureCredential credential = new DefaultAzureCredentialBuilder().build();

        String[] scopes = {
                "https://ai.azure.com/.default",
                "https://cognitiveservices.azure.com/.default",
                "https://graph.microsoft.com/.default"
        };

        for (String scope : scopes) {
            try {
                TokenRequestContext context = new TokenRequestContext().addScopes(scope);
                AccessToken token = credential.getTokenSync(context);
                System.out.printf("Scope: %s%n", scope);
                System.out.printf("  Token (first 20 chars): %s...%n",
                        token.getToken().substring(0, 20));
                System.out.printf("  Expires: %s%n", token.getExpiresAt());
            } catch (Exception e) {
                System.err.printf("Failed for scope %s: %s%n", scope, e.getMessage());
            }
        }
    }
}
