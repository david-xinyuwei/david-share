# Managed Meeting Agent Customer Start Here

This package contains the independent Managed Agent implementation. The earlier `Agents/Meeting-Agent` repository remains unchanged.

## Supported Path

`Meeting events -> local Windows UI -> Foundry Managed Agent -> mind map and editable PPTX -> unsent New Outlook draft`

## Prerequisites

- Windows 11 and New Outlook
- Python 3.12
- Node.js 22 or newer
- Azure CLI signed in through a dedicated `AZURE_CONFIG_DIR`
- Foundry access to the deployed `managed-meeting-agent`

## Start

Run in native Windows PowerShell:

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-<tenant>-<subscription>"
az account show

.\scripts\start-ui.ps1 `
  -ManagedAgentEndpoint "https://<account>.services.ai.azure.com/api/projects/<project>/openai/v1/responses" `
  -ManagedAgentName "managed-meeting-agent" `
  -ManagedAgentVersion "1" `
  -AzureConfigDir $env:AZURE_CONFIG_DIR
```

Open `http://127.0.0.1:4173`, select **Meeting JSON**, upload `examples/meeting-record-stargate.json`, and choose **Generate meeting package**.

## Acceptance

Accept the run only when:

1. The header shows **Foundry Managed Agent** and **entra auth**.
2. All six actual processing stages complete.
3. The page displays a mind map and downloads valid JSON, Mermaid, PNG, PPTX, and EML artifacts.
4. The PowerPoint opens as an editable six-slide deck.
5. New Outlook opens an editable draft with `X-Unsent: 1`, the inline mind map, and PNG/PPTX attachments.
6. The user must select **Send** manually.

The customer path uses no AOAI API key and has no automatic-send capability. See [README.md](README.md) for architecture, evidence, tests, and boundaries.
