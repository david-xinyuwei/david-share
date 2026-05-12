// TRIPLE:
//   Skill: azure-security-keyvault-keys-java
//   Prompt: "Using azure-security-keyvault-keys-java skill, write Java code that creates a key and performs sign/verify."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java/skills/azure-security-keyvault-keys-java

import com.azure.identity.DefaultAzureCredentialBuilder;
import com.azure.security.keyvault.keys.KeyClient;
import com.azure.security.keyvault.keys.KeyClientBuilder;
import com.azure.security.keyvault.keys.cryptography.CryptographyClient;
import com.azure.security.keyvault.keys.cryptography.CryptographyClientBuilder;
import com.azure.security.keyvault.keys.cryptography.models.SignResult;
import com.azure.security.keyvault.keys.cryptography.models.SignatureAlgorithm;
import com.azure.security.keyvault.keys.cryptography.models.VerifyResult;
import com.azure.security.keyvault.keys.models.CreateRsaKeyOptions;
import com.azure.security.keyvault.keys.models.KeyVaultKey;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public class KeyVaultKeys {

    public static void main(String[] args) throws Exception {
        String vaultUrl = System.getenv("AZURE_KEYVAULT_URL");

        KeyClient keyClient = new KeyClientBuilder()
                .vaultUrl(vaultUrl)
                .credential(new DefaultAzureCredentialBuilder().build())
                .buildClient();

        // Create an RSA key
        String keyName = "skill-demo-rsa-key";
        CreateRsaKeyOptions keyOptions = new CreateRsaKeyOptions(keyName).setKeySize(2048);
        KeyVaultKey key = keyClient.createRsaKey(keyOptions);
        System.out.printf("Key created: %s (type: %s)%n", key.getName(), key.getKeyType());

        // Sign data
        CryptographyClient cryptoClient = new CryptographyClientBuilder()
                .keyIdentifier(key.getId())
                .credential(new DefaultAzureCredentialBuilder().build())
                .buildClient();

        byte[] data = "Hello from Azure SDK Java skill demo!".getBytes(StandardCharsets.UTF_8);
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(data);

        SignResult signResult = cryptoClient.sign(SignatureAlgorithm.RS256, digest);
        System.out.printf("Signed with algorithm: %s%n", signResult.getAlgorithm());

        // Verify signature
        VerifyResult verifyResult = cryptoClient.verify(SignatureAlgorithm.RS256, digest,
                signResult.getSignature());
        System.out.printf("Signature valid: %s%n", verifyResult.isValid());
    }
}
