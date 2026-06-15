// TRIPLE:
//   Skill: azure-storage-blob-ts
//   Prompt: "Using azure-storage-blob-ts skill, write TypeScript code that uploads a blob, creates a container (handle 409), and generates a user-delegation SAS."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript/skills/azure-storage-blob-ts

import {
  BlobServiceClient,
  generateBlobSASQueryParameters,
  BlobSASPermissions,
  SASProtocol,
} from "@azure/storage-blob";
import { DefaultAzureCredential } from "@azure/identity";

async function main(): Promise<void> {
  const account = process.env["AZURE_STORAGE_ACCOUNT_NAME"]!;
  const credential = new DefaultAzureCredential();
  const blobServiceClient = new BlobServiceClient(
    `https://${account}.blob.core.windows.net`,
    credential
  );

  // Create container (handle 409 Conflict if it already exists)
  const containerName = "skill-demo";
  const containerClient = blobServiceClient.getContainerClient(containerName);
  try {
    await containerClient.create();
    console.log(`Container '${containerName}' created.`);
  } catch (err: any) {
    if (err.statusCode === 409) {
      console.log(`Container '${containerName}' already exists.`);
    } else {
      throw err;
    }
  }

  // Upload a blob
  const blobName = "hello.txt";
  const blockBlobClient = containerClient.getBlockBlobClient(blobName);
  const content = "Hello from Azure SDK TypeScript skill demo!";
  await blockBlobClient.upload(content, Buffer.byteLength(content));
  console.log(`Blob '${blobName}' uploaded.`);

  // Generate user-delegation SAS
  const startsOn = new Date();
  const expiresOn = new Date(startsOn.getTime() + 3600 * 1000);
  const userDelegationKey = await blobServiceClient.getUserDelegationKey(startsOn, expiresOn);
  const sasToken = generateBlobSASQueryParameters(
    {
      containerName,
      blobName,
      permissions: BlobSASPermissions.parse("r"),
      startsOn,
      expiresOn,
      protocol: SASProtocol.Https,
    },
    userDelegationKey,
    account
  ).toString();

  console.log(`SAS URL: ${blockBlobClient.url}?${sasToken}`);
}

main().catch(console.error);
