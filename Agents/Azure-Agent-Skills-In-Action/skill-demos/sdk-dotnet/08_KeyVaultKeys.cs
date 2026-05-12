// TRIPLE:
//   Skill: azure-security-keyvault-keys-dotnet
//   Prompt: "Using azure-security-keyvault-keys-dotnet skill, write C# code that creates
//            an RSA key in Key Vault and uses CryptographyClient to sign/verify a payload."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet/skills/azure-security-keyvault-keys-dotnet

using System.Text;
using Azure.Identity;
using Azure.Security.KeyVault.Keys;
using Azure.Security.KeyVault.Keys.Cryptography;

var vaultUrl = new Uri(Environment.GetEnvironmentVariable("KEY_VAULT_URL")!);
var keyClient = new KeyClient(vaultUrl, new DefaultAzureCredential());

// Create RSA key (per skill: use KeyClient for key management, CryptographyClient for crypto ops)
var key = (await keyClient.CreateRsaKeyAsync(new CreateRsaKeyOptions("agent-signing-key")
{
    KeySize = 2048,
    ExpiresOn = DateTimeOffset.UtcNow.AddDays(365),
})).Value;
Console.WriteLine($"Created key: {key.Name} ({key.KeyType})");

// Sign with CryptographyClient
var cryptoClient = keyClient.GetCryptographyClient(key.Name, key.Properties.Version);
var data = Encoding.UTF8.GetBytes("Agent evaluation result hash");
var signature = (await cryptoClient.SignDataAsync(SignatureAlgorithm.RS256, data)).Signature;
Console.WriteLine($"Signed: {Convert.ToBase64String(signature)[..40]}...");

// Verify
var verifyResult = await cryptoClient.VerifyDataAsync(SignatureAlgorithm.RS256, data, signature);
Console.WriteLine($"Verified: {verifyResult.IsValid}");
